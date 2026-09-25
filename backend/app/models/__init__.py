"""All models, imported here so `Base.metadata` knows every table."""

from app.models.content import Course, Exercise, Lesson, Skill, Unit
from app.models.enums import (
    AchievementMetric,
    ExerciseType,
    SessionMode,
    SessionStatus,
    XpSource,
)
from app.models.gamification import Achievement, UserAchievement, XpEvent
from app.models.progress import LessonCompletion, LessonSession, SessionAnswer
from app.models.user import User

__all__ = [
    "Achievement",
    "AchievementMetric",
    "Course",
    "Exercise",
    "ExerciseType",
    "Lesson",
    "LessonCompletion",
    "LessonSession",
    "SessionAnswer",
    "SessionMode",
    "SessionStatus",
    "Skill",
    "Unit",
    "User",
    "UserAchievement",
    "XpEvent",
    "XpSource",
]
