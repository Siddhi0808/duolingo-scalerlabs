"""Canonical exercise payload/solution schemas and the seed's exercise builder."""

import pytest
from pydantic import ValidationError

from app.db.seed.authoring import MatchingPairsIn, WordBankIn
from app.db.seed.exercise_builder import build_exercise, stable_shuffle, tokenize
from app.models.enums import ExerciseType
from app.schemas.exercises import InvalidExercise, validate_exercise

MC_PAYLOAD = {"options": [{"id": "a", "text": "hola"}, {"id": "b", "text": "adiós"}]}


def test_valid_multiple_choice_passes() -> None:
    payload, solution = validate_exercise(
        ExerciseType.MULTIPLE_CHOICE, MC_PAYLOAD, {"correct_option_id": "b"}
    )
    assert solution.model_dump() == {"correct_option_id": "b"}


def test_payload_cannot_carry_extra_fields_such_as_the_answer() -> None:
    leaky = {**MC_PAYLOAD, "correct_option_id": "a"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_exercise(ExerciseType.MULTIPLE_CHOICE, leaky, {"correct_option_id": "a"})


@pytest.mark.parametrize(
    ("type_", "payload", "solution", "message"),
    [
        (ExerciseType.MULTIPLE_CHOICE, MC_PAYLOAD, {"correct_option_id": "z"}, "not in"),
        (
            ExerciseType.WORD_BANK,
            {
                "source_text": "Hello",
                "tiles": [{"id": "t1", "text": "Hola"}, {"id": "t2", "text": "y"}],
            },
            {"accepted": [["Hola", "amigo"]]},
            "can't be built",
        ),
        (
            ExerciseType.WORD_BANK,
            {
                "source_text": "Hello",
                "tiles": [{"id": "t1", "text": "Hola"}, {"id": "t2", "text": "y"}],
            },
            {"accepted": [["Hola", "y"]]},
            "distractor",
        ),
        (
            ExerciseType.MATCHING_PAIRS,
            {
                "left": [{"id": f"l{i}", "text": f"en{i}"} for i in range(1, 4)],
                "right": [{"id": f"r{i}", "text": f"es{i}"} for i in range(1, 4)],
            },
            {"pairs": [["l1", "r1"], ["l2", "r1"], ["l3", "r3"]]},
            "exactly once",
        ),
        (
            ExerciseType.TYPE_ANSWER,
            {"source_text": "Hola", "answer_language": "es"},
            {"accepted": ["hola"]},
            "equals the source",
        ),
    ],
)
def test_inconsistent_payload_and_solution_are_rejected(
    type_: ExerciseType, payload: object, solution: object, message: str
) -> None:
    with pytest.raises(InvalidExercise, match=message):
        validate_exercise(type_, payload, solution)


def test_stable_shuffle_is_deterministic_and_never_the_identity() -> None:
    items = ["uno", "dos", "tres", "cuatro"]
    assert stable_shuffle(items, "seed") == stable_shuffle(items, "seed")
    assert stable_shuffle(items, "seed") != items
    assert sorted(stable_shuffle(items, "seed")) == sorted(items)


def test_tokenize_strips_edge_punctuation() -> None:
    assert tokenize("¿Quiero un café, por favor?") == ["Quiero", "un", "café", "por", "favor"]


def test_word_bank_tiles_cover_every_accepted_answer() -> None:
    spec = WordBankIn(
        type="word_bank",
        source="My name is Carlos",
        answer="Me llamo Carlos",
        also=["Mi nombre es Carlos"],
        distractors=["Te"],
    )
    built = build_exercise(spec, "test")
    tiles = sorted(tile["text"] for tile in built.payload["tiles"])
    assert tiles == sorted(["Me", "llamo", "Carlos", "Mi", "nombre", "es", "Te"])
    assert built.solution["accepted"] == [
        ["Me", "llamo", "Carlos"],
        ["Mi", "nombre", "es", "Carlos"],
    ]


def test_matching_ids_do_not_encode_the_pairing() -> None:
    spec = MatchingPairsIn(
        type="matching_pairs",
        pairs=[("dog", "perro"), ("cat", "gato"), ("house", "casa"), ("book", "libro")],
    )
    built = build_exercise(spec, "animals")
    pairs = built.solution["pairs"]
    # right ids are assigned after shuffling, so l1<->r1, l2<->r2... is not the answer
    assert pairs != [[f"l{i}", f"r{i}"] for i in range(1, 5)]
    right_texts = [tile["text"] for tile in built.payload["right"]]
    assert right_texts != ["perro", "gato", "casa", "libro"]
