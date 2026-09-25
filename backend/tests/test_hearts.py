"""Heart regeneration: the pure rule, countdown, loss and materialization."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.models import User
from app.services.hearts import (
    HeartState,
    calculate_regenerated_hearts,
    effective,
    lose_heart,
    materialize,
    regeneration_interval,
    seconds_until_next_heart,
    status,
)

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)
INTERVAL = timedelta(minutes=30)


def regen(hearts: int, elapsed: timedelta, max_hearts: int = 5) -> HeartState:
    return calculate_regenerated_hearts(hearts, max_hearts, T0, T0 + elapsed, INTERVAL)


# --------------------------------------------------------------------------- the rule


def test_full_hearts_stay_full() -> None:
    assert regen(5, 10 * INTERVAL) == HeartState(5, T0)


@pytest.mark.parametrize("hearts", [0, 1, 3])
def test_no_elapsed_time_changes_nothing(hearts: int) -> None:
    assert regen(hearts, timedelta(0)) == HeartState(hearts, T0)


def test_clock_skew_is_treated_as_no_elapsed_time() -> None:
    assert regen(2, -5 * MIN) == HeartState(2, T0)


def test_less_than_one_interval_changes_nothing() -> None:
    assert regen(3, INTERVAL - timedelta(seconds=1)) == HeartState(3, T0)


def test_exactly_one_interval_adds_one_heart() -> None:
    assert regen(3, INTERVAL) == HeartState(4, T0 + INTERVAL)


def test_zero_and_one_hearts_regenerate() -> None:
    assert regen(0, INTERVAL) == HeartState(1, T0 + INTERVAL)
    assert regen(1, INTERVAL) == HeartState(2, T0 + INTERVAL)


def test_multiple_intervals_add_multiple_hearts() -> None:
    assert regen(1, 2 * INTERVAL + 10 * MIN) == HeartState(3, T0 + 2 * INTERVAL)


def test_exactly_enough_intervals_to_fill() -> None:
    assert regen(3, 2 * INTERVAL) == HeartState(5, T0 + 2 * INTERVAL)


def test_regeneration_stops_at_max() -> None:
    assert regen(0, 3 * 24 * 60 * MIN) == HeartState(5, T0 + 5 * INTERVAL)
    assert regen(4, 10 * INTERVAL).hearts == 5


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [(30 * MIN, 4), (60 * MIN, 5), (180 * MIN, 5)],  # the examples from the brief
)
def test_brief_examples(elapsed: timedelta, expected: int) -> None:
    assert regen(3, elapsed).hearts == expected


def test_partial_interval_is_preserved() -> None:
    """3 hearts at 12:00; at 12:45 -> 4 hearts, anchor 12:30, 15 minutes to go."""
    at_1245 = T0 + 45 * MIN
    state = calculate_regenerated_hearts(3, 5, T0, at_1245, INTERVAL)
    assert state == HeartState(4, T0 + 30 * MIN)  # not reset to 12:45
    assert seconds_until_next_heart(state, at_1245, 5, INTERVAL) == 15 * 60
    at_1300 = T0 + 60 * MIN
    assert calculate_regenerated_hearts(4, 5, state.anchor, at_1300, INTERVAL).hearts == 5


def test_regeneration_is_idempotent() -> None:
    once = regen(2, 45 * MIN)
    now = T0 + 45 * MIN
    again = calculate_regenerated_hearts(once.hearts, 5, once.anchor, now, INTERVAL)
    assert again == once  # re-applying at the same instant regenerates nothing more


# --------------------------------------------------------------------------- countdown


def test_seconds_until_next() -> None:
    assert seconds_until_next_heart(HeartState(5, T0), T0, 5, INTERVAL) is None
    assert seconds_until_next_heart(HeartState(2, T0), T0, 5, INTERVAL) == 1800
    halfway = T0 + timedelta(minutes=12, seconds=30, milliseconds=400)
    assert seconds_until_next_heart(HeartState(2, T0), halfway, 5, INTERVAL) == 1050  # ceil
    future_anchor = HeartState(2, T0 + 60 * MIN)  # never more than one interval
    assert seconds_until_next_heart(future_anchor, T0, 5, INTERVAL) == 1800


# --------------------------------------------------------------------------- user state


def user(hearts: int, anchor: datetime = T0) -> User:
    return User(username="u", display_name="U", hearts=hearts, hearts_updated_at=anchor)


def test_status_reports_effective_hearts() -> None:
    info = status(user(3), T0 + 45 * MIN)
    assert info.model_dump() == {
        "current": 4,
        "max": 5,
        "regenerating": True,
        "seconds_until_next": 900,
        "refill_cost_gems": 350,
    }
    full = status(user(5), T0)
    assert (full.current, full.regenerating, full.seconds_until_next) == (5, False, None)


def test_status_and_effective_do_not_write() -> None:
    learner = user(3)
    status(learner, T0 + 5 * INTERVAL)
    effective(learner, T0 + 5 * INTERVAL)
    assert (learner.hearts, learner.hearts_updated_at) == (3, T0)


def test_materialize_writes_the_regenerated_state_once() -> None:
    learner = user(3)
    materialize(learner, T0 + 45 * MIN)
    assert (learner.hearts, learner.hearts_updated_at) == (4, T0 + 30 * MIN)
    materialize(learner, T0 + 45 * MIN)  # same instant: nothing more
    assert (learner.hearts, learner.hearts_updated_at) == (4, T0 + 30 * MIN)


def test_losing_a_heart_from_full_starts_the_clock() -> None:
    learner = user(5)
    lose_heart(learner, T0 + 90 * MIN)
    assert (learner.hearts, learner.hearts_updated_at) == (4, T0 + 90 * MIN)


def test_losing_a_heart_while_regenerating_keeps_progress() -> None:
    learner = user(3)
    lose_heart(learner, T0 + 20 * MIN)  # 20 minutes into the interval
    assert (learner.hearts, learner.hearts_updated_at) == (2, T0)
    assert status(learner, T0 + 30 * MIN).current == 3  # 10 minutes later: +1


def test_losing_a_heart_applies_regeneration_first() -> None:
    learner = user(3)
    lose_heart(learner, T0 + 65 * MIN)  # regenerates to 5 first, then loses one
    assert (learner.hearts, learner.hearts_updated_at) == (4, T0 + 65 * MIN)


def test_hearts_never_go_below_zero() -> None:
    learner = user(0, T0)
    lose_heart(learner, T0)
    assert learner.hearts == 0


def test_interval_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    assert regeneration_interval() == timedelta(minutes=30)
    monkeypatch.setenv("HEART_REGEN_MINUTES", "1")
    get_settings.cache_clear()
    try:
        assert regeneration_interval() == timedelta(minutes=1)
    finally:
        monkeypatch.delenv("HEART_REGEN_MINUTES")
        get_settings.cache_clear()
