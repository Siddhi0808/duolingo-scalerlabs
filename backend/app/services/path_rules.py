"""Learning-path rules: pure functions, no database, no HTTP.

Given the course's skills in path order and the set of lesson ids the learner has
completed, derive every skill, lesson and unit state. Because nothing here touches the
database, each rule can be unit-tested with a handful of integers.

Rules
-----
1. Skills form one linear path: units in order, skills in order within each unit. So
   the "previous skill" of a unit's first skill is the last skill of the previous unit.
2. A skill is COMPLETED when it has at least one lesson and every lesson has a
   completion. Completed stays completed, whatever happens elsewhere in the path.
3. A skill is unlocked when it is the first skill in the path, or the previous skill is
   COMPLETED, or the learner has already completed any of its lessons (progress is
   never taken away, e.g. if content is added to an earlier skill later).
4. An unlocked skill is IN_PROGRESS if some of its lessons are done, else AVAILABLE.
   Everything else is LOCKED.
5. Lessons: a completed lesson is COMPLETED; otherwise it is AVAILABLE when its skill is
   unlocked and LOCKED when it is not.
6. Percentages are floored (1/3 -> 33, 2/3 -> 66), so 100% only ever means "all done".
"""

from collections.abc import Sequence, Set
from dataclasses import dataclass
from enum import StrEnum


class NodeState(StrEnum):
    """State of a skill or a unit on the path."""

    LOCKED = "locked"
    AVAILABLE = "available"  # unlocked, nothing done yet
    IN_PROGRESS = "in_progress"  # unlocked, some lessons done
    COMPLETED = "completed"  # every lesson done


class LessonState(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    COMPLETED = "completed"


OPEN_STATES = frozenset({NodeState.AVAILABLE, NodeState.IN_PROGRESS})


@dataclass(frozen=True)
class SkillInput:
    """A skill as the rules see it: its id and its lesson ids in lesson order."""

    skill_id: int
    lesson_ids: tuple[int, ...]


@dataclass(frozen=True)
class SkillProgress:
    skill_id: int
    state: NodeState
    completed_lessons: int
    total_lessons: int
    lesson_states: dict[int, LessonState]
    next_lesson_id: int | None  # first unfinished lesson of an unlocked skill

    @property
    def percent(self) -> int:
        return progress_percent(self.completed_lessons, self.total_lessons)


@dataclass(frozen=True)
class UnitProgress:
    state: NodeState
    completed_skills: int
    total_skills: int
    completed_lessons: int
    total_lessons: int

    @property
    def percent(self) -> int:
        return progress_percent(self.completed_lessons, self.total_lessons)


def progress_percent(done: int, total: int) -> int:
    return 0 if total == 0 else done * 100 // total


def derive_skills(skills: Sequence[SkillInput], completed: Set[int]) -> list[SkillProgress]:
    """Derive the state of every skill, in path order (rules 1-5)."""
    results: list[SkillProgress] = []
    previous_completed = True  # the first skill has no prerequisite
    for skill in skills:
        total = len(skill.lesson_ids)
        done = sum(1 for lesson_id in skill.lesson_ids if lesson_id in completed)

        if total > 0 and done == total:
            state = NodeState.COMPLETED
        elif previous_completed or done > 0:
            state = NodeState.IN_PROGRESS if done > 0 else NodeState.AVAILABLE
        else:
            state = NodeState.LOCKED

        lesson_states = {
            lesson_id: _lesson_state(lesson_id in completed, state)
            for lesson_id in skill.lesson_ids
        }
        next_lesson_id = (
            next((lid for lid in skill.lesson_ids if lid not in completed), None)
            if state in OPEN_STATES
            else None
        )
        results.append(
            SkillProgress(
                skill_id=skill.skill_id,
                state=state,
                completed_lessons=done,
                total_lessons=total,
                lesson_states=lesson_states,
                next_lesson_id=next_lesson_id,
            )
        )
        previous_completed = state is NodeState.COMPLETED
    return results


def _lesson_state(is_completed: bool, skill_state: NodeState) -> LessonState:
    if is_completed:
        return LessonState.COMPLETED
    if skill_state is NodeState.LOCKED:
        return LessonState.LOCKED
    return LessonState.AVAILABLE


def derive_unit(skills: Sequence[SkillProgress]) -> UnitProgress:
    """A unit's state summarises its skills.

    COMPLETED if every skill is completed, LOCKED if every skill is locked,
    IN_PROGRESS if any lesson in it is done, otherwise AVAILABLE.
    """
    states = [skill.state for skill in skills]
    completed_lessons = sum(skill.completed_lessons for skill in skills)
    if states and all(s is NodeState.COMPLETED for s in states):
        state = NodeState.COMPLETED
    elif all(s is NodeState.LOCKED for s in states):
        state = NodeState.LOCKED
    elif completed_lessons > 0:
        state = NodeState.IN_PROGRESS
    else:
        state = NodeState.AVAILABLE
    return UnitProgress(
        state=state,
        completed_skills=sum(s is NodeState.COMPLETED for s in states),
        total_skills=len(states),
        completed_lessons=completed_lessons,
        total_lessons=sum(skill.total_lessons for skill in skills),
    )


def current_skill(skills: Sequence[SkillProgress]) -> SkillProgress | None:
    """The skill the learner should do next: the first unlocked, unfinished one."""
    return next((skill for skill in skills if skill.state in OPEN_STATES), None)
