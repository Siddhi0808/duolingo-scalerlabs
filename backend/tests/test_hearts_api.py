"""Hearts over HTTP with a controllable clock, the mock refill, and concurrency."""

import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.api.routers import hearts as hearts_router
from app.core.clock import utc_now
from app.main import app
from app.models import Exercise, LessonSession, SessionAnswer, User, XpEvent
from app.schemas.lesson import AnswerRequest
from app.services import hearts, lesson_service, profile_service
from tests.factories import set_hearts
from tests.lesson_helpers import right_answer, wrong_answer

T0 = datetime(2026, 9, 25, 6, 30, tzinfo=UTC)  # 12:00 IST on the seed day
MIN = timedelta(minutes=1)
NEXT_LESSON = 8


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    frozen = Clock(T0)
    for module in (lesson_service, profile_service, hearts_router):
        monkeypatch.setattr(module, "utc_now", frozen)
    return frozen


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(factory: sessionmaker[Session], seeded: Session, clock: Clock) -> Iterator[TestClient]:
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


def hearts_in_db(factory: sessionmaker[Session]) -> tuple[int, int]:
    with factory() as db:
        learner = db.scalars(select(User).where(User.username == "learner")).one()
        return learner.hearts, learner.gems


def exercise(factory: sessionmaker[Session], exercise_id: int) -> Exercise:
    with factory() as db:
        found = db.get(Exercise, exercise_id)
        assert found is not None
        return found


def answer_current(
    client: TestClient, factory: sessionmaker[Session], session_id: str, *, correct: bool
) -> Any:
    current = client.get(f"/api/v1/sessions/{session_id}/current").json()
    ex = exercise(factory, current["id"])
    return client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"exercise_id": ex.id, "answer": right_answer(ex) if correct else wrong_answer(ex)},
    )


# --------------------------------------------------------------------------- reads


def test_every_endpoint_reports_the_same_effective_hearts(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    set_hearts(seeded, "learner", 3, T0 - 45 * MIN)  # 45 minutes ago
    expected = {
        "current": 4,
        "max": 5,
        "regenerating": True,
        "seconds_until_next": 15 * 60,
        "refill_cost_gems": 350,
    }
    assert client.get("/api/v1/me").json()["hearts"] == expected
    started = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").json()
    assert started["hearts"] == expected
    state = client.get(f"/api/v1/sessions/{started['session_id']}").json()
    assert state["hearts"] == expected
    answered = answer_current(client, factory, started["session_id"], correct=True).json()
    assert answered["hearts"] == expected
    assert hearts_in_db(factory)[0] == 3  # reads never wrote the regenerated value


def test_me_regenerates_over_time(client: TestClient, seeded: Session, clock: Clock) -> None:
    set_hearts(seeded, "learner", 3, T0)
    readings = []
    for _ in range(5):
        heart_view = client.get("/api/v1/me").json()["hearts"]
        readings.append((heart_view["current"], heart_view["seconds_until_next"]))
        clock.advance(15 * MIN)
    assert readings == [(3, 1800), (3, 900), (4, 1800), (4, 900), (5, None)]


def test_session_state_shows_regeneration(
    client: TestClient, seeded: Session, clock: Clock
) -> None:
    set_hearts(seeded, "learner", 2, T0)
    session_id = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").json()["session_id"]
    clock.advance(30 * MIN)
    assert client.get(f"/api/v1/sessions/{session_id}").json()["hearts"]["current"] == 3


# --------------------------------------------------------------------------- start / answer


def test_start_is_blocked_at_zero_hearts_then_allowed_after_regeneration(
    client: TestClient, seeded: Session, clock: Clock
) -> None:
    set_hearts(seeded, "learner", 0, T0)
    blocked = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start")
    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "NO_HEARTS"
    assert error["details"]["hearts"]["seconds_until_next"] == 1800
    clock.advance(29 * MIN)
    assert client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").status_code == 409
    clock.advance(1 * MIN)
    started = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start")
    assert started.status_code == 200 and started.json()["hearts"]["current"] == 1


def test_answer_uses_regenerated_hearts(
    client: TestClient, factory: sessionmaker[Session], seeded: Session, clock: Clock
) -> None:
    set_hearts(seeded, "learner", 1, T0)
    session_id = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").json()["session_id"]
    clock.advance(30 * MIN)  # 1 -> 2 hearts, so one mistake no longer fails the lesson
    wrong = answer_current(client, factory, session_id, correct=False).json()
    assert wrong["progress"]["status"] == "active"
    assert wrong["hearts"]["current"] == 1
    # Persisted atomically with the loss: regenerated to 2 at T0+30, then lost one; the
    # anchor stays at T0+30 (the interval that was in progress).
    with factory() as db:
        learner = db.scalars(select(User).where(User.username == "learner")).one()
        assert (learner.hearts, learner.hearts_updated_at) == (1, T0 + 30 * MIN)


def test_answering_with_zero_effective_hearts_is_refused(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    session_id = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").json()["session_id"]
    set_hearts(seeded, "learner", 0, T0)  # e.g. changed outside this session
    response = answer_current(client, factory, session_id, correct=True)
    assert response.status_code == 409 and response.json()["error"]["code"] == "NO_HEARTS"
    with factory() as db:
        count = select(func.count()).select_from(SessionAnswer)
        assert db.scalar(count.where(SessionAnswer.session_id == session_id)) == 0


def test_failing_on_the_last_heart_awards_nothing(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    set_hearts(seeded, "learner", 1, T0)
    with factory() as db:
        xp_before = db.scalar(select(func.count()).select_from(XpEvent))
    session_id = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").json()["session_id"]
    failed = answer_current(client, factory, session_id, correct=False).json()
    assert failed["progress"]["status"] == "failed" and failed["rewards"] is None
    assert failed["hearts"]["current"] == 0 and failed["hearts"]["seconds_until_next"] == 1800
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(XpEvent)) == xp_before
        learner = db.scalars(select(User).where(User.username == "learner")).one()
        assert (learner.xp_total, learner.streak_count) == (80, 6)


# --------------------------------------------------------------------------- refill


@pytest.mark.parametrize("start_hearts", [0, 3])
def test_refill_from_zero_or_partial(
    client: TestClient, factory: sessionmaker[Session], seeded: Session, start_hearts: int
) -> None:
    set_hearts(seeded, "learner", start_hearts, T0)
    body = client.post("/api/v1/hearts/refill").json()
    assert body["refilled"] is True and body["gems_spent"] == 350 and body["gems"] == 250
    assert body["hearts"]["current"] == 5 and body["hearts"]["regenerating"] is False
    assert hearts_in_db(factory) == (5, 250)


def test_refill_at_full_hearts_is_a_free_no_op(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    first = client.post("/api/v1/hearts/refill").json()  # seeded learner has 5/5
    second = client.post("/api/v1/hearts/refill").json()
    for body in (first, second):
        assert (body["refilled"], body["gems_spent"], body["gems"]) == (False, 0, 600)
    assert hearts_in_db(factory) == (5, 600)


def test_refill_counts_regenerated_hearts_first(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    set_hearts(seeded, "learner", 3, T0 - 90 * MIN)  # regenerated to 5 by now
    body = client.post("/api/v1/hearts/refill").json()
    assert body["refilled"] is False and body["gems"] == 600  # nothing to buy
    assert hearts_in_db(factory) == (5, 600)


def test_refill_is_idempotent_and_never_exceeds_max(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    set_hearts(seeded, "learner", 2, T0)
    results = [client.post("/api/v1/hearts/refill").json() for _ in range(3)]
    assert [r["refilled"] for r in results] == [True, False, False]
    assert all(r["hearts"]["current"] == 5 for r in results)
    assert hearts_in_db(factory) == (5, 250)  # charged once


def test_refill_without_enough_gems(
    client: TestClient, factory: sessionmaker[Session], seeded: Session
) -> None:
    learner = set_hearts(seeded, "learner", 1, T0)
    learner.gems = 100
    seeded.commit()
    response = client.post("/api/v1/hearts/refill")
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "INSUFFICIENT_GEMS",
        "message": "Not enough gems to refill hearts.",
        "details": {"cost": 350, "gems": 100},
    }
    assert hearts_in_db(factory) == (1, 100)


def test_refill_then_start_a_lesson(client: TestClient, seeded: Session) -> None:
    set_hearts(seeded, "learner", 0, T0)
    assert client.post(f"/api/v1/lessons/{NEXT_LESSON}/start").status_code == 409
    client.post("/api/v1/hearts/refill")
    started = client.post(f"/api/v1/lessons/{NEXT_LESSON}/start")
    assert started.status_code == 200 and started.json()["hearts"]["current"] == 5


def test_refill_does_not_change_the_path(client: TestClient, seeded: Session) -> None:
    before = client.get("/api/v1/path").json()
    set_hearts(seeded, "learner", 0, T0)
    client.post("/api/v1/hearts/refill")
    assert client.get("/api/v1/path").json() == before


# --------------------------------------------------------------------------- concurrency


def race(monkeypatch: pytest.MonkeyPatch, *actions: Any) -> list[BaseException]:
    """Run actions in parallel threads, holding each at hearts.materialize until all have
    read the learner row, so they genuinely race to write it."""
    barrier = threading.Barrier(len(actions), timeout=10)
    calls, lock = [0], threading.Lock()
    real_materialize = hearts.materialize

    def racing_materialize(user: User, now: datetime) -> None:
        real_materialize(user, now)
        with lock:
            calls[0] += 1
            first_round = calls[0] <= len(actions)
        if first_round:
            barrier.wait()

    monkeypatch.setattr(hearts, "materialize", racing_materialize)
    errors: list[BaseException] = []

    def run(action: Any) -> None:
        try:
            action()
        except BaseException as error:  # collected and asserted by the caller
            errors.append(error)

    threads = [threading.Thread(target=run, args=(action,)) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def test_concurrent_refills_charge_once(
    factory: sessionmaker[Session], seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_hearts(seeded, "learner", 1, utc_now())
    outcomes: list[bool] = []

    def refill() -> None:
        with factory() as db:
            learner = db.scalars(select(User).where(User.username == "learner")).one()
            outcomes.append(hearts.refill(db, learner, utc_now()).refilled)

    assert race(monkeypatch, refill, refill) == []
    assert sorted(outcomes) == [False, True]
    assert hearts_in_db(factory) == (5, 250)


def test_refill_committed_between_an_answers_read_and_write_is_not_lost(
    factory: sessionmaker[Session], seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force the dangerous interleaving deterministically:

        answer: reads learner (3 hearts, version v)
        refill: reads learner, charges 350 gems, sets 5 hearts, commits (version v+1)
        answer: grades wrong, writes hearts from its stale read

    Without the optimistic lock the answer would write 2 hearts over the refill (gems
    charged, hearts lost). With it, the answer's UPDATE matches no row (StaleDataError),
    is rolled back and retried from fresh state: 5 - 1 = 4 hearts.
    """
    set_hearts(seeded, "learner", 3, utc_now())
    learner = seeded.scalars(select(User).where(User.username == "learner")).one()
    session_id = lesson_service.start_lesson(seeded, learner, NEXT_LESSON).session_id
    session = seeded.get(LessonSession, session_id)
    assert session is not None
    first = exercise(factory, session.exercise_ids[0])
    request = AnswerRequest.model_validate({"exercise_id": first.id, "answer": wrong_answer(first)})

    answer_has_read, refill_done = threading.Event(), threading.Event()
    real_require_hearts = lesson_service._require_hearts
    first_call = [True]

    def pause_after_read(user: User, now: datetime) -> None:
        real_require_hearts(user, now)
        if first_call[0]:  # only the first attempt waits; the retry runs straight through
            first_call[0] = False
            answer_has_read.set()
            assert refill_done.wait(timeout=10)

    monkeypatch.setattr(lesson_service, "_require_hearts", pause_after_read)
    errors: list[BaseException] = []

    def answer() -> None:
        try:
            with factory() as db:
                user = db.scalars(select(User).where(User.username == "learner")).one()
                result = lesson_service.submit_answer(db, user, session_id, request)
                assert result.hearts.current == 4
        except BaseException as error:  # asserted below
            errors.append(error)

    def refill() -> None:
        try:
            assert answer_has_read.wait(timeout=10)
            with factory() as db:
                user = db.scalars(select(User).where(User.username == "learner")).one()
                assert hearts.refill(db, user, utc_now()).refilled
        except BaseException as error:  # asserted below
            errors.append(error)
        finally:
            refill_done.set()

    threads = [threading.Thread(target=answer), threading.Thread(target=refill)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert hearts_in_db(factory) == (4, 250)  # refill kept, then one heart lost
    with factory() as db:
        count = select(func.count()).select_from(SessionAnswer)
        assert db.scalar(count.where(SessionAnswer.session_id == session_id)) == 1


def test_optimistic_locking_retry_recovers_from_concurrent_mutation(
    factory: sessionmaker[Session], seeded: Session
) -> None:
    """Two independent sessions load the same user state.
    Session 1 commits a mutation (incrementing version).
    Session 2 calls refill(), raising StaleDataError on commit,
    which is caught and successfully retried with refreshed state.
    """
    set_hearts(seeded, "learner", 3, utc_now())

    with factory() as db1, factory() as db2:
        u1 = db1.scalars(select(User).where(User.username == "learner")).one()
        u2 = db2.scalars(select(User).where(User.username == "learner")).one()
        assert u1.version == u2.version
        initial_version = u1.version

        # db1 mutates and commits
        u1.gems -= 50
        db1.commit()
        assert u1.version == initial_version + 1

        # db2 attempts refill using stale u2 (u2 has initial_version)
        now = utc_now()
        res = hearts.refill(db2, u2, now)
        assert res.refilled is True
        # 600 - 50 (db1) - 350 (refill) = 200 gems
        assert res.gems == 200
        assert u2.hearts == 5

    with factory() as db:
        final_user = db.scalars(select(User).where(User.username == "learner")).one()
        assert final_user.gems == 200
        assert final_user.hearts == 5
        assert final_user.version == initial_version + 2
