"""XP ledger and achievements."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base
from app.models.enums import AchievementMetric, XpSource, str_enum

if TYPE_CHECKING:
    from app.models.progress import LessonSession
    from app.models.user import User


class XpEvent(Base):
    """Append-only ledger of XP awards: the auditable truth behind users.xp_total.

    * `local_date` is the learner's calendar date at award time, so "XP today" and
      "active days" are one indexed SUM with no timezone math in SQL.
    * `session_id` is UNIQUE: one session can award XP at most once, even if the
      completion request is retried. (SQLite allows many NULLs for bonus events.)
    * ON DELETE SET NULL on the session keeps the ledger intact if session logs are
      ever pruned.
    """

    __tablename__ = "xp_events"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("session_id"),
        Index(None, "user_id", "created_at"),
        Index(None, "user_id", "local_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int]
    source: Mapped[XpSource] = mapped_column(str_enum(XpSource, "xp_source"))
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    local_date: Mapped[date]

    user: Mapped["User"] = relationship(back_populates="xp_events")
    session: Mapped["LessonSession | None"] = relationship()

    def __repr__(self) -> str:
        return f"<XpEvent user={self.user_id} +{self.amount} {self.source.value}>"


class Achievement(Base):
    """Catalog entry (content-like, shared by all learners).

    Rules are data: unlocked when the learner's `metric` reaches `threshold`.
    """

    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("metric", "tier"),
        CheckConstraint("threshold > 0", name="threshold_positive"),
        CheckConstraint("tier >= 1", name="tier_positive"),
        CheckConstraint("gem_reward >= 0", name="gem_reward_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # e.g. "wildfire_1"
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(32))
    metric: Mapped[AchievementMetric] = mapped_column(
        str_enum(AchievementMetric, "achievement_metric")
    )
    threshold: Mapped[int]
    tier: Mapped[int] = mapped_column(default=1)
    gem_reward: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<Achievement {self.code}>"


class UserAchievement(Base):
    """An unlocked achievement. Composite PK => an achievement unlocks once per user."""

    __tablename__ = "user_achievements"
    __table_args__ = (Index(None, "achievement_id"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="RESTRICT"), primary_key=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["User"] = relationship(back_populates="achievements")
    achievement: Mapped[Achievement] = relationship()

    def __repr__(self) -> str:
        return f"<UserAchievement user={self.user_id} achievement={self.achievement_id}>"
