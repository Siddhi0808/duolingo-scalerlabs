"""Build right and wrong answers for any stored exercise (test-only; reads the solution)."""

from typing import Any

from app.models import Exercise, ExerciseType


def right_answer(exercise: Exercise) -> dict[str, Any]:
    payload, solution = exercise.payload, exercise.solution
    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            return {"type": "multiple_choice", "option_id": solution["correct_option_id"]}
        case ExerciseType.WORD_BANK:
            unused = list(payload["tiles"])
            tile_ids = []
            for word in solution["accepted"][0]:
                tile = next(t for t in unused if t["text"] == word)
                unused.remove(tile)
                tile_ids.append(tile["id"])
            return {"type": "word_bank", "tile_ids": tile_ids}
        case ExerciseType.MATCHING_PAIRS:
            return {"type": "matching_pairs", "pairs": solution["pairs"]}
        case ExerciseType.FILL_BLANK:
            option = next(o for o in payload["options"] if o["id"] == solution["correct_option_id"])
            return {"type": "fill_blank", "text": option["text"]}
        case ExerciseType.TYPE_ANSWER:
            return {"type": "type_answer", "text": solution["accepted"][0]}
    raise AssertionError(exercise.type)


def wrong_answer(exercise: Exercise) -> dict[str, Any]:
    payload, solution = exercise.payload, exercise.solution
    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            other = next(o for o in payload["options"] if o["id"] != solution["correct_option_id"])
            return {"type": "multiple_choice", "option_id": other["id"]}
        case ExerciseType.WORD_BANK:
            used = right_answer(exercise)["tile_ids"]
            extra = next(t["id"] for t in payload["tiles"] if t["id"] not in used)
            return {"type": "word_bank", "tile_ids": [*used, extra]}  # extra word
        case ExerciseType.MATCHING_PAIRS:
            pairs = [list(pair) for pair in solution["pairs"]]
            pairs[0][1], pairs[1][1] = pairs[1][1], pairs[0][1]  # swap two partners
            return {"type": "matching_pairs", "pairs": pairs}
        case ExerciseType.FILL_BLANK:
            other = next(o for o in payload["options"] if o["id"] != solution["correct_option_id"])
            return {"type": "fill_blank", "text": other["text"]}
        case ExerciseType.TYPE_ANSWER:
            return {"type": "type_answer", "text": "definitely not the answer"}
    raise AssertionError(exercise.type)
