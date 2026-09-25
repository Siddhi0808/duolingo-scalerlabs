"""Closed value sets used by the schema.

Each enum is stored as VARCHAR with a CHECK constraint (see `str_enum`), so an
invalid value is rejected by SQLite itself, not only by Python.
"""

from enum import StrEnum

from sqlalchemy import Enum


class ExerciseType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    WORD_BANK = "word_bank"  # translation built from tappable word tiles
    MATCHING_PAIRS = "matching_pairs"
    FILL_BLANK = "fill_blank"
    TYPE_ANSWER = "type_answer"


class SessionMode(StrEnum):
    LESSON = "lesson"  # a specific lesson; costs hearts, records completion
    PRACTICE = "practice"  # review of completed material; no heart loss


class SessionStatus(StrEnum):
    """Lifecycle and final result of a lesson session."""

    ACTIVE = "active"  # in progress, resumable
    COMPLETED = "completed"  # finished; rewards granted, result stored
    FAILED = "failed"  # ran out of hearts
    ABANDONED = "abandoned"  # learner quit


class XpSource(StrEnum):
    LESSON = "lesson"
    PRACTICE = "practice"
    BONUS = "bonus"


class AchievementMetric(StrEnum):
    """What an achievement's threshold is measured against (all derived at evaluation)."""

    TOTAL_XP = "total_xp"
    STREAK = "streak"
    LESSONS_COMPLETED = "lessons_completed"
    PERFECT_LESSONS = "perfect_lessons"
    SKILLS_COMPLETED = "skills_completed"


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """VARCHAR column + CHECK constraint named ck_<table>_<name>, storing enum *values*."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=max(len(member.value) for member in enum_cls),
        values_callable=lambda cls: [member.value for member in cls],
    )
