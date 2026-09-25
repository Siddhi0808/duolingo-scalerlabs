"""GET /api/v1/path over HTTP, against a seeded temporary database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.main import app
from app.schemas.path import PathResponse

FORBIDDEN_KEYS = {
    "exercises",
    "exercise",
    "payload",
    "solution",
    "prompt",
    "options",
    "tiles",
    "correct_option_id",
    "accepted",
    "pairs",
}


@pytest.fixture
def client(engine: Engine, seeded: Session) -> Iterator[TestClient]:
    """App wired to the seeded test database instead of backend/lingo.db."""
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def test_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db
            db.commit()

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in all_keys(v)}
    return set()


def test_path_returns_the_seeded_learners_state(client: TestClient) -> None:
    response = client.get("/api/v1/path")
    assert response.status_code == 200
    body = response.json()
    assert body["course"]["slug"] == "es-from-en"
    assert [u["state"] for u in body["units"]] == ["in_progress", "locked", "locked"]
    skills = [s for u in body["units"] for s in u["skills"]]
    assert [s["state"] for s in skills] == ["completed", "completed", "in_progress"] + [
        "locked"
    ] * 6
    assert body["current_skill_id"] == skills[2]["id"]


def test_response_validates_against_the_schema(client: TestClient) -> None:
    body = client.get("/api/v1/path").json()
    parsed = PathResponse.model_validate(body)  # extra="forbid": no unexpected fields
    assert len(parsed.units) == 3
    assert sum(len(u.skills) for u in parsed.units) == 9


def test_no_exercise_content_or_solutions_are_exposed(client: TestClient) -> None:
    body = client.get("/api/v1/path").json()
    assert not all_keys(body) & FORBIDDEN_KEYS
    text = client.get("/api/v1/path").text
    assert "correct_option_id" not in text and "accepted" not in text


def test_locked_lessons_expose_metadata_only(client: TestClient) -> None:
    body = client.get("/api/v1/path").json()
    locked = [
        lesson
        for unit in body["units"]
        for skill in unit["skills"]
        for lesson in skill["lessons"]
        if lesson["state"] == "locked"
    ]
    assert locked, "seeded learner has locked lessons"
    assert all(set(lesson) == {"id", "position", "title", "state"} for lesson in locked)


def test_no_endpoint_serves_lesson_exercises(client: TestClient) -> None:
    # Exercises are only reachable one at a time through a session (M4), never per lesson.
    paths = set(client.get("/api/v1/openapi.json").json()["paths"])
    assert paths == {
        "/api/v1/health",
        "/api/v1/path",
        "/api/v1/lessons/{lesson_id}/start",
        "/api/v1/sessions/{session_id}",
        "/api/v1/sessions/{session_id}/current",
        "/api/v1/sessions/{session_id}/answer",
        "/api/v1/sessions/{session_id}/abandon",
        "/api/v1/me",
        "/api/v1/leaderboard",
        "/api/v1/hearts/refill",
    }
    assert client.get("/api/v1/lessons/8").status_code == 404
    assert client.get("/api/v1/lessons/12/exercises").status_code == 404


def test_missing_learner_returns_a_clear_error(client: TestClient, seeded: Session) -> None:
    seeded.execute(text("UPDATE users SET username = 'renamed' WHERE id = 1"))
    seeded.commit()
    response = client.get("/api/v1/path")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LEARNER_NOT_FOUND"
