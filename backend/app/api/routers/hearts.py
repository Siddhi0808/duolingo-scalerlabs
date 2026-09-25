"""POST /hearts/refill: mock refill of hearts for gems (no real payments)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.clock import utc_now
from app.schemas.gamification import HeartRefillResponse
from app.services import hearts

router = APIRouter(tags=["hearts"])


@router.post("/hearts/refill", response_model=HeartRefillResponse)
def refill_hearts(db: DbSession, user: CurrentUser) -> HeartRefillResponse:
    return hearts.refill(db, user, utc_now())
