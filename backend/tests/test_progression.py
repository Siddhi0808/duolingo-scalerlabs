"""XP, streak, daily goal and achievements applied by the lesson engine (service level).

All times are explicit so the tests do not depend on when they run. The seed's
reference day is 2026-09-25; the learner (Asia/Kolkata) has 80 XP, a 6-day streak
last extended on the 24th, and lessons 1-7 completed. The `learner` fixture gives
them 3 hearts as of NOON_IST.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    Exercise,
    LessonCompletion,
    LessonSession,
    User,
    UserAchievement,
    XpEvent,
    XpSource,
)
from app.schemas.lesson import AnswerRequest, AnswerResult
from app.services import achievement_service, lesson_service, profile_service, xp_service
from tests.factories import set_hearts
from tests.lesson_helpers import right_answer, wrong_answer

NOON_IST = datetime(2026, 9, 25, 6, 30, tzinfo=UTC)  # 12:00 on the 25th in Kolkata
TODAY = date(2026, 9, 25)
NEXT_LESSON, AFTER_NEXT = 8, 9  # lesson 9 unlocks once lesson 8 completes skill 3


@pytest.fixture
def learner(seeded: Session) -> User:
    return set_hearts(seeded, "learner", 3, NOON_IST)


@pytest.fixture
def newbie(seeded: Session) -> User:
    user = User(username="newbie", display_name="Newbie", current_course_id=1)
    seeded.add(user)
    seeded.commit()
    return user


def play(
    db: Session, user: User, lesson_id: int, now: datetime, *, wrong: int = 0
) -> tuple[str, AnswerResult]:
    """Play a whole lesson, answering the first `wrong` exercises wrongly."""
    started = lesson_service.start_lesson(db, user, lesson_id, now=now)
    result: AnswerResult | None = None
    for index in range(started.progress.total):
        current = lesson_service.get_current_exercise(db, user, started.session_id)
        exercise = db.get(Exercise, current.id)
        assert exercise is not None
        body: dict[str, Any] = {
            "exercise_id": exercise.id,
            "answer": wrong_answer(exercise) if index < wrong else right_answer(exercise),
        }
        result = lesson_service.submit_answer(
            db, user, started.session_id, AnswerRequest.model_validate(body), now=now
        )
        if result.progress.status.value != "active":
            break
    assert result is not None
    return started.session_id, result


def xp_events(db: Session, user: User) -> list[XpEvent]:
    return list(db.scalars(select(XpEvent).where(XpEvent.user_id == user.id)))


def codes(db: Session, user: User) -> set[str]:
    rows = db.scalars(
        select(Achievement.code).join(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    return set(rows)


# --------------------------------------------------------------------------- XP


def test_successful_lesson_awards_exactly_10_xp(seeded: Session, learner: User) -> None:
    before = len(xp_events(seeded, learner))
    session_id, result = play(seeded, learner, NEXT_LESSON, NOON_IST)
    assert result.rewards is not None
    assert (result.rewards.xp_awarded, result.rewards.xp_total) == (10, 90)
    assert result.rewards.first_completion
    seeded.refresh(learner)
    assert learner.xp_total == 90
    event = seeded.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).one()
    assert (event.amount, event.source, event.local_date) == (10, XpSource.LESSON, TODAY)
    assert event.created_at == NOON_IST
    assert len(xp_events(seeded, learner)) == before + 1
    session = seeded.get(LessonSession, session_id)
    assert session is not None and session.xp_awarded == 10


def test_failed_lesson_awards_nothing(seeded: Session, learner: User) -> None:
    session_id, result = play(seeded, learner, NEXT_LESSON, NOON_IST, wrong=3)
    assert result.progress.status.value == "failed" and result.rewards is None
    seeded.refresh(learner)
    assert learner.xp_total == 80
    assert (learner.streak_count, learner.last_streak_date) == (6, TODAY - timedelta(days=1))
    assert seeded.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).all() == []
    assert (
        seeded.scalars(
            select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
        ).all()
        == []
    )


def test_replaying_a_completed_lesson_awards_no_xp(seeded: Session, learner: User) -> None:
    session_id, result = play(seeded, learner, 1, NOON_IST)  # lesson 1: completed in seed
    assert result.rewards is not None
    assert not result.rewards.first_completion and result.rewards.xp_awarded == 0
    assert not result.rewards.streak.extended  # no XP -> not a streak day
    seeded.refresh(learner)
    assert (learner.xp_total, learner.streak_count) == (80, 6)
    assert seeded.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).all() == []
    completion = seeded.scalars(select(LessonCompletion).where(LessonCompletion.lesson_id == 1))
    assert completion.one().times_completed == 2


def test_replayed_final_answer_awards_nothing_more(seeded: Session, learner: User) -> None:
    session_id, original = play(seeded, learner, NEXT_LESSON, NOON_IST)
    session = seeded.get(LessonSession, session_id)
    assert session is not None
    last = seeded.get(Exercise, session.exercise_ids[-1])
    assert last is not None
    body = AnswerRequest.model_validate({"exercise_id": last.id, "answer": right_answer(last)})
    later = NOON_IST + timedelta(days=1)  # even a day later: still nothing new
    replay = lesson_service.submit_answer(seeded, learner, session_id, body, now=later)
    assert replay.replayed and replay.rewards == original.rewards
    seeded.refresh(learner)
    assert (learner.xp_total, learner.streak_count, learner.last_streak_date) == (90, 7, TODAY)
    assert len(seeded.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).all()) == 1


def test_a_second_xp_event_for_a_session_is_impossible(seeded: Session, learner: User) -> None:
    session_id, _ = play(seeded, learner, NEXT_LESSON, NOON_IST)
    session = seeded.get(LessonSession, session_id)
    assert session is not None
    with pytest.raises(IntegrityError, match="xp_events.session_id"):
        xp_service.award_xp(seeded, learner, 10, XpSource.LESSON, NOON_IST, session=session)
    seeded.rollback()
    seeded.refresh(learner)
    assert learner.xp_total == 90  # the failed attempt's increment was rolled back


def test_xp_awards_must_be_positive(seeded: Session, learner: User) -> None:
    with pytest.raises(ValueError, match="positive"):
        xp_service.award_xp(seeded, learner, 0, XpSource.BONUS, NOON_IST)


# --------------------------------------------------------------------------- streak


def test_completion_extends_the_streak_on_the_next_local_day(
    seeded: Session, learner: User
) -> None:
    _, result = play(seeded, learner, NEXT_LESSON, NOON_IST)
    assert result.rewards is not None
    streak = result.rewards.streak
    assert (streak.before, streak.after, streak.longest, streak.extended) == (6, 7, 7, True)
    seeded.refresh(learner)
    assert (learner.streak_count, learner.longest_streak, learner.last_streak_date) == (
        7,
        7,
        TODAY,
    )


def test_several_lessons_on_one_day_count_once(seeded: Session, learner: User) -> None:
    play(seeded, learner, NEXT_LESSON, NOON_IST)
    _, second = play(seeded, learner, AFTER_NEXT, NOON_IST + timedelta(hours=5))
    assert second.rewards is not None
    assert (second.rewards.streak.after, second.rewards.streak.extended) == (7, False)
    assert second.rewards.xp_awarded == 10  # XP still earned


def test_streak_uses_the_learners_local_date_not_utc(seeded: Session, learner: User) -> None:
    # 19:00 UTC on the 24th is 00:30 on the 25th in Kolkata. The learner's last streak
    # day is the 24th, so this is the *next* local day and the streak grows. Judged by
    # UTC date (the 24th) it would wrongly look like the same day.
    just_after_midnight = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    session_id, result = play(seeded, learner, NEXT_LESSON, just_after_midnight)
    assert result.rewards is not None and result.rewards.streak.after == 7
    event = seeded.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).one()
    assert event.local_date == TODAY and event.created_at.date() == date(2026, 9, 24)


def test_missed_days_reset_the_streak(seeded: Session, learner: User) -> None:
    learner.last_streak_date = TODAY - timedelta(days=3)
    seeded.commit()
    _, result = play(seeded, learner, NEXT_LESSON, NOON_IST)
    assert result.rewards is not None
    assert (result.rewards.streak.before, result.rewards.streak.after) == (0, 1)
    assert result.rewards.streak.longest == 6


# --------------------------------------------------------------------------- daily goal


def test_daily_goal_progress(seeded: Session, learner: User) -> None:
    me = profile_service.build_me(seeded, learner, now=NOON_IST)
    assert (me.daily_goal.goal_xp, me.daily_goal.today_xp, me.daily_goal.completed) == (
        20,
        0,
        False,
    )
    assert me.xp_total == 80  # yesterday's seeded XP exists but does not count for today

    _, first = play(seeded, learner, NEXT_LESSON, NOON_IST)
    assert first.rewards is not None
    goal = first.rewards.daily_goal
    assert (goal.today_xp, goal.completed, goal.just_completed) == (10, False, False)

    _, second = play(seeded, learner, AFTER_NEXT, NOON_IST + timedelta(hours=1))
    assert second.rewards is not None
    goal = second.rewards.daily_goal
    assert (goal.today_xp, goal.completed, goal.just_completed) == (20, True, True)

    _, third = play(seeded, learner, 10, NOON_IST + timedelta(hours=2))
    assert third.rewards is not None
    goal = third.rewards.daily_goal
    assert (goal.today_xp, goal.completed, goal.just_completed) == (30, True, False)  # no cap

    me = profile_service.build_me(seeded, learner, now=NOON_IST + timedelta(hours=3))
    assert (me.daily_goal.today_xp, me.daily_goal.completed) == (30, True)
    tomorrow = profile_service.build_me(seeded, learner, now=NOON_IST + timedelta(days=1))
    assert (tomorrow.daily_goal.today_xp, tomorrow.daily_goal.completed) == (0, False)


def test_daily_xp_follows_the_learners_calendar(seeded: Session, learner: User) -> None:
    play(seeded, learner, NEXT_LESSON, datetime(2026, 9, 25, 18, 15, tzinfo=UTC))  # 23:45 IST
    play(seeded, learner, AFTER_NEXT, datetime(2026, 9, 25, 18, 45, tzinfo=UTC))  # 00:15 IST
    assert xp_service.xp_on_day(seeded, learner.id, date(2026, 9, 25)) == 10
    assert xp_service.xp_on_day(seeded, learner.id, date(2026, 9, 26)) == 10


# --------------------------------------------------------------------------- achievements


def test_first_lesson_achievement(seeded: Session, newbie: User) -> None:
    _, result = play(seeded, newbie, 1, NOON_IST)
    assert result.rewards is not None
    assert [a.code for a in result.rewards.new_achievements] == ["scholar_1"]
    assert codes(seeded, newbie) == {"scholar_1"}


def test_100_xp_achievement(seeded: Session, learner: User) -> None:
    _, first = play(seeded, learner, NEXT_LESSON, NOON_IST)  # 90 XP
    assert first.rewards is not None
    assert "sage_1" not in {a.code for a in first.rewards.new_achievements}
    _, second = play(seeded, learner, AFTER_NEXT, NOON_IST)  # 100 XP
    assert second.rewards is not None
    assert "sage_1" in {a.code for a in second.rewards.new_achievements}


def test_3_day_streak_achievement(seeded: Session, newbie: User) -> None:
    for day, lesson in enumerate((1, 2, 3)):
        _, result = play(seeded, newbie, lesson, NOON_IST + timedelta(days=day))
    assert result.rewards is not None and result.rewards.streak.after == 3
    assert "wildfire_1" in {a.code for a in result.rewards.new_achievements}


def test_7_day_streak_achievement(seeded: Session, learner: User) -> None:
    assert "wildfire_2" not in codes(seeded, learner)
    _, result = play(seeded, learner, NEXT_LESSON, NOON_IST)  # streak 6 -> 7
    assert result.rewards is not None
    # A perfect lesson 8 is also the learner's 5th perfect lesson -> Sharpshooter.
    assert [a.code for a in result.rewards.new_achievements] == ["wildfire_2", "sharpshooter_1"]


def test_imperfect_lesson_unlocks_only_the_streak_badge(seeded: Session, learner: User) -> None:
    _, result = play(seeded, learner, NEXT_LESSON, NOON_IST, wrong=1)
    assert result.rewards is not None
    assert [a.code for a in result.rewards.new_achievements] == ["wildfire_2"]


def test_achievements_are_never_duplicated(seeded: Session, learner: User) -> None:
    play(seeded, learner, NEXT_LESSON, NOON_IST)
    before = codes(seeded, learner)
    assert achievement_service.evaluate(seeded, learner, TODAY, NOON_IST) == []  # again
    play(seeded, learner, 1, NOON_IST)  # a replay also re-evaluates
    seeded.commit()
    total = select(func.count()).select_from(UserAchievement)
    count = seeded.scalar(total.where(UserAchievement.user_id == learner.id))
    assert codes(seeded, learner) == before and count == len(before)
    seeded.expunge_all()  # forget loaded rows so the duplicate reaches the database
    with pytest.raises(IntegrityError):  # and the primary key forbids it outright
        seeded.add(UserAchievement(user_id=learner.id, achievement_id=1, unlocked_at=NOON_IST))
        seeded.flush()


def test_seeded_learner_metrics(seeded: Session, learner: User) -> None:
    metrics = achievement_service.learner_metrics(seeded, learner, TODAY)
    assert {m.value: v for m, v in metrics.items()} == {
        "total_xp": 80,
        "streak": 6,
        "lessons_completed": 7,
        "perfect_lessons": 4,
        "skills_completed": 2,
    }
