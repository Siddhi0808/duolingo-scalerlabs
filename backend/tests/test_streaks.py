"""Pure streak rules and the timestamp -> local calendar date conversion."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.clock import local_date
from app.services.streaks import StreakState, advance, displayed, extended_today

D = date(2026, 9, 25)
DAY = timedelta(days=1)


def state(current: int, longest: int, last: date | None) -> StreakState:
    return StreakState(current=current, longest=longest, last_date=last)


def test_first_activity_starts_a_streak_of_one() -> None:
    assert advance(state(0, 0, None), D) == state(1, 1, D)


def test_same_day_activity_does_not_increment() -> None:
    once = advance(state(0, 0, None), D)
    assert advance(once, D) == once
    assert advance(advance(once, D), D) == once  # several lessons on one day


def test_next_day_increments() -> None:
    assert advance(state(4, 9, D - DAY), D) == state(5, 9, D)


def test_one_missed_day_resets_to_one() -> None:
    assert advance(state(4, 9, D - 2 * DAY), D) == state(1, 9, D)


def test_many_missed_days_reset_to_one() -> None:
    assert advance(state(30, 30, D - 40 * DAY), D) == state(1, 30, D)


def test_longest_streak_tracks_the_maximum() -> None:
    streak = state(0, 0, None)
    for offset in range(5):  # five consecutive days
        streak = advance(streak, D + offset * DAY)
    assert (streak.current, streak.longest) == (5, 5)
    streak = advance(streak, D + 10 * DAY)  # gap
    assert (streak.current, streak.longest) == (1, 5)
    for offset in range(11, 17):  # six more days: new record
        streak = advance(streak, D + offset * DAY)
    assert (streak.current, streak.longest) == (7, 7)


def test_an_earlier_date_never_rewinds_the_streak() -> None:
    assert advance(state(3, 3, D), D - DAY) == state(3, 3, D)


@pytest.mark.parametrize(
    ("last", "shown"),
    [(None, 0), (D, 4), (D - DAY, 4), (D - 2 * DAY, 0), (D - 30 * DAY, 0)],
)
def test_displayed_streak_breaks_only_after_a_missed_day(last: date | None, shown: int) -> None:
    assert displayed(state(4, 8, last), D) == shown


def test_extended_today() -> None:
    assert extended_today(state(2, 2, D), D)
    assert not extended_today(state(2, 2, D - DAY), D)
    assert not extended_today(state(0, 0, None), D)


# --------------------------------------------------------------------------- time zones


@pytest.mark.parametrize(
    ("utc", "zone", "expected"),
    [
        # Kolkata is UTC+05:30: the local day changes at 18:30 UTC.
        (datetime(2026, 9, 25, 18, 29, 59, tzinfo=UTC), "Asia/Kolkata", date(2026, 9, 25)),
        (datetime(2026, 9, 25, 18, 30, tzinfo=UTC), "Asia/Kolkata", date(2026, 9, 26)),
        # Los Angeles is UTC-07:00 in September: still the previous day at 03:00 UTC.
        (datetime(2026, 9, 26, 3, 0, tzinfo=UTC), "America/Los_Angeles", date(2026, 9, 25)),
        (datetime(2026, 9, 26, 3, 0, tzinfo=UTC), "UTC", date(2026, 9, 26)),
        (datetime(2026, 9, 26, 3, 0, tzinfo=UTC), "Not/AZone", date(2026, 9, 26)),  # fallback
    ],
)
def test_local_date(utc: datetime, zone: str, expected: date) -> None:
    assert local_date(utc, zone) == expected


def test_local_date_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        local_date(datetime(2026, 9, 25, 12, 0), "UTC")


def test_timezone_boundary_decides_the_streak_day() -> None:
    """Two completions 30 minutes apart, on either side of Kolkata's midnight.

    In UTC both are on the 25th (one day); for a Kolkata learner they are the 25th and
    26th, so the streak grows. The learner's calendar is what counts.
    """
    before_midnight = datetime(2026, 9, 25, 18, 15, tzinfo=UTC)  # 23:45 IST
    after_midnight = datetime(2026, 9, 25, 18, 45, tzinfo=UTC)  # 00:15 IST next day
    streak = advance(state(0, 0, None), local_date(before_midnight, "Asia/Kolkata"))
    streak = advance(streak, local_date(after_midnight, "Asia/Kolkata"))
    assert streak.current == 2
    utc_only = advance(state(0, 0, None), before_midnight.date())
    assert advance(utc_only, after_midnight.date()).current == 1  # the wrong (UTC) answer
