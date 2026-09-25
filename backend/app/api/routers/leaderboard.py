"""GET /leaderboard: read-only ranking by total XP. There is no write endpoint."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.gamification import LeaderboardResponse
from app.services import leaderboard_service

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(db: DbSession, user: CurrentUser) -> LeaderboardResponse:
    return leaderboard_service.build_leaderboard(db, user)
