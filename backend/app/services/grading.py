"""Server-side grading. Pure functions: no database, no HTTP, no clock.

    grade(type, payload, solution, answer)
        -> validate stored payload/solution (app.schemas.exercises)
        -> dispatch on exercise type to one small grader
        -> Grade(correct, correct_answer, note)

Two kinds of failure are kept apart:

* InvalidAnswerError: the answer is not a legal move for this exercise (unknown option
  or tile id, a tile used twice, pairs that are not one-to-one...). It is rejected
  *without grading*, so no heart is lost. The check uses only the public payload, so
  an invalid answer reveals nothing about the solution.
* A legal but wrong answer: Grade(correct=False, ...).

Grading rules
-------------
multiple_choice  The chosen option id must equal the solution's option id.
word_bank        Tile ids -> tile texts, in order. Correct if the sequence equals one
                 of the accepted sequences, comparing words case-insensitively. Order
                 matters; missing or extra words are wrong. Each tile may be used once.
matching_pairs   Must pair every left item with exactly one right item (a complete
                 one-to-one matching). Correct if the set of pairs equals the solution's
                 set; the order the pairs are listed in does not matter.
fill_blank       Text rule (below) against the correct option's text.
type_answer      Text rule against each accepted answer.

Text rule (fill_blank, type_answer)
-----------------------------------
normalize(): Unicode NFC -> punctuation . , ! ? ¿ ¡ ; : and quotes become spaces ->
case-folded -> whitespace collapsed and trimmed. "  ¿Cómo  te llamas? " equals
"cómo te llamas".
1. normalize(submitted) == normalize(accepted)            -> correct.
2. Equal once accents are removed too (dias == días)      -> correct, with a note.
   (ACCEPT_MISSING_ACCENTS; learners often cannot type á/ñ. Set False to be strict.)
3. Otherwise wrong. No edit distance or other fuzzy matching.
"""

import unicodedata
from dataclasses import dataclass

from app.models.enums import ExerciseType
from app.schemas.exercises import (
    FillBlankPayload,
    FillBlankSolution,
    MatchingPairsPayload,
    MatchingPairsSolution,
    MultipleChoicePayload,
    MultipleChoiceSolution,
    TypeAnswerPayload,
    TypeAnswerSolution,
    WordBankPayload,
    WordBankSolution,
    validate_exercise,
)
from app.schemas.lesson import (
    Answer,
    FillBlankAnswer,
    MatchingPairsAnswer,
    MultipleChoiceAnswer,
    TypeAnswerAnswer,
    WordBankAnswer,
)

ACCEPT_MISSING_ACCENTS = True
PUNCTUATION = '.,!?¿¡;:"“”«»'
_PUNCTUATION_TO_SPACE = str.maketrans({char: " " for char in PUNCTUATION})


class InvalidAnswerError(ValueError):
    """The submission is not a legal answer for this exercise; it is not graded."""


@dataclass(frozen=True)
class Grade:
    correct: bool
    correct_answer: str  # display text, shown after grading
    note: str | None = None


# --------------------------------------------------------------------------- text rule


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_PUNCTUATION_TO_SPACE)
    return " ".join(text.casefold().split())


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def match_text(submitted: str, accepted: list[str]) -> tuple[bool, str | None]:
    """Apply the text rule. Returns (correct, note)."""
    given = normalize(submitted)
    if not given:
        raise InvalidAnswerError("The answer is empty.")
    targets = [normalize(answer) for answer in accepted]
    if given in targets:
        return True, None
    if ACCEPT_MISSING_ACCENTS:
        for original, target in zip(accepted, targets, strict=True):
            if strip_accents(given) == strip_accents(target):
                return True, f"Watch the accents: {original}"
    return False, None


# --------------------------------------------------------------------------- graders


def grade_multiple_choice(
    payload: MultipleChoicePayload, solution: MultipleChoiceSolution, answer: MultipleChoiceAnswer
) -> Grade:
    options = {option.id: option.text for option in payload.options}
    if answer.option_id not in options:
        raise InvalidAnswerError(f"Unknown option {answer.option_id!r}.")
    return Grade(
        correct=answer.option_id == solution.correct_option_id,
        correct_answer=options[solution.correct_option_id],
    )


def grade_word_bank(
    payload: WordBankPayload, solution: WordBankSolution, answer: WordBankAnswer
) -> Grade:
    tiles = {tile.id: tile.text for tile in payload.tiles}
    unknown = [tile_id for tile_id in answer.tile_ids if tile_id not in tiles]
    if unknown:
        raise InvalidAnswerError(f"Unknown tiles {unknown}.")
    if len(set(answer.tile_ids)) != len(answer.tile_ids):
        raise InvalidAnswerError("A tile was used more than once.")
    words = [tiles[tile_id].casefold() for tile_id in answer.tile_ids]
    correct = any(words == [word.casefold() for word in seq] for seq in solution.accepted)
    return Grade(correct=correct, correct_answer=" ".join(solution.accepted[0]))


def grade_matching_pairs(
    payload: MatchingPairsPayload, solution: MatchingPairsSolution, answer: MatchingPairsAnswer
) -> Grade:
    left = {item.id: item.text for item in payload.left}
    right = {item.id: item.text for item in payload.right}
    lefts = [pair[0] for pair in answer.pairs]
    rights = [pair[1] for pair in answer.pairs]
    if sorted(lefts) != sorted(left) or sorted(rights) != sorted(right):
        raise InvalidAnswerError("Match every item exactly once.")
    correct = set(answer.pairs) == set(solution.pairs)
    display = ", ".join(f"{left[a]} = {right[b]}" for a, b in solution.pairs)
    return Grade(correct=correct, correct_answer=display)


def grade_fill_blank(
    payload: FillBlankPayload, solution: FillBlankSolution, answer: FillBlankAnswer
) -> Grade:
    expected = next(o.text for o in payload.options if o.id == solution.correct_option_id)
    correct, note = match_text(answer.text, [expected])
    sentence = f"{payload.before}{expected}{payload.after}".strip()
    return Grade(correct=correct, correct_answer=sentence, note=note)


def grade_type_answer(
    _payload: TypeAnswerPayload, solution: TypeAnswerSolution, answer: TypeAnswerAnswer
) -> Grade:
    correct, note = match_text(answer.text, solution.accepted)
    return Grade(correct=correct, correct_answer=solution.accepted[0], note=note)


# --------------------------------------------------------------------------- dispatch


def grade(exercise_type: ExerciseType, payload: object, solution: object, answer: Answer) -> Grade:
    """Grade `answer` against a stored exercise. Raises InvalidAnswerError for illegal moves."""
    if answer.type != exercise_type.value:
        raise InvalidAnswerError(
            f"Expected an answer of type {exercise_type.value!r}, got {answer.type!r}."
        )
    parsed_payload, parsed_solution = validate_exercise(exercise_type, payload, solution)
    match parsed_payload, parsed_solution, answer:
        case MultipleChoicePayload() as p, MultipleChoiceSolution() as s, MultipleChoiceAnswer():
            return grade_multiple_choice(p, s, answer)
        case WordBankPayload() as p, WordBankSolution() as s, WordBankAnswer():
            return grade_word_bank(p, s, answer)
        case MatchingPairsPayload() as p, MatchingPairsSolution() as s, MatchingPairsAnswer():
            return grade_matching_pairs(p, s, answer)
        case FillBlankPayload() as p, FillBlankSolution() as s, FillBlankAnswer():
            return grade_fill_blank(p, s, answer)
        case TypeAnswerPayload() as p, TypeAnswerSolution() as s, TypeAnswerAnswer():
            return grade_type_answer(p, s, answer)
        case _:
            raise InvalidAnswerError("Answer does not match the exercise.")
