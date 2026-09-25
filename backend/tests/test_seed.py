"""Seed tests: content shape, answer secrecy, learner/bot state and determinism."""

import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.seed import seed_database
from app.db.seed.__main__ import main as seed_cli
from app.db.session import create_db_engine
from app.models import (
    Achievement,
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    LessonCompletion,
    LessonSession,
    SessionMode,
    SessionStatus,
    Skill,
    Unit,
    User,
    UserAchievement,
    XpEvent,
)
from app.schemas.exercises import validate_exercise
from tests.conftest import SEED_DAY

REFERENCE_DAY = SEED_DAY

EXPECTED_SKILLS = {
    "Basics": ["Greetings", "Introductions", "Basic Words"],
    "Food and Drink": ["Food and Drinks", "Ordering Food", "Preferences"],
    "Everyday Life": ["Family", "Everyday Activities", "Time and Routine"],
}
LESSONS_PER_SKILL = [3, 3, 2, 3, 2, 2, 3, 2, 2]
TOTAL_EXERCISES = 117

# Keys that would indicate an answer leaking into a browser-facing payload.
SOLUTION_KEYS = {"correct_option_id", "accepted", "pairs", "answer", "solution", "correct"}


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of every table, ordered by primary key: the 'logical dataset'."""
    with engine.connect() as conn:
        dump = {}
        for table in Base.metadata.sorted_tables:
            order = ", ".join(column.name for column in table.primary_key.columns)
            rows = conn.execute(text(f"SELECT * FROM {table.name} ORDER BY {order}"))
            dump[table.name] = [tuple(row) for row in rows]
    return dump


@contextmanager
def fresh_engine(tmp_path: Path, name: str) -> Iterator[Engine]:
    engine = create_db_engine(f"sqlite:///{tmp_path / name}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def seed_into(engine: Engine, reference_day: date = REFERENCE_DAY, *, reset: bool = False) -> bool:
    with sessionmaker(bind=engine)() as db, db.begin():
        return seed_database(db, reference_day, reset=reset).skipped


# --------------------------------------------------------------------------- course


def test_seed_creates_one_spanish_course(seeded: Session) -> None:
    course = seeded.scalars(select(Course)).one()
    assert (course.learning_language, course.from_language) == ("es", "en")
    assert course.title == "Spanish"


def test_units_and_skills_in_order(seeded: Session) -> None:
    course = seeded.scalars(select(Course)).one()
    assert {unit.title: [skill.title for skill in unit.skills] for unit in course.units} == (
        EXPECTED_SKILLS
    )
    assert [unit.title for unit in course.units] == list(EXPECTED_SKILLS)
    assert seeded.scalar(select(func.count()).select_from(Unit)) == 3
    assert seeded.scalar(select(func.count()).select_from(Skill)) == 9


def test_lessons_per_skill(seeded: Session) -> None:
    skills = seeded.scalars(select(Skill).order_by(Skill.id)).all()
    assert [len(skill.lessons) for skill in skills] == LESSONS_PER_SKILL
    assert seeded.scalar(select(func.count()).select_from(Lesson)) == 22


def test_exercise_volume_and_lesson_size(seeded: Session) -> None:
    exercises = seeded.scalars(select(Exercise)).all()
    assert len(exercises) == TOTAL_EXERCISES
    assert 80 <= len(exercises) <= 120
    for lesson in seeded.scalars(select(Lesson)).all():
        assert 5 <= len(lesson.exercises) <= 6, lesson.title
        assert len({exercise.type for exercise in lesson.exercises}) >= 4, lesson.title


def test_all_five_exercise_types_appear_many_times(seeded: Session) -> None:
    counts = Counter(seeded.scalars(select(Exercise.type)).all())
    assert set(counts) == set(ExerciseType)
    assert all(count >= 15 for count in counts.values()), counts


def test_lessons_are_not_identical(seeded: Session) -> None:
    lessons = seeded.scalars(select(Lesson)).all()
    type_sequences = {tuple(e.type for e in lesson.exercises) for lesson in lessons}
    assert len(type_sequences) >= 15  # 22 lessons, varied type mixes and orders
    prompts = seeded.scalars(select(Exercise.prompt)).all()
    assert not any(p.lower().startswith("question") for p in prompts)


def test_every_exercise_has_a_valid_payload_and_server_side_solution(seeded: Session) -> None:
    for exercise in seeded.scalars(select(Exercise)).all():
        validate_exercise(exercise.type, exercise.payload, exercise.solution)
        assert exercise.solution, exercise.id
        assert exercise.prompt.strip()


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def test_no_solution_is_included_in_any_payload(seeded: Session) -> None:
    for exercise in seeded.scalars(select(Exercise)).all():
        payload, solution = exercise.payload, exercise.solution
        assert not _keys(payload) & SOLUTION_KEYS, exercise.id
        dumped = json.dumps(payload, ensure_ascii=False).casefold()
        match exercise.type:
            case ExerciseType.TYPE_ANSWER:
                for answer in solution["accepted"]:
                    assert answer.casefold() not in dumped, exercise.id
            case ExerciseType.WORD_BANK:
                tiles = [tile["text"] for tile in payload["tiles"]]
                answer = solution["accepted"][0]
                assert tiles[: len(answer)] != answer, exercise.id  # tiles are shuffled
            case ExerciseType.MATCHING_PAIRS:
                n = len(payload["left"])
                assert solution["pairs"] != [[f"l{i}", f"r{i}"] for i in range(1, n + 1)]


def test_correct_option_position_carries_no_signal(seeded: Session) -> None:
    for type_ in (ExerciseType.MULTIPLE_CHOICE, ExerciseType.FILL_BLANK):
        positions: Counter[int] = Counter()
        exercises = seeded.scalars(select(Exercise).where(Exercise.type == type_)).all()
        for exercise in exercises:
            ids = [option["id"] for option in exercise.payload["options"]]
            positions[ids.index(exercise.solution["correct_option_id"])] += 1
        assert len(positions) >= 3, (type_, positions)
        assert max(positions.values()) <= 0.6 * len(exercises), (type_, positions)


def test_exercise_ids_and_order_are_deterministic(seeded: Session) -> None:
    rows = seeded.execute(
        select(Exercise.id, Exercise.lesson_id, Exercise.order_index).order_by(Exercise.id)
    ).all()
    assert [row.id for row in rows] == list(range(1, TOTAL_EXERCISES + 1))
    # ids follow course order: (lesson, position) pairs are already sorted by id
    assert [(r.lesson_id, r.order_index) for r in rows] == sorted(
        (r.lesson_id, r.order_index) for r in rows
    )
    first = seeded.get(Exercise, 1)
    assert first is not None and first.type is ExerciseType.MULTIPLE_CHOICE
    assert first.prompt == "Which one means “hello”?"


# --------------------------------------------------------------------------- learner


def learner(db: Session) -> User:
    return db.scalars(select(User).where(User.username == "learner")).one()


def test_default_learner_exists(seeded: Session) -> None:
    user = learner(seeded)
    assert user.id == 1 and not user.is_bot
    assert user.timezone == "Asia/Kolkata"
    assert user.current_course is not None and user.current_course.slug == "es-from-en"
    assert user.daily_goal_xp == 20


def test_learner_has_partial_believable_progress(seeded: Session) -> None:
    user = learner(seeded)
    assert user.xp_total == 80  # 8 completed sessions x 10 XP
    assert user.xp_total == sum(event.amount for event in user.xp_events)
    assert (user.streak_count, user.longest_streak) == (6, 6)
    assert user.last_streak_date == REFERENCE_DAY - timedelta(days=1)
    assert user.hearts == 5  # overnight regeneration: the demo starts with full hearts
    assert user.gems == 1500
    assert len(user.completions) == 7

    sessions = user.sessions
    assert len(sessions) == 8
    assert all(s.status is SessionStatus.COMPLETED and s.ended_at for s in sessions)
    assert Counter(s.mode for s in sessions) == {SessionMode.LESSON: 7, SessionMode.PRACTICE: 1}
    assert all(event.session_id is not None for event in user.xp_events)  # ledger -> sessions
    # activity on each of the last 6 days = the 6-day streak
    days = {event.local_date for event in user.xp_events}
    assert days == {REFERENCE_DAY - timedelta(days=k) for k in range(1, 7)}


def test_learner_achievements_mix_unlocked_and_locked(seeded: Session) -> None:
    unlocked = {ua.achievement.code for ua in learner(seeded).achievements}
    assert unlocked == {"scholar_1", "scholar_2", "conqueror_1", "wildfire_1"}
    assert seeded.scalar(select(func.count()).select_from(Achievement)) == 15
    assert "sharpshooter_1" not in unlocked  # 4 of 5 perfect lessons: next to unlock


def test_path_shows_completed_active_and_locked_skills(seeded: Session) -> None:
    """Test-only check of the *data*: unlock rules themselves are tested in test_path_rules.py."""
    completed_lessons = set(
        seeded.scalars(
            select(LessonCompletion.lesson_id).where(LessonCompletion.user_id == 1)
        ).all()
    )
    skills = seeded.scalars(select(Skill).join(Unit).order_by(Unit.order_index, Skill.order_index))
    progress = [
        (sum(lesson.id in completed_lessons for lesson in skill.lessons), len(skill.lessons))
        for skill in skills
    ]
    assert progress[:3] == [(3, 3), (3, 3), (1, 2)]  # two done, one in progress
    assert all(done == 0 for done, _ in progress[3:])  # six untouched -> locked
    assert progress[3:] and len(progress) == 9


# --------------------------------------------------------------------------- leaderboard


def test_leaderboard_bots(seeded: Session) -> None:
    bots = seeded.scalars(select(User).where(User.is_bot.is_(True)).order_by(User.id)).all()
    assert len(bots) == 9
    assert len({bot.username for bot in bots}) == 9
    assert all("." in bot.username or "_" in bot.username for bot in bots)

    week_start = REFERENCE_DAY - timedelta(days=6)
    weekly = dict(
        seeded.execute(
            select(User.username, func.sum(XpEvent.amount))
            .join(XpEvent)
            .where(XpEvent.local_date >= week_start)
            .group_by(User.username)
        ).all()
    )
    assert len(set(weekly.values())) == len(weekly) == 10  # no ties
    ranking = sorted(weekly, key=weekly.__getitem__, reverse=True)
    assert ranking[0] == "maria.garcia"
    assert 2 <= ranking.index("learner") + 1 <= 9  # mid-table, not first or last


def test_every_user_ledger_matches_stored_counters(seeded: Session) -> None:
    for user in seeded.scalars(select(User)).all():
        assert user.xp_total == sum(e.amount for e in user.xp_events), user.username
        latest = max(e.local_date for e in user.xp_events)
        assert user.last_streak_date == latest, user.username
        # stored streak == unbroken run of active days ending at last_streak_date
        days = {e.local_date for e in user.xp_events}
        run, day = 0, latest
        while day in days:
            run, day = run + 1, day - timedelta(days=1)
        assert user.streak_count == run, user.username
        assert user.longest_streak >= user.streak_count >= 0


# --------------------------------------------------------------------------- determinism


def test_seeding_twice_is_a_no_op(tmp_path: Path) -> None:
    with fresh_engine(tmp_path, "twice.db") as engine:
        assert seed_into(engine) is False
        before = snapshot(engine)
        assert seed_into(engine) is True  # skipped: already seeded
        assert snapshot(engine) == before


def test_two_fresh_databases_are_identical(tmp_path: Path) -> None:
    with fresh_engine(tmp_path, "a.db") as first:
        with fresh_engine(tmp_path, "b.db") as second:
            seed_into(first)
            seed_into(second)
            assert snapshot(first) == snapshot(second)


def test_reset_then_seed_reproduces_the_same_dataset(tmp_path: Path) -> None:
    with fresh_engine(tmp_path, "reset.db") as engine:
        seed_into(engine)
        original = snapshot(engine)
        with sessionmaker(bind=engine)() as db, db.begin():  # simulate learner activity
            db.execute(text("UPDATE users SET hearts = 0, gems = 1 WHERE username = 'learner'"))
            db.execute(text("DELETE FROM lesson_completions WHERE id = 1"))
        assert snapshot(engine) != original
        assert seed_into(engine, reset=True) is False
        assert snapshot(engine) == original


def test_reference_day_moves_learner_dates_but_not_content(tmp_path: Path) -> None:
    with fresh_engine(tmp_path, "today.db") as today:
        with fresh_engine(tmp_path, "later.db") as later:
            seed_into(today)
            seed_into(later, REFERENCE_DAY + timedelta(days=30))
            a, b = snapshot(today), snapshot(later)
            for table in ("courses", "units", "skills", "lessons", "exercises", "achievements"):
                assert a[table] == b[table], table
            assert a["xp_events"] != b["xp_events"]  # dates shift with the reference day


def test_seed_cli_seed_skip_and_reset(capsys: pytest.CaptureFixture[str]) -> None:
    # The CLI uses the app's global engine, which conftest points at a temp file.
    assert seed_cli(["--reset", "--today", "2026-09-25"]) == 0
    assert "Reset and seeded" in capsys.readouterr().out
    assert seed_cli(["--today", "2026-09-25"]) == 0
    assert "already seeded" in capsys.readouterr().out
    assert seed_cli(["--reset", "--today", "2026-09-25"]) == 0
    out = capsys.readouterr().out
    assert "exercises" in out and "117" in out


def test_seeded_rows_satisfy_every_constraint(seeded: Session) -> None:
    assert seeded.execute(text("PRAGMA foreign_key_check")).all() == []
    assert seeded.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
    assert seeded.scalar(select(func.count()).select_from(UserAchievement)) == 4
    assert seeded.scalar(select(func.count()).select_from(LessonSession)) == 8
