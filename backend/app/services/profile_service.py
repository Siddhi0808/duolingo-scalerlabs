"""GET /me: the learner's gamification summary. Read-only; derives, never writes.

"Today" is the learner's local calendar date at request time. The displayed streak
drops to 0 once a whole local day has been missed, but the stored streak is only
changed by the next qualifying activity (no writes on read, no midnight job).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import local_date, utc_now
from app.models import AchievementMetric, User
from app.schemas.gamification import (
    AchievementProgress,
    DailyGoal,
    LessonStats,
    MeResponse,
    StreakInfo,
)
from app.services import achievement_service, hearts, path_service, streaks, xp_service


def build_me(db: Session, user: User, now: datetime | None = None) -> MeResponse:
    now = now or utc_now()
    today = local_date(now, user.timezone)
    streak = streaks.StreakState(user.streak_count, user.longest_streak, user.last_streak_date)
    today_xp = xp_service.xp_on_day(db, user.id, today)
    course = (
        path_service.load_course_tree(db, user.current_course_id)
        if user.current_course_id is not None
        else None
    )
    metrics = achievement_service.learner_metrics(db, user, today, course)  # reuses the tree
    unlocked = achievement_service.unlocked(db, user.id)

    total_lessons = total_skills = 0
    if course is not None:
        skills = [skill for unit in course.units for skill in unit.skills]
        total_skills = len(skills)
        total_lessons = sum(len(skill.lessons) for skill in skills)

    return MeResponse(
        username=user.username,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        today=today,
        xp_total=user.xp_total,
        streak=StreakInfo(
            current=streaks.displayed(streak, today),
            longest=user.longest_streak,
            extended_today=streaks.extended_today(streak, today),
            last_active_date=user.last_streak_date,
        ),
        hearts=hearts.status(user, now),  # effective (regeneration applied)
        gems=user.gems,
        daily_goal=DailyGoal(
            goal_xp=user.daily_goal_xp,
            today_xp=today_xp,
            completed=today_xp >= user.daily_goal_xp,
        ),
        stats=LessonStats(
            lessons_completed=metrics[AchievementMetric.LESSONS_COMPLETED],
            total_lessons=total_lessons,
            skills_completed=metrics[AchievementMetric.SKILLS_COMPLETED],
            total_skills=total_skills,
            perfect_lessons=metrics[AchievementMetric.PERFECT_LESSONS],
        ),
        achievements=[
            AchievementProgress(
                code=achievement.code,
                title=achievement.title,
                description=achievement.description,
                icon=achievement.icon,
                tier=achievement.tier,
                unlocked=achievement.id in unlocked,
                unlocked_at=unlocked[achievement.id].unlocked_at
                if achievement.id in unlocked
                else None,
                current=min(metrics[achievement.metric], achievement.threshold),
                target=achievement.threshold,
            )
            for achievement in achievement_service.catalog(db)
        ],
    )
