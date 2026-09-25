"""Pure unlocking rules: no database, just skills as tuples of lesson ids."""

import pytest

from app.services.path_rules import (
    LessonState,
    NodeState,
    SkillInput,
    current_skill,
    derive_skills,
    derive_unit,
    progress_percent,
)

L, A, P, C = NodeState.LOCKED, NodeState.AVAILABLE, NodeState.IN_PROGRESS, NodeState.COMPLETED

# Three skills with lessons 1-3, 4-5 and 6-8.
PATH = [SkillInput(1, (1, 2, 3)), SkillInput(2, (4, 5)), SkillInput(3, (6, 7, 8))]


def states(completed: set[int], path: list[SkillInput] = PATH) -> list[NodeState]:
    return [skill.state for skill in derive_skills(path, completed)]


@pytest.mark.parametrize(
    ("completed", "expected"),
    [
        (set(), [A, L, L]),  # fresh learner: only the first skill is open
        ({1}, [P, L, L]),  # one lesson done: still in progress, next still locked
        ({1, 2}, [P, L, L]),
        ({1, 2, 3}, [C, A, L]),  # skill done -> next skill unlocks
        ({1, 2, 3, 4}, [C, P, L]),
        ({1, 2, 3, 4, 5}, [C, C, A]),
        ({1, 2, 3, 4, 5, 6, 7, 8}, [C, C, C]),
    ],
)
def test_skill_states_follow_linear_progression(
    completed: set[int], expected: list[NodeState]
) -> None:
    assert states(completed) == expected


def test_completed_skill_stays_completed_regardless_of_order() -> None:
    # Content grew: skill 1 gained lesson 9 after the learner finished skills 1 and 2.
    grown = [SkillInput(1, (1, 2, 3, 9)), *PATH[1:]]
    assert states({1, 2, 3, 4, 5}, grown) == [P, C, A]


def test_started_skill_stays_unlocked_even_if_its_prerequisite_reopens() -> None:
    grown = [SkillInput(1, (1, 2, 3, 9)), *PATH[1:]]
    assert states({1, 2, 3, 4}, grown) == [P, P, L]  # progress is never taken away


@pytest.mark.parametrize(
    ("done", "total", "percent"),
    [(0, 3, 0), (1, 3, 33), (2, 3, 66), (3, 3, 100), (1, 2, 50), (7, 22, 31), (0, 0, 0)],
)
def test_progress_percent_is_floored(done: int, total: int, percent: int) -> None:
    assert progress_percent(done, total) == percent


def test_percent_never_reaches_100_before_completion() -> None:
    assert progress_percent(199, 200) == 99


def test_lesson_states() -> None:
    skills = derive_skills(PATH, {1})
    assert skills[0].lesson_states == {
        1: LessonState.COMPLETED,
        2: LessonState.AVAILABLE,
        3: LessonState.AVAILABLE,
    }
    assert set(skills[1].lesson_states.values()) == {LessonState.LOCKED}
    assert set(skills[2].lesson_states.values()) == {LessonState.LOCKED}


def test_completed_lessons_stay_completed_inside_a_started_skill() -> None:
    # Lesson 4 completed while skill 1 is unfinished (possible only if content changed):
    # skill 2 stays open, its completed lesson stays completed, the rest is available.
    skills = derive_skills(PATH, {1, 4})
    assert skills[1].state is NodeState.IN_PROGRESS
    assert skills[1].lesson_states == {4: LessonState.COMPLETED, 5: LessonState.AVAILABLE}


def test_next_lesson_is_first_unfinished_lesson_of_an_open_skill() -> None:
    skills = derive_skills(PATH, {1, 3})
    assert skills[0].next_lesson_id == 2
    assert skills[1].next_lesson_id is None  # locked
    done = derive_skills(PATH, {1, 2, 3})
    assert done[0].next_lesson_id is None  # completed
    assert done[1].next_lesson_id == 4


def test_current_skill() -> None:
    assert current_skill(derive_skills(PATH, set())) is not None
    progress = derive_skills(PATH, {1, 2, 3})
    current = current_skill(progress)
    assert current is not None and current.skill_id == 2
    assert current_skill(derive_skills(PATH, set(range(1, 9)))) is None  # course finished


@pytest.mark.parametrize(
    ("completed", "state", "skills_done", "lessons_done"),
    [
        (set(), A, 0, 0),
        ({1}, P, 0, 1),
        ({1, 2, 3}, P, 1, 3),
        (set(range(1, 9)), C, 3, 8),
    ],
)
def test_unit_progress(
    completed: set[int], state: NodeState, skills_done: int, lessons_done: int
) -> None:
    unit = derive_unit(derive_skills(PATH, completed))
    assert unit.state is state
    assert (unit.completed_skills, unit.total_skills) == (skills_done, 3)
    assert (unit.completed_lessons, unit.total_lessons) == (lessons_done, 8)
    assert unit.percent == progress_percent(lessons_done, 8)


def test_unit_of_locked_skills_is_locked() -> None:
    later_unit = derive_skills(PATH, set())[1:]
    assert derive_unit(later_unit).state is NodeState.LOCKED
