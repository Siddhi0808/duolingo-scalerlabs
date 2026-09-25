"""The single heart-state service: regeneration, loss, refill and the API view.

Stored state is two columns: `users.hearts` and `users.hearts_updated_at` (the
*regeneration anchor*: the moment the current regeneration interval started).
Regeneration is never a background job. The effective heart count is a pure function
of (stored hearts, anchor, now, interval, max):

    calculate_regenerated_hearts(3, 5, 12:00, 12:45, 30 min) -> 4 hearts, anchor 12:30
      (one full interval passed; the anchor advances by exactly one interval, so the
       15 minutes already spent toward the next heart are kept, not thrown away)

Read vs write
-------------
* Reads (GET /me, GET /sessions/{id}, responses) call `status()`: computed, not saved.
* Writes that change hearts (`lose_heart`, `refill`) first `materialize()` the
  regenerated state onto the user row, then apply their change. Both land in the
  same transaction as the rest of the request.

Anchor rules
------------
* Losing a heart from full starts the clock: anchor = now.
* Losing a heart while already regenerating keeps the anchor (progress toward the
  next heart is not reset).
* When regeneration reaches max, the anchor is irrelevant until the next loss.
* A refill sets hearts to max (anchor = now, idle while full).

Concurrency: users has an optimistic-lock `version` column, so two requests that both
read the same heart state cannot both write their result; the loser is retried with
fresh state by the calling service.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.constants import HEART_REFILL_GEM_COST, MAX_HEARTS
from app.core.errors import ConflictError
from app.models import User
from app.schemas.gamification import HeartInfo, HeartRefillResponse


@dataclass(frozen=True)
class HeartState:
    hearts: int
    anchor: datetime  # start of the current regeneration interval


def regeneration_interval() -> timedelta:
    return timedelta(minutes=get_settings().heart_regen_minutes)


# --------------------------------------------------------------------------- pure rules


def calculate_regenerated_hearts(
    current_hearts: int,
    max_hearts: int,
    last_change_at: datetime,
    now: datetime,
    regeneration_interval: timedelta,
) -> HeartState:
    """Effective hearts at `now`. Pure and deterministic.

    1. Full hearts stay full.
    2. No (or negative, e.g. clock skew) elapsed time: unchanged.
    3. Each whole interval elapsed adds one heart, several at once if needed.
    4. Never above max.
    5. The anchor advances by whole intervals only, preserving partial progress.
    """
    if current_hearts >= max_hearts:
        return HeartState(max_hearts, last_change_at)
    elapsed = now - last_change_at
    if elapsed <= timedelta(0):
        return HeartState(current_hearts, last_change_at)
    gained = elapsed // regeneration_interval
    if gained == 0:
        return HeartState(current_hearts, last_change_at)
    if current_hearts + gained >= max_hearts:
        became_full_at = last_change_at + (max_hearts - current_hearts) * regeneration_interval
        return HeartState(max_hearts, became_full_at)
    return HeartState(current_hearts + gained, last_change_at + gained * regeneration_interval)


def seconds_until_next_heart(
    state: HeartState, now: datetime, max_hearts: int, regeneration_interval: timedelta
) -> int | None:
    """Whole seconds (rounded up) until the next heart; None when full."""
    if state.hearts >= max_hearts:
        return None
    remaining = (state.anchor + regeneration_interval - now).total_seconds()
    return max(0, min(math.ceil(remaining), int(regeneration_interval.total_seconds())))


# --------------------------------------------------------------------------- user state


def effective(user: User, now: datetime) -> HeartState:
    return calculate_regenerated_hearts(
        user.hearts, MAX_HEARTS, user.hearts_updated_at, now, regeneration_interval()
    )


def status(user: User, now: datetime) -> HeartInfo:
    """The heart view every endpoint returns. Read-only."""
    state = effective(user, now)
    return HeartInfo(
        current=state.hearts,
        max=MAX_HEARTS,
        regenerating=state.hearts < MAX_HEARTS,
        seconds_until_next=seconds_until_next_heart(
            state, now, MAX_HEARTS, regeneration_interval()
        ),
        refill_cost_gems=HEART_REFILL_GEM_COST,
    )


def materialize(user: User, now: datetime) -> None:
    """Write the regenerated state onto the user row (inside the caller's transaction)."""
    state = effective(user, now)
    if (state.hearts, state.anchor) != (user.hearts, user.hearts_updated_at):
        user.hearts, user.hearts_updated_at = state.hearts, state.anchor


def lose_heart(user: User, now: datetime) -> None:
    """Take one heart (after applying regeneration), never going below zero."""
    materialize(user, now)
    if user.hearts >= MAX_HEARTS:
        user.hearts_updated_at = now  # the regeneration clock starts now
    user.hearts = max(0, user.hearts - 1)


# --------------------------------------------------------------------------- refill


def refill(
    db: Session, user: User, now: datetime, *, _retrying: bool = False
) -> HeartRefillResponse:
    """Mock refill: full hearts for HEART_REFILL_GEM_COST gems. A no-op when already full.

    One transaction. If a concurrent request changed the user row first (optimistic
    lock), it is retried once with fresh state, so two refills can never both charge
    and a refill can never overwrite a heart lost at the same moment.
    """
    materialize(user, now)
    refilled = user.hearts < MAX_HEARTS
    if refilled:
        if user.gems < HEART_REFILL_GEM_COST:
            raise ConflictError(
                "INSUFFICIENT_GEMS",
                "Not enough gems to refill hearts.",
                {"cost": HEART_REFILL_GEM_COST, "gems": user.gems},
            )
        user.gems -= HEART_REFILL_GEM_COST
        user.hearts = MAX_HEARTS
        user.hearts_updated_at = now
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        if _retrying:
            raise
        db.refresh(user)
        return refill(db, user, now, _retrying=True)
    return HeartRefillResponse(
        refilled=refilled,
        gems_spent=HEART_REFILL_GEM_COST if refilled else 0,
        gems=user.gems,
        hearts=status(user, now),
    )
