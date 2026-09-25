"""Pydantic models for the seed *authoring* files in `data/`.

The JSON files use a compact, human-friendly format (e.g. a multiple-choice question is
just `options` + `answer`). These models validate that format strictly (unknown keys
are errors, so typos fail loudly); `exercise_builder` then turns each exercise into the
canonical payload/solution shapes defined in `app.schemas.exercises`.
"""

from datetime import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AchievementMetric
from app.schemas.exercises import Language

NonEmpty = Annotated[str, Field(min_length=1)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- exercises


class MultipleChoiceIn(_In):
    type: Literal["multiple_choice"]
    prompt: NonEmpty
    options: list[NonEmpty] = Field(min_length=2, max_length=4)
    answer: NonEmpty
    images: dict[str, str] = {}
    explanation: str | None = None

    @model_validator(mode="after")
    def _answer_is_an_option(self) -> "MultipleChoiceIn":
        if self.answer not in self.options:
            raise ValueError(f"answer {self.answer!r} is not one of the options")
        if not set(self.images) <= set(self.options):
            raise ValueError("images refer to unknown options")
        return self


class WordBankIn(_In):
    type: Literal["word_bank"]
    to: Language = "es"
    prompt: str | None = None
    source: NonEmpty
    answer: NonEmpty
    also: list[NonEmpty] = []  # other accepted translations
    distractors: list[NonEmpty] = Field(min_length=1)
    explanation: str | None = None


class MatchingPairsIn(_In):
    type: Literal["matching_pairs"]
    prompt: str | None = None
    pairs: list[tuple[NonEmpty, NonEmpty]] = Field(min_length=3, max_length=5)
    explanation: str | None = None


class FillBlankIn(_In):
    type: Literal["fill_blank"]
    prompt: str | None = None
    sentence: NonEmpty  # contains exactly one "___"
    options: list[NonEmpty] = Field(min_length=2, max_length=4)
    answer: NonEmpty
    hint: str | None = None
    explanation: str | None = None

    @model_validator(mode="after")
    def _one_gap_and_valid_answer(self) -> "FillBlankIn":
        if self.sentence.count("___") != 1:
            raise ValueError(f"sentence must contain exactly one ___: {self.sentence!r}")
        if self.answer not in self.options:
            raise ValueError(f"answer {self.answer!r} is not one of the options")
        return self


class TypeAnswerIn(_In):
    type: Literal["type_answer"]
    to: Language = "es"
    prompt: str | None = None
    source: NonEmpty
    answer: NonEmpty
    also: list[NonEmpty] = []
    explanation: str | None = None


ExerciseIn = Annotated[
    MultipleChoiceIn | WordBankIn | MatchingPairsIn | FillBlankIn | TypeAnswerIn,
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- course


class LessonIn(_In):
    title: NonEmpty
    exercises: list[ExerciseIn] = Field(min_length=4)


class SkillIn(_In):
    key: NonEmpty  # stable reference used by learners.json, e.g. "greetings"
    title: NonEmpty
    icon: NonEmpty
    description: str
    lessons: list[LessonIn] = Field(min_length=1)


class UnitIn(_In):
    key: NonEmpty
    title: NonEmpty
    description: str
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    skills: list[SkillIn] = Field(min_length=1)


class CourseIn(_In):
    slug: NonEmpty
    title: NonEmpty
    learning_language: NonEmpty
    from_language: NonEmpty
    units: list[UnitIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_skill_keys(self) -> "CourseIn":
        keys = [skill.key for unit in self.units for skill in unit.skills]
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate skill keys: {keys}")
        return self


class AchievementIn(_In):
    code: NonEmpty
    title: NonEmpty
    description: NonEmpty
    icon: NonEmpty
    metric: AchievementMetric
    threshold: int = Field(gt=0)
    tier: int = Field(ge=1)
    gem_reward: int = Field(ge=0)


# --------------------------------------------------------------------------- learners


class Moment(_In):
    """A local wall-clock moment relative to the seed's reference day."""

    day: int = Field(le=0)  # 0 = reference day, -1 = the day before, ...
    time: time


class ActivityIn(_In):
    """A completed session: either a lesson ("skill_key/lesson_number") or skill practice."""

    day: int = Field(le=-1)
    time: time
    lesson: str | None = Field(default=None, pattern=r"^[a-z_]+/[1-9]$")
    practice: str | None = None
    mistakes: int = Field(ge=0)
    xp: int = Field(gt=0)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "ActivityIn":
        if (self.lesson is None) == (self.practice is None):
            raise ValueError("an activity needs exactly one of `lesson` or `practice`")
        return self


class UnlockIn(_In):
    code: NonEmpty
    day: int = Field(le=0)
    time: time


class LearnerIn(_In):
    username: NonEmpty
    display_name: NonEmpty
    avatar_color: str
    timezone: NonEmpty
    joined: Moment
    daily_goal_xp: int
    hearts: int
    hearts_updated: Moment
    gems: int
    streak_count: int
    longest_streak: int
    last_streak_day: int = Field(le=0)
    activity: list[ActivityIn]
    achievements: list[UnlockIn] = []


class BotIn(_In):
    username: NonEmpty
    display_name: NonEmpty
    avatar_color: str
    timezone: NonEmpty
    streak_count: int
    longest_streak: int
    last_streak_day: int = Field(le=0)
    daily_xp: list[tuple[int, int]] = Field(min_length=1)  # (day offset, XP earned that day)


class LearnersIn(_In):
    comment: str | None = Field(default=None, alias="_comment")
    learner: LearnerIn
    bots: list[BotIn]
