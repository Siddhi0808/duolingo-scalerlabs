"""GET /path: everything the home screen needs to draw the learning path, in one call."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.path import PathResponse
from app.services import path_service

router = APIRouter(tags=["path"])


@router.get("/path", response_model=PathResponse)
def get_path(db: DbSession, user: CurrentUser) -> PathResponse:
    return path_service.build_path(db, user)
