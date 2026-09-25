"""Request/response schemas for the lesson engine.

Answers are a discriminated union on `type`, so each exercise type has exactly one
accepted shape and `extra="forbid"` rejects anything else. In particular, a client
cannot send `"correct": true` or a position/index: the server decides both.

Nothing here carries an exercise `solution`. `PublicExercise` is the only exercise
shape that leaves the server before grading; `AnswerResult.correct_answer` is
human-readable feedback shown only *after* that exercise has been graded (and it can
never be graded again in the same session).
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExerciseType, SessionMode, SessionStatus
from app.schemas.exercises import ItemId
from app.schemas.gamification import CompletionRewards, HeartInfo

Typed = Annotated[str, Field(min_length=1, max_length=200)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- answers


class MultipleChoiceAnswer(_Strict):
    type: Literal["multiple_choice"]
    option_id: ItemId


class WordBankAnswer(_Strict):
    type: Literal["word_bank"]
    tile_ids: list[ItemId] = Field(min_length=1, max_length=14)  # in the order placed


class MatchingPairsAnswer(_Strict):
    type: Literal["matching_pairs"]
    pairs: list[tuple[ItemId, ItemId]] = Field(min_length=1, max_length=5)  # (left, right)


class FillBlankAnswer(_Strict):
    type: Literal["fill_blank"]
    text: Typed  # the word placed in the gap (tapped option text or typed)


class TypeAnswerAnswer(_Strict):
    type: Literal["type_answer"]
    text: Typed


Answer = Annotated[
    MultipleChoiceAnswer
    | WordBankAnswer
    | MatchingPairsAnswer
    | FillBlankAnswer
    | TypeAnswerAnswer,
    Field(discriminator="type"),
]


class AnswerRequest(_Strict):
    # The exercise the client believes it is answering. The server checks it against
    # the session's real current exercise; it is never used to *choose* the exercise.
    exercise_id: int
    answer: Answer


# --------------------------------------------------------------------------- responses


class PublicExercise(_Strict):
    """An exercise as the learner sees it before answering. No solution, ever."""

    id: int
    type: ExerciseType
    position: int  # 1-based position in the session
    prompt: str
    payload: dict[str, Any]


class LessonRef(_Strict):
    id: int
    title: str
    skill_id: int
    skill_title: str


class SessionProgress(_Strict):
    status: SessionStatus
    total: int
    answered: int
    correct: int
    incorrect: int


class SessionState(_Strict):
    session_id: str
    mode: SessionMode
    lesson: LessonRef | None  # null for practice sessions (M6)
    progress: SessionProgress
    hearts: HeartInfo
    current_exercise: PublicExercise | None  # null once the session has ended


class StartSessionResponse(SessionState):
    resumed: bool  # true if an existing active session for this lesson was returned
    abandoned_session_id: str | None  # another lesson's session that was ended to start this


class AnswerResult(_Strict):
    exercise_id: int
    correct: bool
    correct_answer: str  # display text for the feedback sheet
    note: str | None  # e.g. "Watch the accents: días"
    explanation: str | None
    replayed: bool  # true when this is the stored result of an earlier identical submission
    hearts: HeartInfo
    progress: SessionProgress
    failure_reason: Literal["out_of_hearts"] | None
    rewards: CompletionRewards | None  # only on the answer that completed the lesson
