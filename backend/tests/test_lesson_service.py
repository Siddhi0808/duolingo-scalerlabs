"""Lesson engine at the service layer: lifecycle, hearts, completion, idempotency, races."""

import threading
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import utc_now
from app.core.errors import AppError
from app.models import (
    Exercise,
    Lesson,
    LessonCompletion,
    LessonSession,
    SessionAnswer,
    SessionStatus,
    User,
)
from app.schemas.lesson import AnswerRequest, AnswerResult
from app.services import grading, lesson_service
from app.services.hearts import lose_heart, regeneration_interval
from tests.factories import NOW, set_hearts
from tests.lesson_helpers import right_answer, wrong_answer

# Seeded learner: lesson 8 ("Animals and things", 6 exercises) is the next available
# lesson; lesson 12 is in a locked skill. A fresh learner can only start lessons 1-3.
NEXT_LESSON, LOCKED_LESSON = 8, 12


@pytest.fixture
def learner(seeded: Session) -> User:
    # 3 hearts as of "now" (these tests use the real clock and finish in seconds, far
    # less than one regeneration interval).
    return set_hearts(seeded, "learner", 3, utc_now())


@pytest.fixture
def newbie(seeded: Session) -> User:
    user = User(username="newbie", display_name="Newbie", current_course_id=1)
    seeded.add(user)
    seeded.commit()
    return user


def exercise(db: Session, exercise_id: int) -> Exercise:
    found = db.get(Exercise, exercise_id)
    assert found is not None
    return found


def answer(
    db: Session, user: User, session_id: str, *, correct: bool, exercise_id: int | None = None
) -> AnswerResult:
    """Answer the session's current exercise (or `exercise_id`) right or wrong."""
    target = exercise_id or lesson_service.get_current_exercise(db, user, session_id).id
    ex = exercise(db, target)
    body: dict[str, Any] = {
        "exercise_id": target,
        "answer": right_answer(ex) if correct else wrong_answer(ex),
    }
    return lesson_service.submit_answer(db, user, session_id, AnswerRequest.model_validate(body))


def error_code(excinfo: pytest.ExceptionInfo[AppError]) -> str:
    return excinfo.value.code


def count(db: Session, model: type[Any], *where: Any) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


# --------------------------------------------------------------------------- start


def test_start_unlocked_lesson(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    lesson = seeded.get(Lesson, NEXT_LESSON)
    assert lesson is not None
    assert started.progress.status is SessionStatus.ACTIVE
    assert (started.progress.total, started.progress.answered) == (6, 0)
    assert started.current_exercise is not None
    assert started.current_exercise.id == lesson.exercises[0].id
    assert started.current_exercise.position == 1
    assert started.lesson is not None and started.lesson.title == "Animals and things"
    assert not started.resumed and started.hearts.current == 3


def test_cannot_start_a_locked_lesson(seeded: Session, learner: User, newbie: User) -> None:
    with pytest.raises(AppError) as excinfo:
        lesson_service.start_lesson(seeded, learner, LOCKED_LESSON)
    assert error_code(excinfo) == "LESSON_LOCKED" and excinfo.value.status_code == 403
    with pytest.raises(AppError, match="unlock"):
        lesson_service.start_lesson(seeded, newbie, 4)  # skill 2 is locked for a newbie
    assert count(seeded, LessonSession, LessonSession.user_id == newbie.id) == 0


def test_cannot_start_a_nonexistent_lesson(seeded: Session, learner: User) -> None:
    with pytest.raises(AppError) as excinfo:
        lesson_service.start_lesson(seeded, learner, 999)
    assert error_code(excinfo) == "LESSON_NOT_FOUND" and excinfo.value.status_code == 404


def test_completed_lessons_can_be_replayed(seeded: Session, learner: User) -> None:
    replay = lesson_service.start_lesson(seeded, learner, 1)  # completed in the seed
    assert replay.progress.status is SessionStatus.ACTIVE


def test_starting_the_same_lesson_resumes_the_active_session(
    seeded: Session, learner: User
) -> None:
    first = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    answer(seeded, learner, first.session_id, correct=True)
    again = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    assert again.resumed and again.session_id == first.session_id
    assert again.progress.answered == 1
    assert again.current_exercise is not None and again.current_exercise.position == 2
    active = LessonSession.status == SessionStatus.ACTIVE
    assert count(seeded, LessonSession, LessonSession.user_id == learner.id, active) == 1


def test_starting_another_lesson_abandons_the_previous_one(seeded: Session, learner: User) -> None:
    first = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    second = lesson_service.start_lesson(seeded, learner, 1)
    assert second.abandoned_session_id == first.session_id
    old = seeded.get(LessonSession, first.session_id)
    assert old is not None and old.status is SessionStatus.ABANDONED and old.ended_at
    active = LessonSession.status == SessionStatus.ACTIVE
    assert count(seeded, LessonSession, LessonSession.user_id == learner.id, active) == 1


def test_cannot_start_with_zero_hearts(seeded: Session, learner: User) -> None:
    set_hearts(seeded, "learner", 0, utc_now())
    with pytest.raises(AppError) as excinfo:
        lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    assert error_code(excinfo) == "NO_HEARTS" and excinfo.value.status_code == 409


# --------------------------------------------------------------------------- answering


def test_current_exercise_follows_server_state(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    session = seeded.get(LessonSession, started.session_id)
    assert session is not None
    for index in range(3):
        current = lesson_service.get_current_exercise(seeded, learner, started.session_id)
        assert current.id == session.exercise_ids[index]
        assert current.position == index + 1
        answer(seeded, learner, started.session_id, correct=True)


def test_correct_answer_keeps_hearts_and_advances(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    result = answer(seeded, learner, started.session_id, correct=True)
    assert result.correct and not result.replayed
    assert result.hearts.current == 3
    assert (result.progress.answered, result.progress.correct, result.progress.incorrect) == (
        1,
        1,
        0,
    )


def test_wrong_answer_costs_one_heart_and_advances(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    result = answer(seeded, learner, started.session_id, correct=False)
    assert not result.correct and result.hearts.current == 2
    assert result.correct_answer  # shown on the red feedback sheet
    session = seeded.get(LessonSession, started.session_id)
    assert session is not None and session.mistakes_count == 1
    assert (result.progress.answered, result.progress.incorrect) == (1, 1)
    seeded.refresh(learner)
    assert learner.hearts == 2  # persisted


def test_session_advances_exactly_once_per_exercise(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    first_id = started.current_exercise.id if started.current_exercise else 0
    original = answer(seeded, learner, started.session_id, correct=False)
    repeat = answer(seeded, learner, started.session_id, correct=False, exercise_id=first_id)
    assert repeat.replayed and repeat.correct == original.correct
    assert repeat.correct_answer == original.correct_answer
    assert repeat.progress.answered == 1
    assert repeat.hearts.current == 2  # no second heart lost
    assert count(seeded, SessionAnswer, SessionAnswer.session_id == started.session_id) == 1
    current = lesson_service.get_current_exercise(seeded, learner, started.session_id)
    assert current.position == 2


def test_a_different_answer_for_a_graded_exercise_is_rejected(
    seeded: Session, learner: User
) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    first_id = started.current_exercise.id if started.current_exercise else 0
    answer(seeded, learner, started.session_id, correct=False)
    with pytest.raises(AppError) as excinfo:
        answer(seeded, learner, started.session_id, correct=True, exercise_id=first_id)
    assert error_code(excinfo) == "DUPLICATE_SUBMISSION" and excinfo.value.status_code == 409


def test_client_cannot_skip_ahead(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    session = seeded.get(LessonSession, started.session_id)
    assert session is not None
    future = session.exercise_ids[3]
    with pytest.raises(AppError) as excinfo:
        answer(seeded, learner, started.session_id, correct=True, exercise_id=future)
    assert error_code(excinfo) == "EXERCISE_NOT_CURRENT"
    assert excinfo.value.details == {"current_exercise_id": session.exercise_ids[0]}
    assert count(seeded, SessionAnswer, SessionAnswer.session_id == session.id) == 0


def test_invalid_answer_is_not_graded_and_costs_nothing(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    assert started.current_exercise is not None
    bad = AnswerRequest.model_validate(
        {
            "exercise_id": started.current_exercise.id,
            "answer": {"type": "multiple_choice", "option_id": "z"},
        }
    )
    with pytest.raises(AppError) as excinfo:
        lesson_service.submit_answer(seeded, learner, started.session_id, bad)
    assert error_code(excinfo) == "INVALID_ANSWER" and excinfo.value.status_code == 422
    seeded.rollback()
    seeded.refresh(learner)
    assert learner.hearts == 3
    assert count(seeded, SessionAnswer, SessionAnswer.session_id == started.session_id) == 0


# --------------------------------------------------------------------------- endings


def play_lesson(db: Session, user: User, lesson_id: int, wrong_at: set[int]) -> list[AnswerResult]:
    started = lesson_service.start_lesson(db, user, lesson_id)
    return [
        answer(db, user, started.session_id, correct=index not in wrong_at)
        for index in range(started.progress.total)
    ]


def test_final_exercise_completes_the_lesson(seeded: Session, learner: User) -> None:
    results = play_lesson(seeded, learner, NEXT_LESSON, wrong_at=set())
    assert [r.progress.status for r in results] == [SessionStatus.ACTIVE] * 5 + [
        SessionStatus.COMPLETED
    ]
    completion = seeded.scalars(
        select(LessonCompletion).where(
            LessonCompletion.user_id == learner.id, LessonCompletion.lesson_id == NEXT_LESSON
        )
    ).one()
    assert (completion.times_completed, completion.best_mistakes) == (1, 0)
    session = seeded.scalars(
        select(LessonSession).where(LessonSession.lesson_id == NEXT_LESSON)
    ).one()
    assert session.ended_at is not None
    summary = {k: v for k, v in (session.result or {}).items() if k != "rewards"}
    assert summary == {"outcome": "completed", "total": 6, "correct": 6, "incorrect": 0}
    assert session.xp_awarded == 10  # first completion of the lesson
    assert session.result is not None and session.result["rewards"]["xp_awarded"] == 10


def test_lesson_completes_with_mistakes_while_hearts_remain(seeded: Session, learner: User) -> None:
    results = play_lesson(seeded, learner, NEXT_LESSON, wrong_at={0, 5})  # last one wrong too
    assert results[-1].progress.status is SessionStatus.COMPLETED
    assert results[-1].hearts.current == 1
    assert results[-1].failure_reason is None
    completion = seeded.scalars(
        select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
    ).one()
    assert completion.best_mistakes == 2


def test_losing_the_last_heart_fails_the_lesson(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    results = [answer(seeded, learner, started.session_id, correct=False) for _ in range(3)]
    assert [r.hearts.current for r in results] == [2, 1, 0]
    assert results[-1].progress.status is SessionStatus.FAILED
    assert results[-1].failure_reason == "out_of_hearts"
    assert count(seeded, LessonCompletion, LessonCompletion.lesson_id == NEXT_LESSON) == 0
    session = seeded.get(LessonSession, started.session_id)
    assert session is not None and session.ended_at is not None
    assert session.result is not None and session.result["outcome"] == "failed"


def test_failed_session_cannot_continue(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    for _ in range(3):
        answer(seeded, learner, started.session_id, correct=False)
    session = seeded.get(LessonSession, started.session_id)
    assert session is not None
    next_id = session.exercise_ids[3]
    with pytest.raises(AppError) as excinfo:
        answer(seeded, learner, started.session_id, correct=True, exercise_id=next_id)
    assert error_code(excinfo) == "SESSION_NOT_ACTIVE"
    assert excinfo.value.details == {"status": "failed"}
    with pytest.raises(AppError, match="failed"):
        lesson_service.get_current_exercise(seeded, learner, started.session_id)
    with pytest.raises(AppError) as no_hearts:
        lesson_service.start_lesson(seeded, learner, NEXT_LESSON)  # and can't restart
    assert error_code(no_hearts) == "NO_HEARTS"


def test_completed_session_cannot_continue(seeded: Session, learner: User) -> None:
    play_lesson(seeded, learner, NEXT_LESSON, wrong_at=set())
    session = seeded.scalars(
        select(LessonSession).where(LessonSession.lesson_id == NEXT_LESSON)
    ).one()
    with pytest.raises(AppError) as excinfo:
        lesson_service.get_current_exercise(seeded, learner, session.id)
    assert error_code(excinfo) == "SESSION_NOT_ACTIVE"
    state = lesson_service.get_session_state(seeded, learner, session.id)
    assert state.current_exercise is None and state.progress.status is SessionStatus.COMPLETED


def test_repeating_the_final_answer_does_not_complete_twice(seeded: Session, learner: User) -> None:
    results = play_lesson(seeded, learner, NEXT_LESSON, wrong_at=set())
    session = seeded.scalars(
        select(LessonSession).where(LessonSession.lesson_id == NEXT_LESSON)
    ).one()
    last_id = session.exercise_ids[-1]
    for _ in range(3):
        repeat = answer(seeded, learner, session.id, correct=True, exercise_id=last_id)
        assert repeat.replayed and repeat.progress == results[-1].progress
    completion = seeded.scalars(
        select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
    ).one()
    assert completion.times_completed == 1


def test_replaying_a_completed_lesson_updates_the_same_completion(
    seeded: Session, learner: User
) -> None:
    play_lesson(seeded, learner, NEXT_LESSON, wrong_at={1})
    play_lesson(seeded, learner, NEXT_LESSON, wrong_at=set())
    rows = seeded.scalars(
        select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
    ).all()
    assert len(rows) == 1
    assert (rows[0].times_completed, rows[0].best_mistakes) == (2, 0)


def test_abandon(seeded: Session, learner: User) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    first = lesson_service.abandon_session(seeded, learner, started.session_id)
    second = lesson_service.abandon_session(seeded, learner, started.session_id)  # idempotent
    assert first.progress.status is second.progress.status is SessionStatus.ABANDONED
    assert first.current_exercise is None


# --------------------------------------------------------------------------- hearts


def test_lose_heart_never_goes_below_zero() -> None:
    user = User(username="h", display_name="H", hearts=1, hearts_updated_at=NOW)
    lose_heart(user, NOW)
    lose_heart(user, NOW)
    assert user.hearts == 0


def test_lose_heart_starts_the_regeneration_clock_only_from_full() -> None:
    later = NOW + timedelta(hours=1)
    user = User(username="h", display_name="H", hearts=5, hearts_updated_at=NOW)
    lose_heart(user, later)
    assert (user.hearts, user.hearts_updated_at) == (4, later)
    lose_heart(user, later + regeneration_interval() / 3)  # less than one interval later
    assert (user.hearts, user.hearts_updated_at) == (3, later)  # anchor kept


# --------------------------------------------------------------------------- ownership


def test_sessions_are_private(seeded: Session, learner: User, newbie: User) -> None:
    theirs = lesson_service.start_lesson(seeded, newbie, 1)
    for call in (
        lambda: lesson_service.get_session_state(seeded, learner, theirs.session_id),
        lambda: lesson_service.get_current_exercise(seeded, learner, theirs.session_id),
        lambda: lesson_service.abandon_session(seeded, learner, theirs.session_id),
    ):
        with pytest.raises(AppError) as excinfo:
            call()
        assert error_code(excinfo) == "SESSION_NOT_FOUND"
    with pytest.raises(AppError, match="Session not found"):
        answer(seeded, learner, theirs.session_id, correct=True, exercise_id=1)


# --------------------------------------------------------------------------- races


def test_concurrent_identical_submissions_are_graded_once(
    engine: Engine, seeded: Session, learner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = lesson_service.start_lesson(seeded, learner, NEXT_LESSON)
    assert started.current_exercise is not None
    ex = exercise(seeded, started.current_exercise.id)
    body = AnswerRequest.model_validate({"exercise_id": ex.id, "answer": wrong_answer(ex)})

    # Hold both requests after grading until both have read the same session state,
    # so they really race to insert the answer.
    barrier = threading.Barrier(2, timeout=10)
    calls, calls_lock = [0], threading.Lock()
    real_grade = grading.grade

    def racing_grade(*args: Any, **kwargs: Any) -> grading.Grade:
        result = real_grade(*args, **kwargs)
        with calls_lock:
            calls[0] += 1
            first_two = calls[0] <= 2
        if first_two:
            barrier.wait()
        return result

    monkeypatch.setattr(grading, "grade", racing_grade)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    results: list[AnswerResult] = []
    errors: list[BaseException] = []

    def submit() -> None:
        with factory() as db:
            try:
                user = db.get(User, learner.id)
                assert user is not None
                results.append(lesson_service.submit_answer(db, user, started.session_id, body))
            except BaseException as error:  # collected and asserted below
                errors.append(error)

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert sorted(r.replayed for r in results) == [False, True]
    assert {r.hearts.current for r in results} == {2}
    with factory() as check:
        assert count(check, SessionAnswer, SessionAnswer.session_id == started.session_id) == 1
        user = check.get(User, learner.id)
        assert user is not None and user.hearts == 2  # one heart, not two
