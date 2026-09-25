"""Achievements: rules are data rows (metric >= threshold), evaluated in one place.

Metrics are derived from persisted state at evaluation time:
  total_xp           users.xp_total
  streak             the learner's current streak (as displayed today)
  lessons_completed  number of lesson_completions rows (distinct lessons)
  perfect_lessons    lesson_completions with best_mistakes == 0
  skills_completed   skills whose every lesson is completed (path_rules)

`evaluate` must run *after* the completion, XP and streak updates in the same
transaction, so it sees the new values. It is idempotent: it only inserts rows for
achievements not yet unlocked, and the (user_id, achievement_id) primary key makes a
duplicate impossible even if called twice.

Gem rewards on achievements are listed but not paid out (the gem economy is mocked).
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    AchievementMetric,
    Course,
    LessonCompletion,
    User,
    UserAchievement,
)
from app.services import path_service, streaks
from app.services.path_rules import NodeState


def learner_metrics(
    db: Session, user: User, today: date, course: Course | None = None
) -> dict[AchievementMetric, int]:
    """Current value of every achievement metric. Pass `course` (the loaded course tree)
    if the caller already has it, to avoid loading it twice."""
    completions = select(func.count()).select_from(LessonCompletion)
    lessons = db.scalar(completions.where(LessonCompletion.user_id == user.id)) or 0
    perfect = (
        db.scalar(
            completions.where(
                LessonCompletion.user_id == user.id, LessonCompletion.best_mistakes == 0
            )
        )
        or 0
    )
    skills = 0
    if course is None and user.current_course_id is not None:
        course = path_service.load_course_tree(db, user.current_course_id)
    if course is not None:
        progress = path_service.derive_course_progress(
            course, path_service.completed_lesson_ids(db, user.id)
        )
        skills = sum(p.state is NodeState.COMPLETED for p in progress.values())
    streak = streaks.StreakState(user.streak_count, user.longest_streak, user.last_streak_date)
    return {
        AchievementMetric.TOTAL_XP: user.xp_total,
        AchievementMetric.STREAK: streaks.displayed(streak, today),
        AchievementMetric.LESSONS_COMPLETED: lessons,
        AchievementMetric.PERFECT_LESSONS: perfect,
        AchievementMetric.SKILLS_COMPLETED: skills,
    }


def catalog(db: Session) -> list[Achievement]:
    return list(db.scalars(select(Achievement).order_by(Achievement.id)))


def unlocked(db: Session, user_id: int) -> dict[int, UserAchievement]:
    rows = db.scalars(select(UserAchievement).where(UserAchievement.user_id == user_id))
    return {row.achievement_id: row for row in rows}


def evaluate(db: Session, user: User, today: date, now: datetime) -> list[Achievement]:
    """Unlock every achievement whose threshold is now met. Returns the new ones."""
    metrics = learner_metrics(db, user, today)
    already = unlocked(db, user.id)
    new = [
        achievement
        for achievement in catalog(db)
        if achievement.id not in already and metrics[achievement.metric] >= achievement.threshold
    ]
    for achievement in new:
        db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id, unlocked_at=now))
    db.flush()
    return new
