"""Load the deterministic seed dataset into the database.

Determinism rules:
* Content, users and achievements get **explicit ids** (1, 2, 3... in authored order),
  so /lessons/7 means the same lesson after every reseed.
* Session ids are **UUIDv5** (name-based) instead of random UUIDv4.
* Learner timestamps are fixed local wall-clock times at fixed day offsets from a
  **reference day**. The same reference day always produces a byte-identical database;
  the CLI defaults it to "today" so the demo streak is always current.
* Nothing here calls `random` or reads the clock.

This module seeds *state only*. It does not compute XP, streaks, hearts or unlocking;
those rules belong to the services. Stored counters are copied from the data
files, except xp_total, which is the sum of the user's seeded XP events (the ledger
invariant).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed.authoring import AchievementIn, BotIn, CourseIn, LearnerIn, LearnersIn
from app.db.seed.exercise_builder import build_exercise
from app.models import (
    Achievement,
    Course,
    Exercise,
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

DATA_DIR = Path(__file__).parent / "data"

# Fixed namespace for name-based (v5) UUIDs: same name -> same UUID, forever.
SEED_NAMESPACE = uuid.UUID("6f1b8f5e-2c1d-5a7e-9b1f-4c2d8e0a7b31")

PRACTICE_SIZE = 6  # exercises in a seeded practice session
SESSION_MINUTES = 4  # seeded sessions end this long after they start

# Deletion order for --reset: children before parents. Learner state first (it
# RESTRICTs content deletion), then the achievement catalog, then content bottom-up.
RESET_ORDER: tuple[type[Base], ...] = (
    UserAchievement,
    XpEvent,
    SessionAnswer,
    LessonCompletion,
    LessonSession,
    User,
    Achievement,
    Exercise,
    Lesson,
    Skill,
    Unit,
    Course,
)


@dataclass(frozen=True)
class SeedResult:
    skipped: bool
    reference_day: date
    counts: dict[str, int]


def load_course() -> CourseIn:
    return CourseIn.model_validate(_read_json("course_es.json"))


def load_achievements() -> list[AchievementIn]:
    return TypeAdapter(list[AchievementIn]).validate_python(_read_json("achievements.json"))


def load_learners() -> LearnersIn:
    return LearnersIn.model_validate(_read_json("learners.json"))


def default_reference_day(now: datetime | None = None) -> date:
    """Today in the default learner's timezone (the only place the clock is read)."""
    zone = ZoneInfo(load_learners().learner.timezone)
    return (now or datetime.now(UTC)).astimezone(zone).date()


def is_seeded(db: Session) -> bool:
    slug = load_course().slug
    return db.scalar(select(Course.id).where(Course.slug == slug)) is not None


def reset_database(db: Session) -> None:
    """Delete every row, children first. Runs inside the caller's transaction."""
    for model in RESET_ORDER:
        db.execute(delete(model))
    db.flush()


def seed_database(db: Session, reference_day: date, *, reset: bool = False) -> SeedResult:
    """Seed content, achievements, the default learner and leaderboard bots.

    Without `reset`, an already-seeded database is left untouched (idempotent).
    The caller owns the transaction: commit on success, roll back on error.
    """
    if reset:
        reset_database(db)
    elif is_seeded(db):
        return SeedResult(skipped=True, reference_day=reference_day, counts=_counts(db))

    course = _seed_course(db, load_course())
    achievements = _seed_achievements(db, load_achievements())
    people = load_learners()
    _seed_learner(db, people.learner, course, achievements, reference_day)
    for index, bot in enumerate(people.bots, start=2):
        _seed_bot(db, index, bot, course, reference_day)
    db.flush()
    return SeedResult(skipped=False, reference_day=reference_day, counts=_counts(db))


# --------------------------------------------------------------------------- content


def _seed_course(db: Session, spec: CourseIn) -> Course:
    course = Course(
        id=1,
        slug=spec.slug,
        title=spec.title,
        learning_language=spec.learning_language,
        from_language=spec.from_language,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),  # fixed: content has no "age"
    )
    unit_id = skill_id = lesson_id = exercise_id = 0
    for unit_index, unit_spec in enumerate(spec.units):
        unit_id += 1
        unit = Unit(
            id=unit_id,
            order_index=unit_index,
            title=unit_spec.title,
            description=unit_spec.description,
            color=unit_spec.color,
        )
        course.units.append(unit)
        for skill_index, skill_spec in enumerate(unit_spec.skills):
            skill_id += 1
            skill = Skill(
                id=skill_id,
                order_index=skill_index,
                title=skill_spec.title,
                icon=skill_spec.icon,
                description=skill_spec.description,
            )
            unit.skills.append(skill)
            for lesson_index, lesson_spec in enumerate(skill_spec.lessons):
                lesson_id += 1
                lesson = Lesson(id=lesson_id, order_index=lesson_index, title=lesson_spec.title)
                skill.lessons.append(lesson)
                for exercise_index, exercise_spec in enumerate(lesson_spec.exercises):
                    exercise_id += 1
                    seed = f"{skill_spec.key}/{lesson_index + 1}/{exercise_index + 1}"
                    built = build_exercise(exercise_spec, seed)
                    lesson.exercises.append(
                        Exercise(
                            id=exercise_id,
                            order_index=exercise_index,
                            type=built.type,
                            prompt=built.prompt,
                            payload=built.payload,
                            solution=built.solution,
                            explanation=built.explanation,
                        )
                    )
    db.add(course)
    db.flush()
    return course


def _seed_achievements(db: Session, specs: list[AchievementIn]) -> dict[str, Achievement]:
    rows = {}
    for index, spec in enumerate(specs, start=1):
        rows[spec.code] = Achievement(id=index, **spec.model_dump())
    db.add_all(rows.values())
    db.flush()
    return rows


# --------------------------------------------------------------------------- people


def _at(reference_day: date, day: int, local_time: time, zone: ZoneInfo) -> datetime:
    """Local wall-clock time on reference_day + day, as an aware UTC datetime."""
    local = datetime.combine(reference_day + timedelta(days=day), local_time, tzinfo=zone)
    return local.astimezone(UTC)


def _lesson_index(course: Course) -> tuple[dict[str, Lesson], dict[str, Skill]]:
    """Map "skill_key/lesson_number" -> Lesson and skill_key -> Skill, via authored keys."""
    spec = load_course()
    lessons: dict[str, Lesson] = {}
    skills: dict[str, Skill] = {}
    for unit, unit_spec in zip(course.units, spec.units, strict=True):
        for skill, skill_spec in zip(unit.skills, unit_spec.skills, strict=True):
            skills[skill_spec.key] = skill
            for number, lesson in enumerate(skill.lessons, start=1):
                lessons[f"{skill_spec.key}/{number}"] = lesson
    return lessons, skills


def _seed_learner(
    db: Session,
    spec: LearnerIn,
    course: Course,
    achievements: dict[str, Achievement],
    reference_day: date,
) -> None:
    zone = ZoneInfo(spec.timezone)
    lessons, skills = _lesson_index(course)
    user = User(
        id=1,
        username=spec.username,
        display_name=spec.display_name,
        avatar_color=spec.avatar_color,
        timezone=spec.timezone,
        is_bot=False,
        created_at=_at(reference_day, spec.joined.day, spec.joined.time, zone),
        current_course=course,
        hearts=spec.hearts,
        hearts_updated_at=_at(
            reference_day, spec.hearts_updated.day, spec.hearts_updated.time, zone
        ),
        gems=spec.gems,
        xp_total=sum(activity.xp for activity in spec.activity),
        streak_count=spec.streak_count,
        longest_streak=spec.longest_streak,
        last_streak_date=reference_day + timedelta(days=spec.last_streak_day),
        daily_goal_xp=spec.daily_goal_xp,
    )
    db.add(user)
    completions: dict[int, LessonCompletion] = {}

    for number, activity in enumerate(spec.activity, start=1):
        started = _at(reference_day, activity.day, activity.time, zone)
        ended = started + timedelta(minutes=SESSION_MINUTES)
        if activity.lesson is not None:
            lesson = lessons[activity.lesson]
            session = LessonSession(
                mode=SessionMode.LESSON,
                lesson=lesson,
                exercise_ids=[exercise.id for exercise in lesson.exercises],
            )
            source = XpSource.LESSON
        else:
            assert activity.practice is not None
            skill = skills[activity.practice]
            # Practice reviews exercises from lessons already completed in that skill.
            pool = [
                exercise.id
                for lesson in skill.lessons
                if lesson.id in completions
                for exercise in lesson.exercises
            ]
            session = LessonSession(
                mode=SessionMode.PRACTICE, skill=skill, exercise_ids=pool[:PRACTICE_SIZE]
            )
            source = XpSource.PRACTICE

        session.id = str(uuid.uuid5(SEED_NAMESPACE, f"session/{spec.username}/{number}"))
        session.user = user
        session.status = SessionStatus.COMPLETED
        session.mistakes_count = activity.mistakes
        session.xp_awarded = activity.xp
        session.started_at, session.ended_at = started, ended
        # Same summary shape the lesson engine writes (seeded history has no rewards
        # breakdown; its XP is in session.xp_awarded and the XP event).
        total = len(session.exercise_ids)
        session.result = {
            "outcome": "completed",
            "total": total,
            "correct": total - activity.mistakes,
            "incorrect": activity.mistakes,
        }
        db.add(session)
        db.add(
            XpEvent(
                user=user,
                amount=activity.xp,
                source=source,
                session=session,
                created_at=ended,
                local_date=reference_day + timedelta(days=activity.day),
            )
        )

        if activity.lesson is not None:
            lesson = lessons[activity.lesson]
            existing = completions.get(lesson.id)
            if existing is None:
                completions[lesson.id] = LessonCompletion(
                    user=user,
                    lesson=lesson,
                    first_completed_at=ended,
                    last_completed_at=ended,
                    times_completed=1,
                    best_mistakes=activity.mistakes,
                )
                db.add(completions[lesson.id])
            else:  # replay
                existing.times_completed += 1
                existing.last_completed_at = ended
                existing.best_mistakes = min(existing.best_mistakes, activity.mistakes)

    for unlock in spec.achievements:
        db.add(
            UserAchievement(
                user=user,
                achievement=achievements[unlock.code],
                unlocked_at=_at(reference_day, unlock.day, unlock.time, zone),
            )
        )


BOT_ACTIVITY_TIME = time(18, 30)


def _seed_bot(db: Session, user_id: int, spec: BotIn, course: Course, reference_day: date) -> None:
    zone = ZoneInfo(spec.timezone)
    first_day = min(day for day, _ in spec.daily_xp)
    user = User(
        id=user_id,
        username=spec.username,
        display_name=spec.display_name,
        avatar_color=spec.avatar_color,
        timezone=spec.timezone,
        is_bot=True,
        created_at=_at(reference_day, first_day - 1, BOT_ACTIVITY_TIME, zone),
        current_course=course,
        hearts_updated_at=_at(reference_day, first_day - 1, BOT_ACTIVITY_TIME, zone),
        xp_total=sum(amount for _, amount in spec.daily_xp),
        streak_count=spec.streak_count,
        longest_streak=spec.longest_streak,
        last_streak_date=reference_day + timedelta(days=spec.last_streak_day),
    )
    db.add(user)
    # Bots have ledger entries (so weekly leaderboards can sum them) but no session
    # history; session_id is NULL, which the ledger allows.
    for day, amount in sorted(spec.daily_xp):
        db.add(
            XpEvent(
                user=user,
                amount=amount,
                source=XpSource.LESSON,
                created_at=_at(reference_day, day, BOT_ACTIVITY_TIME, zone),
                local_date=reference_day + timedelta(days=day),
            )
        )


# --------------------------------------------------------------------------- helpers


def _read_json(name: str) -> object:
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _counts(db: Session) -> dict[str, int]:
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
        for model in reversed(RESET_ORDER)
    }
