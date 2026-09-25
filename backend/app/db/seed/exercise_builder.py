"""Turn authored exercises into canonical, validated payload/solution pairs.

Two guarantees matter here:

* **No answer leaks into the payload.** Options, word-bank tiles and the right-hand
  matching column are shuffled, and ids are assigned *after* shuffling, so neither
  position nor id numbering reveals the solution. Every result is re-validated with
  `validate_exercise`.
* **Determinism.** Shuffles use a SHA-256 sort key derived from a fixed seed string,
  not `random`, so the output is identical on every run, machine and Python version.
"""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from string import ascii_lowercase
from typing import Any, TypeVar

from app.db.seed.authoring import (
    ExerciseIn,
    FillBlankIn,
    MatchingPairsIn,
    MultipleChoiceIn,
    TypeAnswerIn,
    WordBankIn,
)
from app.models.enums import ExerciseType
from app.schemas.exercises import (
    Choice,
    FillBlankPayload,
    FillBlankSolution,
    Language,
    MatchingPairsPayload,
    MatchingPairsSolution,
    MultipleChoicePayload,
    MultipleChoiceSolution,
    Tile,
    TypeAnswerPayload,
    TypeAnswerSolution,
    WordBankPayload,
    WordBankSolution,
    validate_exercise,
)

_WRITE_IN = {"es": "Write this in Spanish", "en": "Write this in English"}
_EDGE_PUNCTUATION = "¿?¡!.,;:"

T = TypeVar("T")


@dataclass(frozen=True)
class BuiltExercise:
    type: ExerciseType
    prompt: str
    payload: dict[str, Any]
    solution: dict[str, Any]
    explanation: str | None


def stable_shuffle(items: list[T], seed: str) -> list[T]:
    """Deterministic permutation of `items`; never returns the original order (len > 1)."""
    keyed = sorted(
        enumerate(items),
        key=lambda pair: hashlib.sha256(f"{seed}|{pair[0]}|{pair[1]}".encode()).hexdigest(),
    )
    shuffled = [item for _, item in keyed]
    if len(items) > 1 and shuffled == items:
        shuffled = shuffled[1:] + shuffled[:1]  # rotate so the authored order never survives
    return shuffled


def tokenize(sentence: str) -> list[str]:
    """Split a sentence into word-bank tokens: 'Quiero un café, por favor.' -> 5 tokens."""
    tokens = (token.strip(_EDGE_PUNCTUATION) for token in re.split(r"\s+", sentence))
    return [token for token in tokens if token]


def build_exercise(spec: ExerciseIn, seed: str) -> BuiltExercise:
    match spec:
        case MultipleChoiceIn():
            built = _multiple_choice(spec, seed)
        case WordBankIn():
            built = _word_bank(spec, seed)
        case MatchingPairsIn():
            built = _matching_pairs(spec, seed)
        case FillBlankIn():
            built = _fill_blank(spec, seed)
        case TypeAnswerIn():
            built = _type_answer(spec)
    validate_exercise(built.type, built.payload, built.solution)  # defense in depth
    return built


def _dump(model: Any) -> dict[str, Any]:
    result: dict[str, Any] = model.model_dump(mode="json", exclude_none=True)
    return result


def _choices(texts: list[str], images: dict[str, str] | None = None) -> list[Choice]:
    images = images or {}
    return [
        Choice(id=ascii_lowercase[index], text=text, image=images.get(text))
        for index, text in enumerate(texts)
    ]


def _multiple_choice(spec: MultipleChoiceIn, seed: str) -> BuiltExercise:
    # Options are shuffled (then lettered a, b, c...) so the answer's position carries
    # no signal; authors naturally tend to write the answer first.
    options = _choices(stable_shuffle(spec.options, seed), spec.images)
    correct = next(option.id for option in options if option.text == spec.answer)
    return BuiltExercise(
        type=ExerciseType.MULTIPLE_CHOICE,
        prompt=spec.prompt,
        payload=_dump(MultipleChoicePayload(options=options)),
        solution=_dump(MultipleChoiceSolution(correct_option_id=correct)),
        explanation=spec.explanation,
    )


def _word_bank(spec: WordBankIn, seed: str) -> BuiltExercise:
    accepted = [tokenize(spec.answer), *(tokenize(alt) for alt in spec.also)]
    # Tiles: enough copies of every word to build *any* accepted answer, plus distractors.
    needed: Counter[str] = Counter()
    for sequence in accepted:
        needed |= Counter(sequence)
    tile_texts = list(needed.elements()) + spec.distractors
    shuffled = stable_shuffle(tile_texts, seed)
    tiles = [Tile(id=f"t{index + 1}", text=text) for index, text in enumerate(shuffled)]
    return BuiltExercise(
        type=ExerciseType.WORD_BANK,
        prompt=spec.prompt or _WRITE_IN[spec.to],
        payload=_dump(WordBankPayload(source_text=spec.source, tiles=tiles)),
        solution=_dump(WordBankSolution(accepted=accepted)),
        explanation=spec.explanation,
    )


def _matching_pairs(spec: MatchingPairsIn, seed: str) -> BuiltExercise:
    left = [Tile(id=f"l{index + 1}", text=english) for index, (english, _) in enumerate(spec.pairs)]
    right_texts = stable_shuffle([spanish for _, spanish in spec.pairs], seed)
    right = [Tile(id=f"r{index + 1}", text=text) for index, text in enumerate(right_texts)]
    right_id = {tile.text: tile.id for tile in right}
    pairs = [(left[index].id, right_id[spanish]) for index, (_, spanish) in enumerate(spec.pairs)]
    return BuiltExercise(
        type=ExerciseType.MATCHING_PAIRS,
        prompt=spec.prompt or "Tap the matching pairs",
        payload=_dump(MatchingPairsPayload(left=left, right=right)),
        solution=_dump(MatchingPairsSolution(pairs=pairs)),
        explanation=spec.explanation,
    )


def _fill_blank(spec: FillBlankIn, seed: str) -> BuiltExercise:
    before, after = spec.sentence.split("___")
    options = _choices(stable_shuffle(spec.options, seed))
    correct = next(option.id for option in options if option.text == spec.answer)
    return BuiltExercise(
        type=ExerciseType.FILL_BLANK,
        prompt=spec.prompt or "Choose the missing word",
        payload=_dump(
            FillBlankPayload(before=before, after=after, options=options, hint=spec.hint)
        ),
        solution=_dump(FillBlankSolution(correct_option_id=correct)),
        explanation=spec.explanation,
    )


def _type_answer(spec: TypeAnswerIn) -> BuiltExercise:
    language: Language = spec.to
    return BuiltExercise(
        type=ExerciseType.TYPE_ANSWER,
        prompt=spec.prompt or _WRITE_IN[language],
        payload=_dump(TypeAnswerPayload(source_text=spec.source, answer_language=language)),
        solution=_dump(TypeAnswerSolution(accepted=[spec.answer, *spec.also])),
        explanation=spec.explanation,
    )
