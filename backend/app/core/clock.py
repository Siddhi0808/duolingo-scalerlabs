"""Time source and the one place timestamps become calendar dates.

Every stored timestamp is timezone-aware UTC. Anything that depends on "which day"
(streaks, daily XP) converts a timestamp to the *learner's* local calendar date with
`local_date`, never by taking the UTC date. Services accept an explicit `now` so the
rules can be tested at any instant, including around midnight.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_date(moment: datetime, timezone: str) -> date:
    """The calendar date of `moment` in `timezone` (IANA name, e.g. "Asia/Kolkata").

    2026-09-25T18:45Z is still the 25th in UTC but already the 26th in Kolkata (+05:30).
    An unknown zone falls back to UTC rather than failing a lesson completion.
    """
    if moment.tzinfo is None:
        raise ValueError("local_date needs a timezone-aware datetime")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return moment.astimezone(zone).date()
