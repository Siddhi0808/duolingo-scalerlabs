"""Calendar-day streak rules. Pure functions: dates in, dates and counts out.

A streak counts consecutive *local calendar days* with at least one qualifying
activity (an XP-earning lesson completion). It never looks at hours: finishing at
23:50 and again at 00:10 the next local day is two days, while 00:10 and 23:50 on
the same day is one.

advance(state, day)   applied when qualifying activity happens on local date `day`
  no previous activity       -> current = 1
  day == last day            -> unchanged (already counted today)
  day == last day + 1        -> current + 1
  day >  last day + 1        -> current = 1 (one or more days were missed)
  day <  last day            -> unchanged (a clock/timezone change must not rewind)
  longest = max(longest, current); last day = max(last day, day)

displayed(state, today)   the streak to *show*, derived on read without writing:
  the stored current streak if the last active day is today or yesterday, else 0.
  (A streak is only "broken" once a whole local day has passed without activity.)
"""

from dataclasses import dataclass
from datetime import date, timedelta

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class StreakState:
    current: int
    longest: int
    last_date: date | None


def advance(state: StreakState, day: date) -> StreakState:
    last = state.last_date
    if last is not None and day <= last:
        return state
    current = state.current + 1 if last is not None and day == last + ONE_DAY else 1
    return StreakState(current=current, longest=max(state.longest, current), last_date=day)


def displayed(state: StreakState, today: date) -> int:
    if state.last_date is None or state.last_date < today - ONE_DAY:
        return 0
    return state.current


def extended_today(state: StreakState, today: date) -> bool:
    return state.last_date == today
