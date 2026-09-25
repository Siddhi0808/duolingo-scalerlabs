"""Canonical data shapes for exercise `payload` (browser-safe) and `solution` (server-only).

Every exercise row is validated against these models: at seed time now, and by the
grading and response code later. `extra="forbid"` means a payload physically cannot
carry an unexpected field such as a leaked answer.

  type             payload (sent to the browser)            solution (never sent)
  ---------------  ---------------------------------------  ---------------------------
  multiple_choice  options[{id, text, image?}]              correct_option_id
  word_bank        source_text, tiles[{id, text}]           accepted[[token, ...], ...]
  matching_pairs   left[{id, text}], right[{id, text}]      pairs[[left_id, right_id]]
  fill_blank       before, after, options[...], hint?       correct_option_id
  type_answer      source_text, answer_language             accepted[str, ...]

The browser's submitted answer shapes (option_id / tile_ids / pairs / text) belong to
the lesson engine (M4) and are defined there.
"""

from collections import Counter
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import ExerciseType

ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]{0,7}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Language = Literal["es", "en"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Choice(_Strict):
    id: ItemId
    text: Text
    image: str | None = None  # optional emoji shown on the card


class Tile(_Strict):
    id: ItemId
    text: Text


# --------------------------------------------------------------------------- payloads


class MultipleChoicePayload(_Strict):
    options: list[Choice] = Field(min_length=2, max_length=4)


class WordBankPayload(_Strict):
    source_text: Text  # sentence to translate
    tiles: list[Tile] = Field(min_length=2, max_length=14)  # answer words + distractors, shuffled


class MatchingPairsPayload(_Strict):
    left: list[Tile] = Field(min_length=3, max_length=5)
    right: list[Tile] = Field(min_length=3, max_length=5)  # shuffled; ids don't encode pairing


class FillBlankPayload(_Strict):
    before: str  # text before the gap
    after: str  # text after the gap
    options: list[Choice] = Field(min_length=2, max_length=4)
    hint: str | None = None  # English meaning of the full sentence


class TypeAnswerPayload(_Strict):
    source_text: Text
    answer_language: Language


# --------------------------------------------------------------------------- solutions


class MultipleChoiceSolution(_Strict):
    correct_option_id: ItemId


class WordBankSolution(_Strict):
    # Each accepted answer is a sequence of tile *texts* (not ids), because two tiles
    # may carry the same word.
    accepted: list[list[Text]] = Field(min_length=1)


class MatchingPairsSolution(_Strict):
    pairs: list[tuple[ItemId, ItemId]] = Field(min_length=3, max_length=5)


class FillBlankSolution(_Strict):
    correct_option_id: ItemId


class TypeAnswerSolution(_Strict):
    accepted: list[Text] = Field(min_length=1)


Payload = (
    MultipleChoicePayload
    | WordBankPayload
    | MatchingPairsPayload
    | FillBlankPayload
    | TypeAnswerPayload
)
Solution = (
    MultipleChoiceSolution
    | WordBankSolution
    | MatchingPairsSolution
    | FillBlankSolution
    | TypeAnswerSolution
)

SCHEMAS: dict[ExerciseType, tuple[type[Payload], type[Solution]]] = {
    ExerciseType.MULTIPLE_CHOICE: (MultipleChoicePayload, MultipleChoiceSolution),
    ExerciseType.WORD_BANK: (WordBankPayload, WordBankSolution),
    ExerciseType.MATCHING_PAIRS: (MatchingPairsPayload, MatchingPairsSolution),
    ExerciseType.FILL_BLANK: (FillBlankPayload, FillBlankSolution),
    ExerciseType.TYPE_ANSWER: (TypeAnswerPayload, TypeAnswerSolution),
}


class InvalidExercise(ValueError):
    """Exercise payload/solution are individually valid but inconsistent with each other."""


def validate_exercise(
    type_: ExerciseType, payload: object, solution: object
) -> tuple[Payload, Solution]:
    """Parse payload and solution for `type_` and check they agree with each other.

    Raises pydantic.ValidationError for shape errors, InvalidExercise for consistency
    errors (e.g. the correct option id does not exist).
    """
    payload_cls, solution_cls = SCHEMAS[type_]
    parsed_payload = payload_cls.model_validate(payload)
    parsed_solution = solution_cls.model_validate(solution)
    _cross_check(parsed_payload, parsed_solution)
    return parsed_payload, parsed_solution


def _unique_ids(items: Sequence[Choice | Tile], label: str) -> set[str]:
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise InvalidExercise(f"duplicate ids in {label}: {ids}")
    return set(ids)


def _cross_check(payload: Payload, solution: Solution) -> None:
    match payload, solution:
        case (
            (MultipleChoicePayload() | FillBlankPayload()) as p,
            (MultipleChoiceSolution() | FillBlankSolution()) as s,
        ):
            ids = _unique_ids(p.options, "options")
            texts = [o.text for o in p.options]
            if len(texts) != len(set(texts)):
                raise InvalidExercise(f"duplicate option texts: {texts}")
            if s.correct_option_id not in ids:
                raise InvalidExercise(f"correct_option_id {s.correct_option_id!r} not in {ids}")
            if isinstance(p, FillBlankPayload) and not (p.before.strip() or p.after.strip()):
                raise InvalidExercise("fill_blank needs text around the gap")

        case WordBankPayload() as p, WordBankSolution() as s:
            _unique_ids(p.tiles, "tiles")
            available = Counter(tile.text for tile in p.tiles)
            for sequence in s.accepted:
                if Counter(sequence) - available:
                    raise InvalidExercise(f"accepted answer {sequence} can't be built from tiles")
            if len(p.tiles) <= min(len(sequence) for sequence in s.accepted):
                raise InvalidExercise("word_bank needs at least one distractor tile")

        case MatchingPairsPayload() as p, MatchingPairsSolution() as s:
            left, right = _unique_ids(p.left, "left"), _unique_ids(p.right, "right")
            if len(left) != len(right):
                raise InvalidExercise("left and right columns differ in length")
            if {pair[0] for pair in s.pairs} != left or {pair[1] for pair in s.pairs} != right:
                raise InvalidExercise("pairs must use every left and right item exactly once")
            if len(s.pairs) != len(left):
                raise InvalidExercise("pairs must be one-to-one")

        case TypeAnswerPayload() as p, TypeAnswerSolution() as s:
            if any(answer.casefold() == p.source_text.casefold() for answer in s.accepted):
                raise InvalidExercise("an accepted answer equals the source text")

        case _:
            raise InvalidExercise(
                f"{type(payload).__name__} does not match {type(solution).__name__}"
            )
