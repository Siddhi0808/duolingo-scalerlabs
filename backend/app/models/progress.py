"""Learner progress: lesson sessions, their answers, and lesson completions.

`lesson_completions` is the single source of truth for progress. Skill rings, skill
states (locked/active/completed) and unit completion are derived from it on read;
there is deliberately no skill_progress table that could drift out of sync.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base
from app.models.enums import SessionMode, SessionStatus, str_enum

if TYPE_CHECKING:
    from app.models.content import Exercise, Lesson, Skill
    from app.models.user import User


def _new_session_id() -> str:
    return str(uuid.uuid4())


class LessonSession(Base):
    """One attempt at a lesson (or a practice round).

    * `exercise_ids` snapshots exactly which exercises were served, so an active
      session can be resumed after a refresh and completion can be validated
      against it even if content changes later.
    * `result` stores the completion summary. Completing an already-completed session
      returns this stored result instead of granting rewards again (idempotency).
    * At most one ACTIVE session per user (partial unique index), so "resume" is
      never ambiguous.
    """

    __tablename__ = "lesson_sessions"
    __table_args__ = (
        # Lesson mode targets one lesson; practice targets a skill or the whole course.
        CheckConstraint(
            "(mode = 'lesson' AND lesson_id IS NOT NULL AND skill_id IS NULL)"
            " OR (mode = 'practice' AND lesson_id IS NULL)",
            name="target_matches_mode",
        ),
        # ended_at is set exactly when the session has left the ACTIVE state.
        CheckConstraint("(status = 'active') = (ended_at IS NULL)", name="ended_at_matches_status"),
        CheckConstraint("json_type(exercise_ids) = 'array'", name="exercise_ids_is_array"),
        CheckConstraint("mistakes_count >= 0", name="mistakes_non_negative"),
        CheckConstraint("xp_awarded >= 0", name="xp_awarded_non_negative"),
        Index(None, "user_id", "status"),
        Index(
            "uq_lesson_sessions_one_active_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
        Index(None, "lesson_id"),
        Index(None, "skill_id"),
    )

    # UUID string: not guessable or sequential, and safe to put in a URL.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_session_id)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    mode: Mapped[SessionMode] = mapped_column(str_enum(SessionMode, "session_mode"))
    status: Mapped[SessionStatus] = mapped_column(
        str_enum(SessionStatus, "session_status"), default=SessionStatus.ACTIVE
    )
    exercise_ids: Mapped[list[int]]
    mistakes_count: Mapped[int] = mapped_column(default=0)
    xp_awarded: Mapped[int] = mapped_column(default=0)
    result: Mapped[dict[str, Any] | None]
    started_at: Mapped[datetime] = mapped_column(default=utc_now)
    ended_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="sessions")
    lesson: Mapped["Lesson | None"] = relationship()
    skill: Mapped["Skill | None"] = relationship()
    answers: Mapped[list["SessionAnswer"]] = relationship(
        back_populates="session",
        order_by="SessionAnswer.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<LessonSession {self.id} {self.mode.value} {self.status.value}>"


class SessionAnswer(Base):
    """One submitted answer and its server-side grade.

    UNIQUE(session_id, exercise_id): each exercise is graded at most once per session.
    This is what makes answer submission idempotent under double clicks, retries and
    concurrent requests: a second insert for the same exercise fails at the database,
    so a session can never advance twice or lose two hearts for one exercise.
    The number of rows for a session is also its position: the current exercise is
    `session.exercise_ids[len(answers)]`.
    """

    __tablename__ = "session_answers"
    __table_args__ = (
        CheckConstraint("json_valid(submitted)", name="submitted_is_json"),
        UniqueConstraint("session_id", "exercise_id"),
        Index(None, "exercise_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("lesson_sessions.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"))
    submitted: Mapped[dict[str, Any]]
    is_correct: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    session: Mapped[LessonSession] = relationship(back_populates="answers")
    exercise: Mapped["Exercise"] = relationship()

    def __repr__(self) -> str:
        return f"<SessionAnswer {self.id} ex={self.exercise_id} correct={self.is_correct}>"


class LessonCompletion(Base):
    """The fact that a user has completed a lesson at least once.

    UNIQUE(user_id, lesson_id): replaying a lesson updates this row
    (times_completed += 1) instead of inserting a duplicate. First completion vs
    replay is therefore unambiguous, which is what decides the XP amount.
    """

    __tablename__ = "lesson_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id"),
        CheckConstraint("times_completed >= 1", name="times_completed_positive"),
        CheckConstraint("best_mistakes >= 0", name="best_mistakes_non_negative"),
        CheckConstraint("last_completed_at >= first_completed_at", name="completion_times_ordered"),
        Index(None, "lesson_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    # No defaults: the completion service sets both from one injected `now`, so a
    # first completion has first == last exactly and tests can control the time.
    first_completed_at: Mapped[datetime]
    last_completed_at: Mapped[datetime]
    times_completed: Mapped[int] = mapped_column(default=1)
    best_mistakes: Mapped[int]

    user: Mapped["User"] = relationship(back_populates="completions")
    lesson: Mapped["Lesson"] = relationship()

    def __repr__(self) -> str:
        return f"<LessonCompletion user={self.user_id} lesson={self.lesson_id}>"
