"""Gamification over HTTP: /me, /leaderboard, the full reward flow, and transaction rollback.

The clock is frozen at 12:00 IST on the seed's reference day, so results do not depend
on the date the tests run.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.main import app
from app.models import (
    Exercise,
    LessonCompletion,
    LessonSession,
    User,
    UserAchievement,
    XpEvent,
)
from app.schemas.gamification import LeaderboardResponse, MeResponse
from app.services import achievement_service, lesson_service, profile_service
from tests.factories import set_hearts
from tests.lesson_helpers import right_answer, wrong_answer

FROZEN_NOW = datetime(2026, 9, 25, 6, 30, tzinfo=UTC)  # 12:00 IST on the seed day


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(
    factory: sessionmaker[Session], seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setattr(lesson_service, "utc_now", lambda: FROZEN_NOW)
    monkeypatch.setattr(profile_service, "utc_now", lambda: FROZEN_NOW)
    set_hearts(seeded, "learner", 3, FROZEN_NOW)

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


def exercise(factory: sessionmaker[Session], exercise_id: int) -> Exercise:
    with factory() as db:
        found = db.get(Exercise, exercise_id)
        assert found is not None
        return found


def play(
    client: TestClient, factory: sessionmaker[Session], lesson_id: int, *, all_wrong: bool = False
) -> tuple[str, list[dict[str, Any]]]:
    session_id = client.post(f"/api/v1/lessons/{lesson_id}/start").json()["session_id"]
    results: list[dict[str, Any]] = []
    while True:
        current = client.get(f"/api/v1/sessions/{session_id}/current")
        if current.status_code != 200:
            return session_id, results
        ex = exercise(factory, current.json()["id"])
        answer = wrong_answer(ex) if all_wrong else right_answer(ex)
        response = client.post(
            f"/api/v1/sessions/{session_id}/answer",
            json={"exercise_id": ex.id, "answer": answer},
        )
        assert response.status_code == 200, response.text
        results.append(response.json())


def snapshot(factory: sessionmaker[Session]) -> dict[str, Any]:
    with factory() as db:
        user = db.scalars(select(User).where(User.username == "learner")).one()

        def count(model: Any) -> int:
            return db.scalar(select(func.count()).select_from(model)) or 0

        return {
            "xp_total": user.xp_total,
            "streak": (user.streak_count, user.longest_streak, user.last_streak_date),
            "hearts": user.hearts,
            "xp_events": count(XpEvent),
            "completions": count(LessonCompletion),
            "achievements": count(UserAchievement),
        }


# --------------------------------------------------------------------------- /me


def test_me_summary_for_the_seeded_learner(client: TestClient) -> None:
    body = client.get("/api/v1/me").json()
    me = MeResponse.model_validate(body)
    assert (me.username, me.xp_total, me.gems) == ("learner", 80, 1500)
    assert me.today.isoformat() == "2026-09-25"
    assert (me.streak.current, me.streak.longest, me.streak.extended_today) == (6, 6, False)
    assert (me.hearts.current, me.hearts.max) == (3, 5)
    assert (me.daily_goal.goal_xp, me.daily_goal.today_xp, me.daily_goal.completed) == (
        20,
        0,
        False,
    )
    assert me.stats.model_dump() == {
        "lessons_completed": 7,
        "total_lessons": 22,
        "skills_completed": 2,
        "total_skills": 9,
        "perfect_lessons": 4,
    }
    by_code = {a.code: a for a in me.achievements}
    assert len(by_code) == 15
    assert {c for c, a in by_code.items() if a.unlocked} == {
        "scholar_1",
        "scholar_2",
        "conqueror_1",
        "wildfire_1",
    }
    assert (by_code["wildfire_2"].current, by_code["wildfire_2"].target) == (6, 7)
    assert (by_code["sage_1"].current, by_code["sage_1"].target) == (80, 100)


def test_me_does_not_expose_internal_fields(client: TestClient) -> None:
    body = client.get("/api/v1/me").json()
    for private in ("id", "user_id", "current_course_id", "hearts_updated_at", "is_bot"):
        assert private not in body
    assert all("id" not in a and "achievement_id" not in a for a in body["achievements"])


# --------------------------------------------------------------------------- leaderboard


def test_leaderboard_order_and_current_learner(client: TestClient) -> None:
    board = LeaderboardResponse.model_validate(client.get("/api/v1/leaderboard").json())
    xp = [entry.xp for entry in board.entries]
    assert xp == sorted(xp, reverse=True)
    assert [entry.rank for entry in board.entries] == list(range(1, 11))
    mine = [entry for entry in board.entries if entry.is_current_user]
    assert [(e.username, e.xp, e.rank) for e in mine] == [("learner", 80, 9)]
    assert board.current_user_rank == 9
    assert board.entries[0].username == "maria.garcia"  # bots appear
    assert sum(not e.is_current_user for e in board.entries) == 9


def test_leaderboard_ties_break_by_user_id(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    with factory() as db:
        db.add_all(
            [
                User(id=50, username="zed", display_name="Zed", xp_total=1000),
                User(id=40, username="amy", display_name="Amy", xp_total=1000),
            ]
        )
        db.commit()
    top = client.get("/api/v1/leaderboard").json()["entries"][:2]
    assert [(e["username"], e["rank"]) for e in top] == [("amy", 1), ("zed", 2)]  # id 40 first


def test_leaderboard_is_read_only(client: TestClient) -> None:
    before = client.get("/api/v1/leaderboard").json()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/v1/leaderboard").status_code == 405
    tampered = client.get("/api/v1/leaderboard", params={"xp": 99999, "username": "learner"})
    assert tampered.json() == before
    assert client.post("/api/v1/me", json={"xp_total": 99999}).status_code == 405


# --------------------------------------------------------------------------- full flow


def test_complete_replay_and_fail_over_http(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    me_before = client.get("/api/v1/me").json()
    assert client.get("/api/v1/leaderboard").json()["current_user_rank"] == 9

    # Complete lesson 8 successfully.
    session_id, results = play(client, factory, 8)
    final = results[-1]
    assert final["progress"]["status"] == "completed"
    rewards = final["rewards"]
    assert rewards["xp_awarded"] == 10 and rewards["xp_total"] == 90
    assert rewards["streak"] == {"before": 6, "after": 7, "longest": 7, "extended": True}
    assert rewards["daily_goal"] == {
        "goal_xp": 20,
        "today_xp": 10,
        "completed": False,
        "just_completed": False,
    }
    assert [a["code"] for a in rewards["new_achievements"]] == ["wildfire_2", "sharpshooter_1"]
    assert all(r["rewards"] is None for r in results[:-1])  # only the completing answer

    with factory() as db:
        assert db.scalars(select(LessonCompletion).where(LessonCompletion.lesson_id == 8)).one()
        event = db.scalars(select(XpEvent).where(XpEvent.session_id == session_id)).one()
        assert event.amount == 10

    me_after = client.get("/api/v1/me").json()
    assert me_after["xp_total"] == me_before["xp_total"] + 10
    assert me_after["streak"]["current"] == 7 and me_after["streak"]["extended_today"]
    assert me_after["daily_goal"]["today_xp"] == 10
    unlocked = {a["code"] for a in me_after["achievements"] if a["unlocked"]}
    assert {"wildfire_2", "sharpshooter_1"} <= unlocked
    assert client.get("/api/v1/leaderboard").json()["current_user_rank"] == 8  # passed diego_v

    # Replay the final answer: nothing doubles.
    state = snapshot(factory)
    with factory() as db:
        session = db.get(LessonSession, session_id)
        assert session is not None
        last = exercise(factory, session.exercise_ids[-1])
    replay = client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"exercise_id": last.id, "answer": right_answer(last)},
    ).json()
    assert replay["replayed"] and replay["rewards"] == rewards
    assert snapshot(factory) == state

    # Fail lesson 9: no completion, no XP, no streak change.
    before_fail = snapshot(factory)
    _, failed = play(client, factory, 9, all_wrong=True)
    assert failed[-1]["progress"]["status"] == "failed" and failed[-1]["rewards"] is None
    after_fail = snapshot(factory)
    assert after_fail == {**before_fail, "hearts": 0}

    # The path still shows lesson 8 completed.
    path = client.get("/api/v1/path").json()
    lessons = {
        lesson["id"]: lesson["state"]
        for unit in path["units"]
        for skill in unit["skills"]
        for lesson in skill["lessons"]
    }
    assert lessons[8] == "completed" and lessons[9] == "available"


# --------------------------------------------------------------------------- rollback


def test_failure_after_xp_event_rolls_back_everything(
    client: TestClient, factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash in achievement evaluation: after the completion, XP event, xp_total and
    streak were written (flushed) but before commit. None of it may survive."""
    before = snapshot(factory)
    written_before_crash: dict[str, Any] = {}
    real_evaluate = achievement_service.evaluate

    def crash(db: Session, user: User, *args: Any, **kwargs: Any) -> Any:
        written_before_crash["xp_events"] = db.scalar(select(func.count()).select_from(XpEvent))
        written_before_crash["xp_total"] = user.xp_total
        written_before_crash["streak"] = user.streak_count
        raise RuntimeError("achievement store unavailable")

    monkeypatch.setattr(achievement_service, "evaluate", crash)
    _, results = play_until_crash(client, factory, 8)
    assert results[-1].status_code == 500
    assert results[-1].json()["error"]["code"] == "INTERNAL_ERROR"

    # The crash really happened after XP and streak were applied in the transaction...
    assert written_before_crash == {
        "xp_events": before["xp_events"] + 1,
        "xp_total": before["xp_total"] + 10,
        "streak": 7,
    }
    # ...and none of it (nor the completion or the final answer) was committed.
    assert snapshot(factory) == before
    with factory() as db:
        session = db.scalars(select(LessonSession).where(LessonSession.lesson_id == 8)).one()
        assert session.status.value == "active" and session.xp_awarded == 0
        assert len(session.answers) == len(session.exercise_ids) - 1

    monkeypatch.setattr(achievement_service, "evaluate", real_evaluate)
    retry = client.post(
        f"/api/v1/sessions/{session.id}/answer",
        json={
            "exercise_id": session.exercise_ids[-1],
            "answer": right_answer(exercise(factory, session.exercise_ids[-1])),
        },
    )
    assert retry.status_code == 200 and retry.json()["rewards"]["xp_awarded"] == 10
    assert snapshot(factory)["xp_total"] == before["xp_total"] + 10


def play_until_crash(
    client: TestClient, factory: sessionmaker[Session], lesson_id: int
) -> tuple[str, list[Any]]:
    session_id = client.post(f"/api/v1/lessons/{lesson_id}/start").json()["session_id"]
    responses: list[Any] = []
    while True:
        current = client.get(f"/api/v1/sessions/{session_id}/current")
        if current.status_code != 200:
            return session_id, responses
        ex = exercise(factory, current.json()["id"])
        response = client.post(
            f"/api/v1/sessions/{session_id}/answer",
            json={"exercise_id": ex.id, "answer": right_answer(ex)},
        )
        responses.append(response)
        if response.status_code != 200:
            return session_id, responses
