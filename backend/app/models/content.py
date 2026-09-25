"""Course content: Course -> Unit -> Skill -> Lesson -> Exercise.

Content is shared by all learners and never references learner state. Each level
has an explicit `order_index` that is unique within its parent, and the unique
(parent_id, order_index) constraint doubles as the index for "children in order".

Deletes cascade down the tree (a unit cannot exist without its course). Learner
tables reference content with ON DELETE RESTRICT, so content that has learner
history cannot be deleted by accident.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base
from app.models.enums import ExerciseType, str_enum


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    learning_language: Mapped[str] = mapped_column(String(8))  # e.g. "es"
    from_language: Mapped[str] = mapped_column(String(8))  # e.g. "en"
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    units: Mapped[list["Unit"]] = relationship(
        back_populates="course",
        order_by="Unit.order_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Course {self.slug}>"


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("course_id", "order_index"),
        CheckConstraint("order_index >= 0", name="order_index_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    order_index: Mapped[int]
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(7), default="#58CC02")  # banner colour, hex

    course: Mapped[Course] = relationship(back_populates="units")
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="unit",
        order_by="Skill.order_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Unit {self.id} #{self.order_index} {self.title!r}>"


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("unit_id", "order_index"),
        CheckConstraint("order_index >= 0", name="order_index_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    order_index: Mapped[int]
    title: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(32), default="star")  # frontend icon key
    description: Mapped[str] = mapped_column(Text, default="")

    unit: Mapped[Unit] = relationship(back_populates="skills")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="skill",
        order_by="Lesson.order_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Skill {self.id} #{self.order_index} {self.title!r}>"


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("skill_id", "order_index"),
        CheckConstraint("order_index >= 0", name="order_index_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    order_index: Mapped[int]
    title: Mapped[str] = mapped_column(String(120))

    skill: Mapped[Skill] = relationship(back_populates="lessons")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="lesson",
        order_by="Exercise.order_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Lesson {self.id} #{self.order_index} {self.title!r}>"


class Exercise(Base):
    """One exercise of any of the five types.

    A single table with a `type` discriminator and two JSON columns, instead of one
    table per type: the types share lifecycle, ordering and grading flow, and differ
    only in shape, which Pydantic validates per type (app/schemas/exercises.py).

      payload  - what the learner sees (options, tiles, pairs...). Safe to send.
      solution - the correct answer(s). Server-only; never serialized to the client.
    """

    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("lesson_id", "order_index"),
        CheckConstraint("order_index >= 0", name="order_index_non_negative"),
        CheckConstraint("length(trim(prompt)) > 0", name="prompt_not_blank"),
        CheckConstraint(
            "json_valid(payload) AND json_type(payload) = 'object'", name="payload_is_object"
        ),
        CheckConstraint(
            "json_valid(solution) AND json_type(solution) = 'object'", name="solution_is_object"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    order_index: Mapped[int]
    type: Mapped[ExerciseType] = mapped_column(str_enum(ExerciseType, "exercise_type"))
    prompt: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    solution: Mapped[dict[str, Any]]
    explanation: Mapped[str | None] = mapped_column(Text)  # optional tip shown on feedback

    lesson: Mapped[Lesson] = relationship(back_populates="exercises")

    def __repr__(self) -> str:
        return f"<Exercise {self.id} #{self.order_index} {self.type.value}>"
