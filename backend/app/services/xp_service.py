"""XP: the amount rule, the ledger write and ledger queries.

The only way XP is created is `award_xp`, called by trusted server-side code inside
the lesson-completion transaction. It writes an XpEvent (the audit trail) and
increments users.xp_total in the same transaction, so the two can never disagree.
XpEvent.session_id is UNIQUE: a session can produce at most one XP event, even if
application code tried twice.
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import local_date
from app.core.constants import LESSON_XP
from app.models import LessonSession, User, XpEvent, XpSource


def lesson_xp(first_completion: bool) -> int:
    """10 XP for the first successful completion of a lesson; replays earn 0."""
    return LESSON_XP if first_completion else 0


def award_xp(
    db: Session,
    user: User,
    amount: int,
    source: XpSource,
    now: datetime,
    session: LessonSession | None = None,
) -> XpEvent:
    """Append a ledger entry and bump the user's total. Flushes, so a duplicate
    session award fails here with IntegrityError (and the transaction rolls back)."""
    if amount <= 0:
        raise ValueError("XP awards must be positive")
    event = XpEvent(
        user_id=user.id,
        amount=amount,
        source=source,
        session_id=session.id if session is not None else None,
        created_at=now,
        local_date=local_date(now, user.timezone),
    )
    db.add(event)
    user.xp_total += amount
    db.flush()
    return event


def xp_on_day(db: Session, user_id: int, day: date) -> int:
    """Total XP the user earned on their local calendar date `day`."""
    total = db.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(
            XpEvent.user_id == user_id, XpEvent.local_date == day
        )
    )
    return int(total or 0)
