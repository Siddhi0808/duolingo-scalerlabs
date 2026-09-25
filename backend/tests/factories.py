"""Tiny builders for model tests (not seed data: just enough rows to exercise the schema)."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    LessonSession,
    SessionMode,
    Skill,
    Unit,
    User,
)


def make_course_tree(db: Session) -> Course:
    """Course -> 1 unit -> 1 skill -> 1 lesson -> 2 exercises."""
    course = Course(slug="es-en", title="Spanish", learning_language="es", from_language="en")
    unit = Unit(order_index=0, title="Basics")
    skill = Skill(order_index=0, title="Greetings")
    lesson = Lesson(order_index=0, title="Greetings 1")
    lesson.exercises = [
        make_exercise(0, ExerciseType.MULTIPLE_CHOICE),
        make_exercise(1, ExerciseType.TYPE_ANSWER),
    ]
    skill.lessons = [lesson]
    unit.skills = [skill]
    course.units = [unit]
    db.add(course)
    db.flush()
    return course


def make_exercise(order_index: int, type_: ExerciseType, **overrides: Any) -> Exercise:
    fields: dict[str, Any] = {
        "order_index": order_index,
        "type": type_,
        "prompt": "Which one means 'hello'?",
        "payload": {"options": [{"id": "a", "text": "hola"}, {"id": "b", "text": "adiós"}]},
        "solution": {"correct_option_id": "a"},
    }
    fields.update(overrides)
    return Exercise(**fields)


def make_user(db: Session, username: str = "learner") -> User:
    user = User(username=username, display_name=username.title())
    db.add(user)
    db.flush()
    return user


def first_lesson(course: Course) -> Lesson:
    return course.units[0].skills[0].lessons[0]


def start_session(db: Session, user: User, lesson: Lesson) -> LessonSession:
    session = LessonSession(
        user=user,
        lesson=lesson,
        mode=SessionMode.LESSON,
        exercise_ids=[exercise.id for exercise in lesson.exercises],
    )
    db.add(session)
    db.flush()
    return session


NOW = datetime(2026, 9, 25, 8, 30, tzinfo=UTC)
TODAY = date(2026, 9, 25)


def set_hearts(db: Session, username: str, hearts: int, at: datetime) -> User:
    """Give a user an explicit heart state (count + regeneration anchor) and commit.

    Tests that care about hearts set them explicitly, so regeneration from the seeded
    timestamps (which depend on the seed's reference day) cannot change the outcome.
    """
    from sqlalchemy import select

    user = db.scalars(select(User).where(User.username == username)).one()
    user.hearts, user.hearts_updated_at = hearts, at
    db.commit()
    return user
