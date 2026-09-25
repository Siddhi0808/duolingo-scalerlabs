"""What a successful lesson completion earns, applied in a fixed order.

Called by lesson_service inside the final answer's transaction, right after the
LessonCompletion row is written:

    1. XP        lesson_xp(first_completion) -> XpEvent + users.xp_total
    2. streak    only if XP was earned (a qualifying activity), on the learner's
                 local date: streaks.advance
    3. daily     today's XP re-summed from the ledger (not stored anywhere)
    4. achievements evaluated last, so they see the updated XP/streak/completions

Nothing here commits; the caller's single commit makes it all-or-nothing.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import local_date
from app.models import LessonSession, User, XpSource
from app.schemas.gamification import (
    AchievementBadge,
    CompletionRewards,
    DailyGoalChange,
    StreakChange,
)
from app.services import achievement_service, streaks, xp_service


def apply_lesson_completion(
    db: Session, user: User, session: LessonSession, first_completion: bool, now: datetime
) -> CompletionRewards:
    today = local_date(now, user.timezone)
    before = streaks.StreakState(user.streak_count, user.longest_streak, user.last_streak_date)
    xp_before_today = xp_service.xp_on_day(db, user.id, today)

    # 1. XP (none for replays of an already-completed lesson)
    amount = xp_service.lesson_xp(first_completion)
    if amount > 0:
        xp_service.award_xp(db, user, amount, XpSource.LESSON, now, session=session)
    session.xp_awarded = amount

    # 2. Streak: XP-earning activity on the learner's local calendar date
    after = streaks.advance(before, today) if amount > 0 else before
    user.streak_count, user.longest_streak = after.current, after.longest
    user.last_streak_date = after.last_date

    # 3. Daily goal, derived from the ledger
    today_xp = xp_before_today + amount
    goal = user.daily_goal_xp

    # 4. Achievements, after everything above is in place
    new_achievements = achievement_service.evaluate(db, user, today, now)

    return CompletionRewards(
        first_completion=first_completion,
        xp_awarded=amount,
        xp_total=user.xp_total,
        streak=StreakChange(
            before=streaks.displayed(before, today),
            after=streaks.displayed(after, today),
            longest=after.longest,
            extended=after.last_date == today and before.last_date != today,
        ),
        daily_goal=DailyGoalChange(
            goal_xp=goal,
            today_xp=today_xp,
            completed=today_xp >= goal,
            just_completed=xp_before_today < goal <= today_xp,
        ),
        new_achievements=[
            AchievementBadge(
                code=a.code, title=a.title, description=a.description, icon=a.icon, tier=a.tier
            )
            for a in new_achievements
        ],
    )
