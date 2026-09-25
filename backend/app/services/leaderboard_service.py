"""Leaderboard: every learner ranked by persisted all-time XP (users.xp_total).

Order is deterministic: XP descending, then user id ascending as the tie-breaker, and
ranks are simply positions 1..n in that order (ties do not share a rank). Read-only:
the only thing that changes xp_total is a server-side lesson completion.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.gamification import LeaderboardEntry, LeaderboardResponse

LEADERBOARD_SIZE = 50


def build_leaderboard(db: Session, user: User) -> LeaderboardResponse:
    rows = db.scalars(
        select(User).order_by(User.xp_total.desc(), User.id.asc()).limit(LEADERBOARD_SIZE)
    ).all()
    entries = [
        LeaderboardEntry(
            rank=position,
            username=row.username,
            display_name=row.display_name,
            avatar_color=row.avatar_color,
            xp=row.xp_total,
            is_current_user=row.id == user.id,
        )
        for position, row in enumerate(rows, start=1)
    ]
    current = next((entry.rank for entry in entries if entry.is_current_user), None)
    return LeaderboardResponse(entries=entries, current_user_rank=current)
