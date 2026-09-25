"""Grading functions for every exercise type, independent of the database."""

from typing import Any

import pytest
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise, ExerciseType
from app.schemas.lesson import Answer
from app.services import grading
from app.services.grading import InvalidAnswerError, grade, normalize
from tests.lesson_helpers import right_answer, wrong_answer

ANSWER: TypeAdapter[Answer] = TypeAdapter(Answer)


def check(
    type_: ExerciseType, payload: dict[str, Any], solution: dict[str, Any], answer: dict[str, Any]
) -> grading.Grade:
    return grade(type_, payload, solution, ANSWER.validate_python(answer))


# --------------------------------------------------------------------------- normalization


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hola", "hola"),
        ("  hola  ", "hola"),
        ("Buenos   días", "buenos días"),
        ("¿Cómo te llamas?", "cómo te llamas"),
        ("La cuenta, por favor.", "la cuenta por favor"),
        ("\tSoy\nAna ", "soy ana"),
        ("“Hola”", "hola"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_keeps_accents_and_apostrophes() -> None:
    assert normalize("Días") == "días"
    assert normalize("I'm") == "i'm"


# --------------------------------------------------------------------------- multiple choice

MC = ExerciseType.MULTIPLE_CHOICE
MC_PAYLOAD = {"options": [{"id": "a", "text": "el perro"}, {"id": "b", "text": "el gato"}]}
MC_SOLUTION = {"correct_option_id": "b"}


def test_multiple_choice_correct() -> None:
    result = check(MC, MC_PAYLOAD, MC_SOLUTION, {"type": "multiple_choice", "option_id": "b"})
    assert result.correct and result.correct_answer == "el gato"


def test_multiple_choice_incorrect() -> None:
    result = check(MC, MC_PAYLOAD, MC_SOLUTION, {"type": "multiple_choice", "option_id": "a"})
    assert not result.correct and result.correct_answer == "el gato"


def test_multiple_choice_invalid_option() -> None:
    with pytest.raises(InvalidAnswerError, match="Unknown option"):
        check(MC, MC_PAYLOAD, MC_SOLUTION, {"type": "multiple_choice", "option_id": "z"})


def test_answer_of_the_wrong_type_is_invalid() -> None:
    with pytest.raises(InvalidAnswerError, match="Expected an answer of type"):
        check(MC, MC_PAYLOAD, MC_SOLUTION, {"type": "type_answer", "text": "el gato"})


# --------------------------------------------------------------------------- word bank

WB = ExerciseType.WORD_BANK
WB_PAYLOAD = {
    "source_text": "I eat bread",
    "tiles": [
        {"id": "t1", "text": "pan"},
        {"id": "t2", "text": "Yo"},
        {"id": "t3", "text": "bebo"},
        {"id": "t4", "text": "como"},
        {"id": "t5", "text": "Como"},
    ],
}
WB_SOLUTION = {"accepted": [["Yo", "como", "pan"], ["Como", "pan"]]}


def wb(*tile_ids: str) -> dict[str, Any]:
    return {"type": "word_bank", "tile_ids": list(tile_ids)}


def test_word_bank_correct_order() -> None:
    result = check(WB, WB_PAYLOAD, WB_SOLUTION, wb("t2", "t4", "t1"))
    assert result.correct and result.correct_answer == "Yo como pan"


def test_word_bank_alternative_answer_and_case_insensitive_tiles() -> None:
    assert check(WB, WB_PAYLOAD, WB_SOLUTION, wb("t5", "t1")).correct
    assert check(WB, WB_PAYLOAD, WB_SOLUTION, wb("t4", "t1")).correct  # "como pan"


@pytest.mark.parametrize(
    "tiles",
    [
        ("t1", "t4", "t2"),  # right words, wrong order
        ("t4", "t2", "t1"),  # a permutation is not accepted
        ("t2", "t4"),  # missing word
        ("t2", "t4", "t1", "t3"),  # extra word
        ("t2", "t3", "t1"),  # wrong word
    ],
)
def test_word_bank_incorrect(tiles: tuple[str, ...]) -> None:
    assert not check(WB, WB_PAYLOAD, WB_SOLUTION, wb(*tiles)).correct


def test_word_bank_unknown_or_reused_tiles_are_invalid() -> None:
    with pytest.raises(InvalidAnswerError, match="Unknown tiles"):
        check(WB, WB_PAYLOAD, WB_SOLUTION, wb("t2", "t9"))
    with pytest.raises(InvalidAnswerError, match="more than once"):
        check(WB, WB_PAYLOAD, WB_SOLUTION, wb("t2", "t4", "t4"))


# --------------------------------------------------------------------------- matching pairs

MP = ExerciseType.MATCHING_PAIRS
MP_PAYLOAD = {
    "left": [
        {"id": "l1", "text": "dog"},
        {"id": "l2", "text": "cat"},
        {"id": "l3", "text": "house"},
    ],
    "right": [
        {"id": "r1", "text": "casa"},
        {"id": "r2", "text": "perro"},
        {"id": "r3", "text": "gato"},
    ],
}
MP_SOLUTION = {"pairs": [["l1", "r2"], ["l2", "r3"], ["l3", "r1"]]}


def mp(*pairs: tuple[str, str]) -> dict[str, Any]:
    return {"type": "matching_pairs", "pairs": [list(p) for p in pairs]}


def test_matching_all_correct() -> None:
    result = check(MP, MP_PAYLOAD, MP_SOLUTION, mp(("l1", "r2"), ("l2", "r3"), ("l3", "r1")))
    assert result.correct
    assert result.correct_answer == "dog = perro, cat = gato, house = casa"


def test_matching_pair_order_does_not_matter() -> None:
    assert check(MP, MP_PAYLOAD, MP_SOLUTION, mp(("l3", "r1"), ("l1", "r2"), ("l2", "r3"))).correct


def test_matching_one_incorrect_pair() -> None:
    assert not check(
        MP, MP_PAYLOAD, MP_SOLUTION, mp(("l1", "r3"), ("l2", "r2"), ("l3", "r1"))
    ).correct


@pytest.mark.parametrize(
    "pairs",
    [
        (("l1", "r2"), ("l2", "r3")),  # incomplete
        (("l1", "r2"), ("l1", "r3"), ("l3", "r1")),  # left item used twice
        (("l1", "r2"), ("l2", "r2"), ("l3", "r1")),  # right item used twice
        (("l1", "r2"), ("l2", "r3"), ("l9", "r1")),  # unknown id
        (("r2", "l1"), ("r3", "l2"), ("r1", "l3")),  # columns swapped
    ],
)
def test_matching_malformed_submission_is_invalid(pairs: tuple[tuple[str, str], ...]) -> None:
    with pytest.raises(InvalidAnswerError, match="exactly once"):
        check(MP, MP_PAYLOAD, MP_SOLUTION, mp(*pairs))


# --------------------------------------------------------------------------- fill blank

FB = ExerciseType.FILL_BLANK
FB_PAYLOAD = {
    "before": "Yo ",
    "after": " agua.",
    "options": [{"id": "a", "text": "como"}, {"id": "b", "text": "bebo"}],
    "hint": "I drink water.",
}
FB_SOLUTION = {"correct_option_id": "b"}


def fb(text: str) -> dict[str, Any]:
    return {"type": "fill_blank", "text": text}


def test_fill_blank_correct() -> None:
    result = check(FB, FB_PAYLOAD, FB_SOLUTION, fb("bebo"))
    assert result.correct and result.correct_answer == "Yo bebo agua."


def test_fill_blank_incorrect() -> None:
    assert not check(FB, FB_PAYLOAD, FB_SOLUTION, fb("como")).correct


def test_fill_blank_case_normalization() -> None:
    assert check(FB, FB_PAYLOAD, FB_SOLUTION, fb("BEBO")).correct


def test_fill_blank_whitespace_normalization() -> None:
    assert check(FB, FB_PAYLOAD, FB_SOLUTION, fb("   bebo \t")).correct


def test_fill_blank_rejects_near_misses() -> None:
    for near_miss in ("beb", "bebos", "bebo agua"):
        assert not check(FB, FB_PAYLOAD, FB_SOLUTION, fb(near_miss)).correct


def test_fill_blank_blank_answer_is_invalid() -> None:
    with pytest.raises(InvalidAnswerError, match="empty"):
        check(FB, FB_PAYLOAD, FB_SOLUTION, fb("  ?  "))


# --------------------------------------------------------------------------- type answer

TA = ExerciseType.TYPE_ANSWER
TA_PAYLOAD = {"source_text": "Good morning", "answer_language": "es"}
TA_SOLUTION = {"accepted": ["Buenos días", "Buen día"]}


def ta(text: str) -> dict[str, Any]:
    return {"type": "type_answer", "text": text}


def test_type_answer_correct_and_alternative() -> None:
    first = check(TA, TA_PAYLOAD, TA_SOLUTION, ta("Buenos días"))
    assert first.correct and first.note is None and first.correct_answer == "Buenos días"
    assert check(TA, TA_PAYLOAD, TA_SOLUTION, ta("buen día")).correct


def test_type_answer_incorrect() -> None:
    assert not check(TA, TA_PAYLOAD, TA_SOLUTION, ta("Buenas noches")).correct


@pytest.mark.parametrize(
    "text", ["BUENOS DÍAS", "  buenos   días  ", "¡Buenos días!", "buenos días."]
)
def test_type_answer_normalization(text: str) -> None:
    result = check(TA, TA_PAYLOAD, TA_SOLUTION, ta(text))
    assert result.correct and result.note is None


def test_missing_accents_are_accepted_with_a_note() -> None:
    result = check(TA, TA_PAYLOAD, TA_SOLUTION, ta("buenos dias"))
    assert result.correct
    assert result.note == "Watch the accents: Buenos días"


def test_accent_leniency_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grading, "ACCEPT_MISSING_ACCENTS", False)
    assert not check(TA, TA_PAYLOAD, TA_SOLUTION, ta("buenos dias")).correct


@pytest.mark.parametrize("text", ["buenos dia", "bueno días", "buenos días amigo", "buenosdías"])
def test_type_answer_has_no_fuzzy_matching(text: str) -> None:
    assert not check(TA, TA_PAYLOAD, TA_SOLUTION, ta(text)).correct


# --------------------------------------------------------------------------- whole seed


def test_every_seeded_exercise_grades_its_right_and_wrong_answers(seeded: Session) -> None:
    exercises = seeded.scalars(select(Exercise)).all()
    for exercise in exercises:
        right = grade(
            exercise.type,
            exercise.payload,
            exercise.solution,
            ANSWER.validate_python(right_answer(exercise)),
        )
        wrong = grade(
            exercise.type,
            exercise.payload,
            exercise.solution,
            ANSWER.validate_python(wrong_answer(exercise)),
        )
        assert right.correct and right.note is None, exercise.id
        assert not wrong.correct, exercise.id
    assert len(exercises) == 117
