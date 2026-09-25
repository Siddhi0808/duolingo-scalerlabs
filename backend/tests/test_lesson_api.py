"""Lesson engine over HTTP: security, error envelope, transactions, full playthrough."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.core.clock import utc_now
from app.main import app
from app.models import Exercise, LessonCompletion, LessonSession, SessionAnswer, User
from app.schemas.lesson import AnswerResult, PublicExercise, SessionState, StartSessionResponse
from app.services import lesson_service
from tests.factories import set_hearts
from tests.lesson_helpers import right_answer, wrong_answer

NEXT_LESSON, LOCKED_LESSON = 8, 12

# Keys that would mean an answer key left the server (checked in every response body).
SOLUTION_KEYS = {"solution", "correct_option_id", "accepted", "pairs", "pair_key", "is_correct"}


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def three_hearts(seeded: Session) -> None:
    """The learner starts these tests with 3 hearts as of now (real clock)."""
    set_hearts(seeded, "learner", 3, utc_now())


@pytest.fixture
def client(factory: sessionmaker[Session], seeded: Session) -> Iterator[TestClient]:
    """The app on the seeded test DB, using the real get_db (commit/rollback) logic."""

    def test_db() -> Iterator[Session]:
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in all_keys(v)}
    return set()


def exercise(factory: sessionmaker[Session], exercise_id: int) -> Exercise:
    with factory() as db:
        found = db.get(Exercise, exercise_id)
        assert found is not None
        return found


def post_answer(client: TestClient, session_id: str, exercise_id: int, answer: Any) -> Any:
    return client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"exercise_id": exercise_id, "answer": answer},
    )


def start(client: TestClient, lesson_id: int = NEXT_LESSON) -> dict[str, Any]:
    response = client.post(f"/api/v1/lessons/{lesson_id}/start")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --------------------------------------------------------------------------- integration


def test_play_a_whole_seeded_lesson(client: TestClient, factory: sessionmaker[Session]) -> None:
    started = start(client)
    StartSessionResponse.model_validate(started)
    session_id = started["session_id"]
    bodies: list[Any] = [started]
    served: list[int] = []

    while True:
        current = client.get(f"/api/v1/sessions/{session_id}/current")
        if current.status_code == 409:
            assert current.json()["error"]["code"] == "SESSION_NOT_ACTIVE"
            break
        exercise_json = PublicExercise.model_validate(current.json())
        bodies.append(current.json())
        served.append(exercise_json.id)
        ex = exercise(factory, exercise_json.id)
        result = post_answer(client, session_id, ex.id, right_answer(ex))
        assert result.status_code == 200, result.text
        AnswerResult.model_validate(result.json())
        bodies.append(result.json())

    with factory() as db:
        session = db.get(LessonSession, session_id)
        assert session is not None
        assert served == session.exercise_ids  # served one at a time, in order
        assert served == sorted(served)
        completion = db.scalars(
            select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
        ).one()
        assert completion.times_completed == 1

    assert bodies[-1]["progress"] == {
        "status": "completed",
        "total": 6,
        "answered": 6,
        "correct": 6,
        "incorrect": 0,
    }
    state = client.get(f"/api/v1/sessions/{session_id}").json()
    SessionState.model_validate(state)
    assert state["current_exercise"] is None

    # The path now shows Basic Words completed and unit 2's first skill unlocked.
    path = client.get("/api/v1/path").json()
    skills = [skill for unit in path["units"] for skill in unit["skills"]]
    assert [s["state"] for s in skills[:4]] == ["completed", "completed", "completed", "available"]
    assert path["units"][0]["state"] == "completed"
    assert path["current_skill_id"] == skills[3]["id"]

    for body in bodies:  # nothing in the whole playthrough leaked an answer key
        assert not all_keys(body) & SOLUTION_KEYS


def test_matching_payload_hides_the_pairing(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    session_id = start(client)["session_id"]
    for _ in range(2):  # lesson 8: multiple choice, fill blank, then matching pairs
        current = client.get(f"/api/v1/sessions/{session_id}/current").json()
        post_answer(
            client, session_id, current["id"], right_answer(exercise(factory, current["id"]))
        )
    matching = client.get(f"/api/v1/sessions/{session_id}/current").json()
    assert matching["type"] == "matching_pairs"
    assert set(matching) == {"id", "type", "position", "prompt", "payload"}
    assert set(matching["payload"]) == {"left", "right"}
    for item in matching["payload"]["left"] + matching["payload"]["right"]:
        assert set(item) == {"id", "text"}


# --------------------------------------------------------------------------- access


def test_locked_lesson_returns_403_and_no_exercises(client: TestClient) -> None:
    response = client.post(f"/api/v1/lessons/{LOCKED_LESSON}/start")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "LESSON_LOCKED"
    assert "current_exercise" not in body and "payload" not in all_keys(body)


def test_unknown_lesson_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/lessons/9999/start")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LESSON_NOT_FOUND"


def test_another_learners_session_looks_nonexistent(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    with factory() as db:
        other = User(username="someone", display_name="Someone", current_course_id=1)
        db.add(other)
        db.commit()
        theirs = lesson_service.start_lesson(db, other, 1).session_id

    missing = client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
    for response in (
        client.get(f"/api/v1/sessions/{theirs}"),
        client.get(f"/api/v1/sessions/{theirs}/current"),
        post_answer(client, theirs, 1, {"type": "multiple_choice", "option_id": "a"}),
        client.post(f"/api/v1/sessions/{theirs}/abandon"),
    ):
        assert response.status_code == 404
        assert response.json() == missing.json()  # indistinguishable from "no such session"
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"


# --------------------------------------------------------------------------- tampering


@pytest.mark.parametrize(
    "body",
    [
        {
            "exercise_id": 38,
            "correct": True,
            "answer": {"type": "multiple_choice", "option_id": "a"},
        },
        {
            "exercise_id": 38,
            "answer": {"type": "multiple_choice", "option_id": "a", "correct": True},
        },
        {"exercise_id": 38, "position": 5, "answer": {"type": "multiple_choice", "option_id": "a"}},
        {"exercise_id": 38, "answer": {"type": "essay", "text": "hola"}},
        {"exercise_id": 38, "answer": {"type": "multiple_choice"}},
    ],
)
def test_malformed_or_tampered_requests_are_rejected(
    client: TestClient, factory: sessionmaker[Session], body: dict[str, Any]
) -> None:
    session_id = start(client)["session_id"]
    response = client.post(f"/api/v1/sessions/{session_id}/answer", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SessionAnswer)
                .where(SessionAnswer.session_id == session_id)
            )
            == 0
        )


def test_cannot_jump_to_a_later_exercise(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    started = start(client)
    with factory() as db:
        session = db.get(LessonSession, started["session_id"])
        assert session is not None
        last = session.exercise_ids[-1]
    response = post_answer(
        client, started["session_id"], last, right_answer(exercise(factory, last))
    )
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "EXERCISE_NOT_CURRENT",
        "message": "That is not the current exercise.",
        "details": {"current_exercise_id": started["current_exercise"]["id"]},
    }


def test_invalid_answer_returns_422_without_cost(client: TestClient) -> None:
    started = start(client)
    current = started["current_exercise"]
    response = post_answer(
        client, started["session_id"], current["id"], {"type": "multiple_choice", "option_id": "z"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ANSWER"
    assert client.get(f"/api/v1/sessions/{started['session_id']}").json()["hearts"]["current"] == 3


# --------------------------------------------------------------------------- duplicates


def test_duplicate_submissions_over_http(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    started = start(client)
    ex = exercise(factory, started["current_exercise"]["id"])
    first = post_answer(client, started["session_id"], ex.id, wrong_answer(ex)).json()
    again = post_answer(client, started["session_id"], ex.id, wrong_answer(ex)).json()
    assert again == {**first, "replayed": True}
    changed = post_answer(client, started["session_id"], ex.id, right_answer(ex))
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "DUPLICATE_SUBMISSION"
    with factory() as db:
        user = db.scalars(select(User).where(User.username == "learner")).one()
        assert user.hearts == 2
        answers = select(func.count()).select_from(SessionAnswer)
        assert db.scalar(answers.where(SessionAnswer.session_id == started["session_id"])) == 1


def test_start_twice_returns_the_same_session(client: TestClient) -> None:
    first, second = start(client), start(client)
    assert second["session_id"] == first["session_id"] and second["resumed"] is True


def test_failed_session_rejects_answers(client: TestClient, factory: sessionmaker[Session]) -> None:
    session_id = start(client)["session_id"]
    for _ in range(3):  # seeded learner has 3 hearts
        current = client.get(f"/api/v1/sessions/{session_id}/current").json()
        last = post_answer(
            client, session_id, current["id"], wrong_answer(exercise(factory, current["id"]))
        )
    assert last.json()["failure_reason"] == "out_of_hearts"
    assert last.json()["progress"]["status"] == "failed"
    with factory() as db:
        session = db.get(LessonSession, session_id)
        assert session is not None
        next_id = session.exercise_ids[3]
    blocked = post_answer(client, session_id, next_id, right_answer(exercise(factory, next_id)))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SESSION_NOT_ACTIVE"
    restart = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start")
    assert restart.status_code == 409 and restart.json()["error"]["code"] == "NO_HEARTS"


# --------------------------------------------------------------------------- transactions


def test_failure_mid_answer_rolls_everything_back(
    client: TestClient, factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash while recording the completion of a *wrong* final answer: nothing persists."""
    started = start(client)
    session_id = started["session_id"]
    with factory() as db:
        session = db.get(LessonSession, session_id)
        assert session is not None
        ids = list(session.exercise_ids)
    for exercise_id in ids[:-1]:
        post_answer(client, session_id, exercise_id, right_answer(exercise(factory, exercise_id)))

    def explode(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(lesson_service, "_record_completion", explode)
    final = ids[-1]
    response = post_answer(client, session_id, final, wrong_answer(exercise(factory, final)))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "disk on fire" not in response.text  # internals are not leaked

    with factory() as db:  # grade, answer row, heart loss, session end: all rolled back
        session = db.get(LessonSession, session_id)
        assert session is not None
        assert session.status.value == "active" and session.ended_at is None
        assert session.mistakes_count == 0
        assert len(session.answers) == len(ids) - 1
        user = db.scalars(select(User).where(User.username == "learner")).one()
        assert user.hearts == 3
        assert (
            db.scalars(
                select(LessonCompletion).where(LessonCompletion.lesson_id == NEXT_LESSON)
            ).all()
            == []
        )

    monkeypatch.undo()  # the same request succeeds once the fault is gone
    retry = post_answer(client, session_id, final, wrong_answer(exercise(factory, final)))
    assert retry.status_code == 200
    assert retry.json()["progress"]["status"] == "completed"
    assert retry.json()["hearts"]["current"] == 2
