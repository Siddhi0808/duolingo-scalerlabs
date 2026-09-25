"""M1 model tests: relationships, ordering, constraints and delete rules."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Achievement,
    AchievementMetric,
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    LessonCompletion,
    LessonSession,
    SessionAnswer,
    SessionMode,
    SessionStatus,
    Skill,
    Unit,
    User,
    UserAchievement,
    XpEvent,
    XpSource,
)
from tests.factories import (
    NOW,
    TODAY,
    first_lesson,
    make_course_tree,
    make_exercise,
    make_user,
    start_session,
)


def fresh_session(engine: Engine) -> Session:
    """A new ORM session, so assertions read from the database, not the identity map."""
    return sessionmaker(bind=engine)()


# --------------------------------------------------------------------------- content


def test_content_hierarchy_relationships(db: Session, engine: Engine) -> None:
    make_course_tree(db)
    db.commit()

    with fresh_session(engine) as s:
        course = s.scalars(select(Course).where(Course.slug == "es-en")).one()
        unit = course.units[0]
        skill = unit.skills[0]
        lesson = skill.lessons[0]

        assert unit.course is course  # Course -> Unit
        assert skill.unit is unit  # Unit -> Skill
        assert lesson.skill is skill  # Skill -> Lesson
        assert [e.lesson for e in lesson.exercises] == [lesson, lesson]  # Lesson -> Exercise


def test_children_are_returned_in_order_index_order(db: Session, engine: Engine) -> None:
    course = make_course_tree(db)
    lesson = first_lesson(course)
    # Insert out of order on purpose; the relationship must sort by order_index.
    db.add_all(
        [
            make_exercise(5, ExerciseType.FILL_BLANK, lesson=lesson),
            make_exercise(3, ExerciseType.WORD_BANK, lesson=lesson),
            Unit(course=course, order_index=2, title="Travel"),
            Unit(course=course, order_index=1, title="Daily life"),
        ]
    )
    db.commit()

    with fresh_session(engine) as s:
        reloaded = s.get(Course, course.id)
        assert reloaded is not None
        assert [u.order_index for u in reloaded.units] == [0, 1, 2]
        exercises = reloaded.units[0].skills[0].lessons[0].exercises
        assert [e.order_index for e in exercises] == [0, 1, 3, 5]


def test_duplicate_exercise_position_in_same_lesson_is_rejected(db: Session) -> None:
    lesson = first_lesson(make_course_tree(db))
    db.add(make_exercise(0, ExerciseType.MATCHING_PAIRS, lesson=lesson))
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed: exercises.lesson_id"):
        db.flush()


def test_same_position_is_allowed_in_different_parents(db: Session) -> None:
    course = make_course_tree(db)
    skill = course.units[0].skills[0]
    second = Lesson(skill=skill, order_index=1, title="Greetings 2")
    second.exercises = [make_exercise(0, ExerciseType.MULTIPLE_CHOICE)]
    db.add(second)
    db.flush()  # exercise order_index 0 exists in both lessons: fine
    assert [lesson.order_index for lesson in skill.lessons] == [0, 1]


def test_duplicate_content_slugs_and_positions_are_rejected(db: Session) -> None:
    course = make_course_tree(db)
    db.add(Course(slug="es-en", title="Dup", learning_language="es", from_language="en"))
    with pytest.raises(IntegrityError, match="courses.slug"):
        db.flush()
    db.rollback()

    course = make_course_tree(db)
    db.add(Skill(unit=course.units[0], order_index=0, title="Clash"))
    with pytest.raises(IntegrityError, match="skills.unit_id, skills.order_index"):
        db.flush()


def test_all_five_exercise_types_are_supported(db: Session, engine: Engine) -> None:
    lesson = first_lesson(make_course_tree(db))
    samples = {
        ExerciseType.MULTIPLE_CHOICE: (
            {"options": [{"id": "a", "text": "el gato"}]},
            {"correct_option_id": "a"},
        ),
        ExerciseType.WORD_BANK: (
            {"source_text": "The cat", "tiles": [{"id": "t1", "text": "el"}]},
            {"accepted": [["el", "gato"]]},
        ),
        ExerciseType.MATCHING_PAIRS: (
            {"left": [{"id": "l1", "text": "cat"}], "right": [{"id": "r1", "text": "gato"}]},
            {"pairs": [["l1", "r1"]]},
        ),
        ExerciseType.FILL_BLANK: (
            {"before": "Yo ", "after": " agua.", "options": [{"id": "a", "text": "bebo"}]},
            {"correct_option_id": "a"},
        ),
        ExerciseType.TYPE_ANSWER: (
            {"placeholder": "Type in Spanish"},
            {"accepted": ["el gato bebe agua"]},
        ),
    }
    for offset, (type_, (payload, solution)) in enumerate(samples.items(), start=10):
        db.add(make_exercise(offset, type_, lesson=lesson, payload=payload, solution=solution))
    db.commit()

    with fresh_session(engine) as s:
        stored = s.scalars(select(Exercise).where(Exercise.order_index >= 10)).all()
        assert {e.type for e in stored} == set(ExerciseType)
        by_type = {e.type: e for e in stored}
        pairs = by_type[ExerciseType.MATCHING_PAIRS]
        # payload and solution are separate columns and round-trip as JSON objects
        assert pairs.payload["right"] == [{"id": "r1", "text": "gato"}]
        assert pairs.solution == {"pairs": [["l1", "r1"]]}
        assert "pairs" not in pairs.payload


@pytest.mark.parametrize(
    ("column", "bad_value", "constraint"),
    [
        ("type", "'essay'", "ck_exercises_exercise_type"),
        ("payload", "'[1, 2]'", "ck_exercises_payload_is_object"),
        ("solution", "'not json'", "ck_exercises_solution_is_object"),
        ("prompt", "'   '", "ck_exercises_prompt_not_blank"),
    ],
)
def test_exercise_checks_are_enforced_by_the_database(
    db: Session, column: str, bad_value: str, constraint: str
) -> None:
    lesson = first_lesson(make_course_tree(db))
    values = {
        "type": "'multiple_choice'",
        "payload": "'{}'",
        "solution": "'{}'",
        "prompt": "'Pick one'",
        column: bad_value,
    }
    sql = (
        "INSERT INTO exercises (lesson_id, order_index, type, prompt, payload, solution) "
        f"VALUES ({lesson.id}, 9, {values['type']}, {values['prompt']}, "
        f"{values['payload']}, {values['solution']})"
    )
    with pytest.raises(IntegrityError, match=constraint):
        db.execute(text(sql))


def test_foreign_keys_are_enforced(db: Session) -> None:
    assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    db.add(Unit(course_id=999, order_index=0, title="Orphan"))
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()
    db.rollback()

    user = make_user(db)
    db.add(
        LessonCompletion(
            first_completed_at=NOW,
            last_completed_at=NOW,
            user=user,
            lesson_id=12345,
            best_mistakes=0,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


def test_deleting_a_course_cascades_through_its_content(db: Session) -> None:
    course = make_course_tree(db)
    db.commit()
    db.delete(course)
    db.commit()
    for model in (Unit, Skill, Lesson, Exercise):
        assert db.scalars(select(model)).all() == []


def test_content_with_learner_history_cannot_be_deleted(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    db.add(
        LessonCompletion(
            first_completed_at=NOW,
            last_completed_at=NOW,
            user=user,
            lesson=first_lesson(course),
            best_mistakes=0,
        )
    )
    db.commit()

    # RESTRICT: learner progress protects the lesson (and therefore the whole course).
    # Raw SQL, so the database itself (not the ORM) must refuse. RESTRICT is checked
    # immediately, at the DELETE statement, not deferred to commit.
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute(text("DELETE FROM lessons"))
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Lesson)) == 1


# --------------------------------------------------------------------------- users


def test_new_user_gets_game_defaults(db: Session) -> None:
    user = make_user(db)
    assert (user.hearts, user.gems, user.xp_total) == (5, 500, 0)
    assert (user.streak_count, user.longest_streak, user.last_streak_date) == (0, 0, None)
    assert user.daily_goal_xp == 20
    assert user.timezone == "Asia/Kolkata"
    assert user.hearts_updated_at.tzinfo is not None
    assert user.version == 1  # optimistic-lock counter


def test_user_updates_bump_the_version_and_detect_stale_writes(engine: Engine) -> None:
    from sqlalchemy.orm.exc import StaleDataError

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup:
        setup.add(User(username="v", display_name="V"))
        setup.commit()
    with factory() as first, factory() as second:
        mine = first.scalars(select(User).where(User.username == "v")).one()
        theirs = second.scalars(select(User).where(User.username == "v")).one()
        theirs.gems -= 100
        second.commit()  # version 1 -> 2
        assert theirs.version == 2
        mine.gems -= 50  # based on a stale read of version 1
        with pytest.raises(StaleDataError):
            first.commit()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("hearts", 6, "ck_users_hearts_range"),
        ("hearts", -1, "ck_users_hearts_range"),
        ("gems", -5, "ck_users_gems_non_negative"),
        ("xp_total", -1, "ck_users_xp_total_non_negative"),
        ("daily_goal_xp", 15, "ck_users_daily_goal_option"),
        ("streak_count", 3, "ck_users_longest_streak_covers_current"),
        ("streak_count", -1, "ck_users_streak_non_negative"),
        ("longest_streak", -1, "ck_users_longest_streak_non_negative"),
    ],
)
def test_user_counter_constraints(db: Session, field: str, value: int, constraint: str) -> None:
    user = make_user(db)
    setattr(user, field, value)
    with pytest.raises(IntegrityError, match=constraint):
        db.flush()


def test_duplicate_username_is_rejected(db: Session) -> None:
    make_user(db, "ana")
    db.add(User(username="ana", display_name="Other Ana"))
    with pytest.raises(IntegrityError, match="users.username"):
        db.flush()


# --------------------------------------------------------------------------- sessions


def test_user_has_sessions_with_uuid_ids_and_can_resume(db: Session, engine: Engine) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    session = start_session(db, user, first_lesson(course))
    db.commit()

    assert len(session.id) == 36 and session.id.count("-") == 4
    assert session.status is SessionStatus.ACTIVE and session.ended_at is None

    with fresh_session(engine) as s:
        # "Resume": the user's active session, looked up by the (user_id, status) index.
        active = s.scalars(
            select(LessonSession).where(
                LessonSession.user_id == user.id, LessonSession.status == SessionStatus.ACTIVE
            )
        ).one()
        assert active.id == session.id
        assert active.user.username == "learner"  # LessonSession -> User
        assert active.exercise_ids == [e.id for e in first_lesson(course).exercises]
        reloaded_user = s.get(User, user.id)
        assert reloaded_user is not None
        assert [x.id for x in reloaded_user.sessions] == [session.id]  # User -> LessonSession


def test_session_answers_are_recorded_in_order(db: Session, engine: Engine) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    lesson = first_lesson(course)
    session = start_session(db, user, lesson)
    first, second = lesson.exercises
    session.answers.extend(
        [
            SessionAnswer(exercise=first, submitted={"option_id": "b"}, is_correct=False),
            SessionAnswer(exercise=second, submitted={"text": "hola"}, is_correct=True),
        ]
    )
    db.commit()

    with fresh_session(engine) as s:
        reloaded = s.get(LessonSession, session.id)
        assert reloaded is not None
        assert [(a.exercise_id, a.is_correct) for a in reloaded.answers] == [
            (first.id, False),
            (second.id, True),
        ]
        assert reloaded.answers[0].submitted == {"option_id": "b"}
        assert all(a.session is reloaded for a in reloaded.answers)


def test_an_exercise_is_graded_at_most_once_per_session(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    lesson = first_lesson(course)
    session = start_session(db, user, lesson)
    first = lesson.exercises[0]
    session.answers.append(SessionAnswer(exercise=first, submitted={"x": 1}, is_correct=False))
    db.flush()
    db.add(SessionAnswer(session=session, exercise=first, submitted={"x": 2}, is_correct=True))
    with pytest.raises(
        IntegrityError,
        match="UNIQUE constraint failed: session_answers.session_id, session_answers.exercise_id",
    ):
        db.flush()
    db.rollback()
    # ...but the same exercise may appear in another session (e.g. a replay).
    other = start_session(db, make_user(db, "other"), lesson)
    other.answers.append(SessionAnswer(exercise=first, submitted={"x": 1}, is_correct=True))
    db.flush()


def test_only_one_active_session_per_user(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    lesson = first_lesson(course)
    first = start_session(db, user, lesson)
    db.commit()

    with pytest.raises(IntegrityError, match="lesson_sessions.user_id"):
        start_session(db, user, lesson)
    db.rollback()

    first.status = SessionStatus.ABANDONED
    first.ended_at = datetime.now(UTC)
    db.flush()
    start_session(db, user, lesson)  # allowed once the previous one has ended
    other = make_user(db, "rival")
    start_session(db, other, lesson)  # other users are independent


@pytest.mark.parametrize(
    ("mode", "with_lesson", "with_skill"),
    [
        (SessionMode.LESSON, False, False),  # lesson mode needs a lesson
        (SessionMode.LESSON, True, True),  # ...and no skill
        (SessionMode.PRACTICE, True, False),  # practice never targets a lesson
    ],
)
def test_session_target_must_match_mode(
    db: Session, mode: SessionMode, with_lesson: bool, with_skill: bool
) -> None:
    course = make_course_tree(db)
    lesson = first_lesson(course)
    db.add(
        LessonSession(
            user=make_user(db),
            mode=mode,
            lesson=lesson if with_lesson else None,
            skill=lesson.skill if with_skill else None,
            exercise_ids=[],
        )
    )
    with pytest.raises(IntegrityError, match="ck_lesson_sessions_target_matches_mode"):
        db.flush()


def test_practice_session_may_target_a_skill_or_the_whole_course(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    skill = course.units[0].skills[0]
    db.add(LessonSession(user=user, mode=SessionMode.PRACTICE, skill=skill, exercise_ids=[1]))
    db.flush()


def test_ended_at_must_match_status(db: Session) -> None:
    course = make_course_tree(db)
    session = start_session(db, make_user(db), first_lesson(course))
    session.status = SessionStatus.COMPLETED  # but ended_at left empty
    with pytest.raises(IntegrityError, match="ck_lesson_sessions_ended_at_matches_status"):
        db.flush()


# --------------------------------------------------------------------------- completions


def test_user_lesson_completion_relationship(db: Session, engine: Engine) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    db.add(
        LessonCompletion(
            first_completed_at=NOW,
            last_completed_at=NOW,
            user=user,
            lesson=first_lesson(course),
            best_mistakes=1,
        )
    )
    db.commit()

    with fresh_session(engine) as s:
        reloaded = s.get(User, user.id)
        assert reloaded is not None
        [completion] = reloaded.completions
        assert completion.lesson.title == "Greetings 1"
        assert completion.times_completed == 1
        assert completion.first_completed_at == completion.last_completed_at


def test_duplicate_completion_is_rejected(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    lesson = first_lesson(course)
    db.add(
        LessonCompletion(
            first_completed_at=NOW, last_completed_at=NOW, user=user, lesson=lesson, best_mistakes=0
        )
    )
    db.flush()
    db.add(
        LessonCompletion(
            first_completed_at=NOW, last_completed_at=NOW, user=user, lesson=lesson, best_mistakes=0
        )
    )
    with pytest.raises(
        IntegrityError,
        match="UNIQUE constraint failed: lesson_completions.user_id, lesson_completions.lesson_id",
    ):
        db.flush()


def test_replay_updates_the_existing_completion(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    completion = LessonCompletion(
        first_completed_at=NOW,
        last_completed_at=NOW,
        user=user,
        lesson=first_lesson(course),
        best_mistakes=2,
    )
    db.add(completion)
    db.flush()
    completion.times_completed += 1
    completion.best_mistakes = 0
    completion.last_completed_at = completion.first_completed_at + timedelta(days=1)
    db.flush()
    assert db.scalars(select(LessonCompletion)).one().times_completed == 2


# --------------------------------------------------------------------------- XP ledger


def test_xp_event_is_persisted(db: Session, engine: Engine) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    session = start_session(db, user, first_lesson(course))
    db.add(XpEvent(user=user, amount=15, source=XpSource.LESSON, session=session, local_date=TODAY))
    user.xp_total += 15
    db.commit()

    with fresh_session(engine) as s:
        event = s.scalars(select(XpEvent)).one()
        assert (event.amount, event.source, event.local_date) == (15, XpSource.LESSON, TODAY)
        assert event.session_id == session.id
        assert event.created_at.tzinfo == UTC
        reloaded = s.get(User, user.id)
        assert reloaded is not None
        assert reloaded.xp_total == 15
        assert [e.amount for e in reloaded.xp_events] == [15]


def test_a_session_cannot_award_xp_twice(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    session = start_session(db, user, first_lesson(course))
    db.add(XpEvent(user=user, amount=10, source=XpSource.LESSON, session=session, local_date=TODAY))
    db.flush()
    db.add(XpEvent(user=user, amount=10, source=XpSource.LESSON, session=session, local_date=TODAY))
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed: xp_events.session_id"):
        db.flush()


def test_sessionless_bonus_events_are_allowed_and_amount_must_be_positive(db: Session) -> None:
    user = make_user(db)
    db.add_all(
        [XpEvent(user=user, amount=5, source=XpSource.BONUS, local_date=TODAY) for _ in range(2)]
    )
    db.flush()  # several NULL session_ids are fine
    db.add(XpEvent(user=user, amount=0, source=XpSource.BONUS, local_date=TODAY))
    with pytest.raises(IntegrityError, match="ck_xp_events_amount_positive"):
        db.flush()


# --------------------------------------------------------------------------- achievements


def test_achievement_unlocks_once_per_user(db: Session) -> None:
    user = make_user(db)
    badge = Achievement(
        code="wildfire_1",
        title="Wildfire",
        description="Reach a 3 day streak",
        icon="flame",
        metric=AchievementMetric.STREAK,
        threshold=3,
    )
    db.add_all([badge, UserAchievement(user=user, achievement=badge)])
    db.flush()
    assert [ua.achievement.code for ua in user.achievements] == ["wildfire_1"]

    db.expunge_all()  # forget the loaded row so the duplicate reaches the database
    db.add(UserAchievement(user_id=user.id, achievement_id=badge.id))
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed: user_achievements"):
        db.flush()


# --------------------------------------------------------------------------- delete rules


def test_deleting_a_user_removes_learner_state_but_not_content(db: Session) -> None:
    course = make_course_tree(db)
    user = make_user(db)
    lesson = first_lesson(course)
    session = start_session(db, user, lesson)
    session.answers.append(
        SessionAnswer(exercise=lesson.exercises[0], submitted={"option_id": "a"}, is_correct=True)
    )
    db.add_all(
        [
            LessonCompletion(
                first_completed_at=NOW,
                last_completed_at=NOW,
                user=user,
                lesson=lesson,
                best_mistakes=0,
            ),
            XpEvent(
                user=user, amount=10, source=XpSource.LESSON, session=session, local_date=TODAY
            ),
        ]
    )
    db.commit()

    db.delete(user)
    db.commit()

    for model in (LessonSession, SessionAnswer, LessonCompletion, XpEvent, UserAchievement):
        assert db.scalars(select(model)).all() == [], model.__name__
    assert len(db.scalars(select(Exercise)).all()) == 2  # content untouched


# --------------------------------------------------------------------------- UTC timestamps


def test_timestamps_are_stored_and_returned_as_utc(db: Session, engine: Engine) -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    user = make_user(db)
    user.hearts_updated_at = datetime(2026, 9, 25, 19, 30, tzinfo=ist)
    db.commit()

    raw: str = db.execute(text("SELECT hearts_updated_at FROM users")).scalar_one()
    assert str(raw).startswith("2026-09-25 14:00:00")  # stored as UTC

    with fresh_session(engine) as s:
        reloaded = s.get(User, user.id)
        assert reloaded is not None
        assert reloaded.hearts_updated_at == datetime(2026, 9, 25, 14, 0, tzinfo=UTC)
        assert reloaded.hearts_updated_at.tzinfo == UTC


def test_naive_datetimes_are_rejected(db: Session) -> None:
    user = make_user(db)
    user.hearts_updated_at = datetime(2026, 9, 25, 12, 0)  # no tzinfo
    with pytest.raises(StatementError, match="Naive datetime"):
        db.flush()
