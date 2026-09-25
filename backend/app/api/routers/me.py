"""GET /me: header and profile data for the current learner, in one call."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.gamification import MeResponse
from app.services import profile_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def get_me(db: DbSession, user: CurrentUser) -> MeResponse:
    return profile_service.build_me(db, user)
