"""Learner account and the counters the header reads on every page.

Stored counters (hearts, gems, xp_total, streak) are updated only by services inside
the same transaction that writes their source records (e.g. xp_total with an
XpEvent). Everything that can be computed on read (skill states, daily XP, current
heart count after regeneration) is not stored here.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.core.constants import (
    DAILY_GOAL_OPTIONS,
    DEFAULT_DAILY_GOAL_XP,
    DEFAULT_TIMEZONE,
    MAX_HEARTS,
    STARTING_GEMS,
)
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.content import Course
    from app.models.gamification import UserAchievement, XpEvent
    from app.models.progress import LessonCompletion, LessonSession

_goal_options_sql = ", ".join(str(option) for option in DAILY_GOAL_OPTIONS)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"hearts BETWEEN 0 AND {MAX_HEARTS}", name="hearts_range"),
        CheckConstraint("gems >= 0", name="gems_non_negative"),
        CheckConstraint("xp_total >= 0", name="xp_total_non_negative"),
        CheckConstraint("streak_count >= 0", name="streak_non_negative"),
        # Implied by the next check too, but stated explicitly so the rule is readable.
        CheckConstraint("longest_streak >= 0", name="longest_streak_non_negative"),
        CheckConstraint("longest_streak >= streak_count", name="longest_streak_covers_current"),
        CheckConstraint(f"daily_goal_xp IN ({_goal_options_sql})", name="daily_goal_option"),
        Index(None, "current_course_id"),
        # Serves the leaderboard's ORDER BY xp_total DESC, id without a sort.
        Index("ix_users_leaderboard", text("xp_total DESC"), "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    avatar_color: Mapped[str] = mapped_column(String(7), default="#1CB0F6")
    # IANA zone; decides where the learner's "day" starts for streaks and daily goals.
    timezone: Mapped[str] = mapped_column(String(64), default=DEFAULT_TIMEZONE)
    is_bot: Mapped[bool] = mapped_column(default=False)  # seeded leaderboard rivals
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    current_course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL")
    )

    # Hearts: stored count + anchor time. Regeneration is computed lazily from
    # hearts_updated_at, so no background job is needed.
    hearts: Mapped[int] = mapped_column(default=MAX_HEARTS)
    hearts_updated_at: Mapped[datetime] = mapped_column(default=utc_now)

    gems: Mapped[int] = mapped_column(default=STARTING_GEMS)

    # Denormalized sum of xp_events.amount, kept in the same transaction as the ledger.
    xp_total: Mapped[int] = mapped_column(default=0)

    # Streak: last local calendar day with activity. "Broken" is derived on read.
    streak_count: Mapped[int] = mapped_column(default=0)
    longest_streak: Mapped[int] = mapped_column(default=0)
    last_streak_date: Mapped[date | None]

    daily_goal_xp: Mapped[int] = mapped_column(default=DEFAULT_DAILY_GOAL_XP)

    # Optimistic lock: every UPDATE of this row checks and bumps `version`. If another
    # transaction changed the row since it was read (e.g. a refill racing an answer),
    # the UPDATE matches no row and SQLAlchemy raises StaleDataError instead of
    # silently overwriting the other change. Services retry once with fresh state.
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}

    current_course: Mapped["Course | None"] = relationship()

    # Learner state belongs to the user: deleting a user deletes it (DB-side cascade).
    sessions: Mapped[list["LessonSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    completions: Mapped[list["LessonCompletion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    xp_events: Mapped[list["XpEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="XpEvent.created_at",
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username}>"
