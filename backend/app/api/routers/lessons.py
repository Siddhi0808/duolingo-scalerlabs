"""Lesson entry point: POST /lessons/{lesson_id}/start (start or resume)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.lesson import StartSessionResponse
from app.services import lesson_service

router = APIRouter(tags=["lessons"])


@router.post("/lessons/{lesson_id}/start", response_model=StartSessionResponse)
def start_lesson(lesson_id: int, db: DbSession, user: CurrentUser) -> StartSessionResponse:
    return lesson_service.start_lesson(db, user, lesson_id)
