"""Session endpoints: read state, get the current exercise, answer, quit.

Every handler is one line: all rules live in lesson_service.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.lesson import AnswerRequest, AnswerResult, PublicExercise, SessionState
from app.services import lesson_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionState)
def get_session(session_id: str, db: DbSession, user: CurrentUser) -> SessionState:
    return lesson_service.get_session_state(db, user, session_id)


@router.get("/{session_id}/current", response_model=PublicExercise)
def get_current_exercise(session_id: str, db: DbSession, user: CurrentUser) -> PublicExercise:
    return lesson_service.get_current_exercise(db, user, session_id)


@router.post("/{session_id}/answer", response_model=AnswerResult)
def submit_answer(
    session_id: str, request: AnswerRequest, db: DbSession, user: CurrentUser
) -> AnswerResult:
    return lesson_service.submit_answer(db, user, session_id, request)


@router.post("/{session_id}/abandon", response_model=SessionState)
def abandon_session(session_id: str, db: DbSession, user: CurrentUser) -> SessionState:
    return lesson_service.abandon_session(db, user, session_id)
