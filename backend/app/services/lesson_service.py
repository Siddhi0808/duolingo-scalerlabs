"""Lesson engine: start/resume a session, serve the current exercise, grade answers.

Session lifecycle (SessionStatus)
---------------------------------
    start ──> ACTIVE ──(last exercise answered, hearts left)──> COMPLETED
                │  └───(wrong answer takes the last heart)─────> FAILED
                └──────(learner quits / starts another lesson)─> ABANDONED

Server-side position
--------------------
A session stores the exercise ids it serves (`exercise_ids`, fixed at start). Each
exercise is answered exactly once (UNIQUE(session_id, exercise_id)), so the number of
answers *is* the position, and the current exercise is `exercise_ids[len(answers)]`.
The client's `exercise_id` is only checked against that; it never selects anything.

Transactions
------------
Each write use case (start, answer, abandon) is one transaction that the service
commits at the end. For the answer that completes a lesson that is: grade + answer
row + session update + heart loss + LessonCompletion + XP event + xp_total + streak +
achievements (progression_service). All commit together or, on any exception, none
do (the request's session rolls back).

Hearts
------
Every heart read/write goes through services.hearts (regeneration applied first).
Starting a lesson or answering with 0 effective hearts is refused with NO_HEARTS.
users.version is an optimistic lock: if another request changed the learner row
between our read and our write, the answer is retried once from fresh state.

Idempotency
-----------
Re-submitting an already-graded exercise returns the stored result again (`replayed`)
if the answer is identical, or DUPLICATE_SUBMISSION if it differs. Two racing
requests for the same exercise are serialized by the unique constraint: the loser's
transaction is rolled back and it takes the same replay path.
"""

from datetime import datetime
from typing import Literal

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.clock import utc_now
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
)
from app.models import (
    Exercise,
    Lesson,
    LessonCompletion,
    LessonSession,
    SessionAnswer,
    SessionMode,
    SessionStatus,
    User,
)
from app.schemas.gamification import CompletionRewards
from app.schemas.lesson import (
    Answer,
    AnswerRequest,
    AnswerResult,
    LessonRef,
    PublicExercise,
    SessionProgress,
    SessionState,
    StartSessionResponse,
)
from app.services import grading, hearts, path_service, progression_service
from app.services.path_rules import LessonState

_answer_adapter: TypeAdapter[Answer] = TypeAdapter(Answer)


# --------------------------------------------------------------------------- start


def start_lesson(
    db: Session, user: User, lesson_id: int, now: datetime | None = None
) -> StartSessionResponse:
    """Start a lesson, or resume the learner's active session for it."""
    now = now or utc_now()
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("LESSON_NOT_FOUND", f"Lesson {lesson_id} does not exist.")
    if path_service.lesson_access(db, user, lesson) is LessonState.LOCKED:
        raise ForbiddenError(
            "LESSON_LOCKED",
            "Complete the previous skill to unlock this lesson.",
            {"lesson_id": lesson_id},
        )

    active = _active_session(db, user)
    if active is not None and active.lesson_id == lesson.id:
        return _start_response(db, active, user, now, resumed=True, abandoned=None)

    _require_hearts(user, now)

    # One active session per user (a partial unique index enforces it): starting a
    # different lesson ends the previous one first, in the same transaction.
    abandoned_id: str | None = None
    if active is not None:
        _end(active, SessionStatus.ABANDONED, now)
        abandoned_id = active.id
        db.flush()

    session = LessonSession(
        user_id=user.id,
        lesson_id=lesson.id,
        mode=SessionMode.LESSON,
        status=SessionStatus.ACTIVE,
        exercise_ids=[exercise.id for exercise in lesson.exercises],
        started_at=now,
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request created an active session first: resume that one.
        db.rollback()
        active = _active_session(db, user)
        if active is None or active.lesson_id != lesson.id:
            raise
        return _start_response(db, active, user, now, resumed=True, abandoned=None)
    return _start_response(db, session, user, now, resumed=False, abandoned=abandoned_id)


# --------------------------------------------------------------------------- read


def get_session_state(
    db: Session, user: User, session_id: str, now: datetime | None = None
) -> SessionState:
    session = _owned_session(db, user, session_id)
    return _state(db, session, user, now or utc_now())


def get_current_exercise(db: Session, user: User, session_id: str) -> PublicExercise:
    session = _owned_session(db, user, session_id)
    _require_active(session)
    exercise = _current_exercise(db, session)
    if exercise is None:  # unreachable: the last answer always ends the session
        raise ConflictError("SESSION_NOT_ACTIVE", "This session has no exercises left.")
    return exercise


# --------------------------------------------------------------------------- answer


def submit_answer(
    db: Session,
    user: User,
    session_id: str,
    request: AnswerRequest,
    now: datetime | None = None,
) -> AnswerResult:
    now = now or utc_now()
    try:
        return _submit_answer(db, user, session_id, request, now)
    except StaleDataError:
        # The learner row changed under us (e.g. a refill committed first): nothing
        # was saved, so re-run once against fresh state.
        db.rollback()
        db.refresh(user)
        return _submit_answer(db, user, session_id, request, now)


def _submit_answer(
    db: Session,
    user: User,
    session_id: str,
    request: AnswerRequest,
    now: datetime,
    *,
    _retrying: bool = False,
) -> AnswerResult:
    session = _owned_session(db, user, session_id)
    submitted = request.answer.model_dump(mode="json")

    # 1. Already graded in this session? Replay or reject; never grade twice.
    previous = next((a for a in session.answers if a.exercise_id == request.exercise_id), None)
    if previous is not None:
        if previous.submitted != submitted:
            raise ConflictError(
                "DUPLICATE_SUBMISSION",
                "This exercise has already been answered.",
                {"exercise_id": request.exercise_id},
            )
        return _replay(db, session, user, previous, now)

    # 2. Only an active session accepts answers, only with hearts left, and only for
    #    its current exercise.
    _require_active(session)
    _require_hearts(user, now)
    position = len(session.answers)
    current_id = session.exercise_ids[position]
    if request.exercise_id != current_id:
        raise ConflictError(
            "EXERCISE_NOT_CURRENT",
            "That is not the current exercise.",
            {"current_exercise_id": current_id},
        )

    # 3. Grade on the server against the stored solution.
    exercise = db.get(Exercise, current_id)
    assert exercise is not None  # FK + RESTRICT guarantee it exists
    try:
        result = grading.grade(exercise.type, exercise.payload, exercise.solution, request.answer)
    except grading.InvalidAnswerError as error:
        raise UnprocessableError(
            "INVALID_ANSWER", str(error), {"exercise_id": exercise.id}
        ) from error

    # 4. Persist the answer first: the unique constraint is the idempotency guard.
    session.answers.append(
        SessionAnswer(
            exercise_id=exercise.id,
            submitted=submitted,
            is_correct=result.correct,
            created_at=now,
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if _retrying:
            raise
        # Lost a race with an identical request: answer from the stored row instead.
        return _submit_answer(db, user, session_id, request, now, _retrying=True)

    # 5. Consequences: heart loss, then fail / complete / continue.
    failure_reason: Literal["out_of_hearts"] | None = None
    rewards: CompletionRewards | None = None
    if not result.correct:
        session.mistakes_count += 1
        hearts.lose_heart(user, now)
    if not result.correct and user.hearts == 0:
        _end(session, SessionStatus.FAILED, now)
        failure_reason = "out_of_hearts"
    elif position + 1 == len(session.exercise_ids):
        _end(session, SessionStatus.COMPLETED, now)
        first_completion = _record_completion(db, user, session, now)
        # XP, streak, daily goal and achievements: same transaction, same commit.
        rewards = progression_service.apply_lesson_completion(
            db, user, session, first_completion, now
        )
        session.result = {**(session.result or {}), "rewards": rewards.model_dump(mode="json")}

    db.commit()
    return AnswerResult(
        exercise_id=exercise.id,
        correct=result.correct,
        correct_answer=result.correct_answer,
        note=result.note,
        explanation=exercise.explanation,
        replayed=False,
        hearts=hearts.status(user, now),
        progress=_progress(session),
        failure_reason=failure_reason,
        rewards=rewards,
    )


# --------------------------------------------------------------------------- abandon


def abandon_session(
    db: Session, user: User, session_id: str, now: datetime | None = None
) -> SessionState:
    """Quit a lesson. Idempotent for an already-abandoned session."""
    now = now or utc_now()
    session = _owned_session(db, user, session_id)
    if session.status is SessionStatus.ACTIVE:
        _end(session, SessionStatus.ABANDONED, now)
        db.commit()
    elif session.status is not SessionStatus.ABANDONED:
        _require_active(session)  # completed/failed sessions can't be abandoned
    return _state(db, session, user, now)


# --------------------------------------------------------------------------- helpers


def _owned_session(db: Session, user: User, session_id: str) -> LessonSession:
    """Load a session of the current learner. Someone else's session looks nonexistent."""
    session = db.get(LessonSession, session_id)
    if session is None or session.user_id != user.id:
        raise NotFoundError("SESSION_NOT_FOUND", "Session not found.")
    return session


def _active_session(db: Session, user: User) -> LessonSession | None:
    return db.scalar(
        select(LessonSession).where(
            LessonSession.user_id == user.id, LessonSession.status == SessionStatus.ACTIVE
        )
    )


def _require_active(session: LessonSession) -> None:
    if session.status is not SessionStatus.ACTIVE:
        raise ConflictError(
            "SESSION_NOT_ACTIVE",
            f"This session is {session.status.value}.",
            {"status": session.status.value},
        )


def _require_hearts(user: User, now: datetime) -> None:
    """Refuse with NO_HEARTS when the learner has no *effective* hearts (after regen)."""
    heart_status = hearts.status(user, now)
    if heart_status.current <= 0:
        raise ConflictError(
            "NO_HEARTS",
            "You have no hearts left.",
            {"hearts": heart_status.model_dump()},
        )


def _end(session: LessonSession, status: SessionStatus, now: datetime) -> None:
    session.status = status
    session.ended_at = now
    if status is not SessionStatus.ABANDONED:
        progress = _progress(session)
        session.result = {
            "outcome": status.value,
            "total": progress.total,
            "correct": progress.correct,
            "incorrect": progress.incorrect,
        }


def _record_completion(db: Session, user: User, session: LessonSession, now: datetime) -> bool:
    """Insert the (user, lesson) completion or update it on replay. Never duplicates.

    Returns True for the learner's first completion of this lesson.
    """
    assert session.lesson_id is not None
    completion = db.scalar(
        select(LessonCompletion).where(
            LessonCompletion.user_id == user.id, LessonCompletion.lesson_id == session.lesson_id
        )
    )
    if completion is None:
        db.add(
            LessonCompletion(
                user_id=user.id,
                lesson_id=session.lesson_id,
                first_completed_at=now,
                last_completed_at=now,
                times_completed=1,
                best_mistakes=session.mistakes_count,
            )
        )
        db.flush()
        return True
    completion.times_completed += 1
    completion.last_completed_at = now
    completion.best_mistakes = min(completion.best_mistakes, session.mistakes_count)
    db.flush()
    return False


def _replay(
    db: Session, session: LessonSession, user: User, answer: SessionAnswer, now: datetime
) -> AnswerResult:
    """Rebuild the original result by re-grading the stored submission (deterministic)."""
    exercise = db.get(Exercise, answer.exercise_id)
    assert exercise is not None
    stored = _answer_adapter.validate_python(answer.submitted)
    result = grading.grade(exercise.type, exercise.payload, exercise.solution, stored)
    is_last = answer is session.answers[-1]
    failed = session.status is SessionStatus.FAILED and is_last
    stored_rewards = (session.result or {}).get("rewards")
    rewards = (
        CompletionRewards.model_validate(stored_rewards)
        if is_last and session.status is SessionStatus.COMPLETED and stored_rewards
        else None
    )
    return AnswerResult(
        exercise_id=exercise.id,
        correct=answer.is_correct,
        correct_answer=result.correct_answer,
        note=result.note,
        explanation=exercise.explanation,
        replayed=True,
        hearts=hearts.status(user, now),
        progress=_progress(session),
        failure_reason="out_of_hearts" if failed else None,
        rewards=rewards,  # the originally awarded rewards, not new ones
    )


def _progress(session: LessonSession) -> SessionProgress:
    answered = len(session.answers)
    correct = sum(1 for answer in session.answers if answer.is_correct)
    return SessionProgress(
        status=session.status,
        total=len(session.exercise_ids),
        answered=answered,
        correct=correct,
        incorrect=answered - correct,
    )


def _current_exercise(db: Session, session: LessonSession) -> PublicExercise | None:
    position = len(session.answers)
    if session.status is not SessionStatus.ACTIVE or position >= len(session.exercise_ids):
        return None
    exercise = db.get(Exercise, session.exercise_ids[position])
    assert exercise is not None
    return PublicExercise(
        id=exercise.id,
        type=exercise.type,
        position=position + 1,
        prompt=exercise.prompt,
        payload=exercise.payload,  # browser-safe by construction; solution is never read
    )


def _lesson_ref(session: LessonSession) -> LessonRef | None:
    if session.lesson is None:
        return None
    return LessonRef(
        id=session.lesson.id,
        title=session.lesson.title,
        skill_id=session.lesson.skill_id,
        skill_title=session.lesson.skill.title,
    )


def _state(db: Session, session: LessonSession, user: User, now: datetime) -> SessionState:
    return SessionState(
        session_id=session.id,
        mode=session.mode,
        lesson=_lesson_ref(session),
        progress=_progress(session),
        hearts=hearts.status(user, now),
        current_exercise=_current_exercise(db, session),
    )


def _start_response(
    db: Session,
    session: LessonSession,
    user: User,
    now: datetime,
    *,
    resumed: bool,
    abandoned: str | None,
) -> StartSessionResponse:
    state = _state(db, session, user, now)
    return StartSessionResponse(
        **state.model_dump(), resumed=resumed, abandoned_session_id=abandoned
    )
