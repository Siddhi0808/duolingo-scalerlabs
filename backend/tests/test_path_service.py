"""Path service against the real seeded course (M2 content), without HTTP."""

from collections.abc import Iterable

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Lesson, LessonCompletion, Skill, User
from app.schemas.path import PathResponse, SkillNode, UnitNode
from app.services.path_rules import LessonState, NodeState
from app.services.path_service import build_path
from tests.factories import NOW

L, A, P, C = NodeState.LOCKED, NodeState.AVAILABLE, NodeState.IN_PROGRESS, NodeState.COMPLETED


@pytest.fixture
def newbie(seeded: Session) -> User:
    """A learner enrolled in the seeded course with no progress at all."""
    user = User(username="newbie", display_name="Newbie", current_course_id=1)
    seeded.add(user)
    seeded.flush()
    return user


def complete(db: Session, user: User, lesson_ids: Iterable[int]) -> None:
    for lesson_id in lesson_ids:
        db.add(
            LessonCompletion(
                user=user,
                lesson_id=lesson_id,
                first_completed_at=NOW,
                last_completed_at=NOW,
                best_mistakes=0,
            )
        )
    db.flush()


def lessons_of(db: Session, skill_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Lesson.id).where(Lesson.skill_id == skill_id).order_by(Lesson.order_index)
        )
    )


def all_skills(path: PathResponse) -> list[SkillNode]:
    return [skill for unit in path.units for skill in unit.skills]


def skill_states(path: PathResponse) -> list[NodeState]:
    return [skill.state for skill in all_skills(path)]


def unit(path: PathResponse, position: int) -> UnitNode:
    return path.units[position - 1]


# Seeded course: unit 1 = skills 1-3, unit 2 = skills 4-6, unit 3 = skills 7-9.


def test_fresh_learner_gets_the_initial_path(seeded: Session, newbie: User) -> None:
    path = build_path(seeded, newbie)
    assert skill_states(path) == [A] + [L] * 8
    assert [u.state for u in path.units] == [A, L, L]
    first = all_skills(path)[0]
    assert first.is_current and first.next_lesson_id == lessons_of(seeded, 1)[0]
    assert {lesson.state for lesson in first.lessons} == {LessonState.AVAILABLE}
    assert path.current_skill_id == 1
    assert path.current_lesson_id == first.next_lesson_id
    assert (path.progress.completed, path.progress.total, path.progress.percent) == (0, 22, 0)


def test_completing_first_lesson_keeps_skill_in_progress(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1)[:1])
    path = build_path(seeded, newbie)
    greetings = all_skills(path)[0]
    assert greetings.state is P
    assert (greetings.progress.completed, greetings.progress.total) == (1, 3)
    assert greetings.progress.percent == 33
    assert greetings.next_lesson_id == lessons_of(seeded, 1)[1]
    assert skill_states(path)[1:] == [L] * 8
    assert unit(path, 1).state is P


def test_completing_a_skill_unlocks_the_next(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1))
    path = build_path(seeded, newbie)
    assert skill_states(path)[:3] == [C, A, L]
    assert all_skills(path)[0].progress.percent == 100
    assert path.current_skill_id == 2


def test_finishing_a_unit_unlocks_the_next_units_first_skill(seeded: Session, newbie: User) -> None:
    for skill_id in (1, 2, 3):
        complete(seeded, newbie, lessons_of(seeded, skill_id))
    path = build_path(seeded, newbie)
    assert skill_states(path) == [C, C, C, A, L, L, L, L, L]
    assert [u.state for u in path.units] == [C, A, L]
    assert path.current_skill_id == 4


def test_later_units_stay_locked_until_prerequisites_are_done(
    seeded: Session, newbie: User
) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1) + lessons_of(seeded, 2))
    complete(seeded, newbie, lessons_of(seeded, 3)[:-1])  # all but the last lesson of unit 1
    path = build_path(seeded, newbie)
    assert skill_states(path)[3:] == [L] * 6
    assert [u.state for u in path.units[1:]] == [L, L]


def test_completed_skills_remain_completed_after_further_progress(
    seeded: Session, newbie: User
) -> None:
    for skill_id in (1, 2, 3, 4, 5):
        complete(seeded, newbie, lessons_of(seeded, skill_id))
    complete(seeded, newbie, lessons_of(seeded, 6)[:1])
    path = build_path(seeded, newbie)
    assert skill_states(path) == [C, C, C, C, C, P, L, L, L]
    assert [u.state for u in path.units] == [C, P, L]


def test_unit_progress_is_derived(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1) + lessons_of(seeded, 2)[:1])
    first = unit(build_path(seeded, newbie), 1)
    assert (first.progress.completed, first.progress.total, first.progress.percent) == (4, 8, 50)
    assert (first.completed_skills, first.total_skills) == (1, 3)


def test_lesson_states_across_the_path(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1) + lessons_of(seeded, 2)[:1])
    skills = all_skills(build_path(seeded, newbie))
    assert [lesson.state for lesson in skills[0].lessons] == [LessonState.COMPLETED] * 3
    assert [lesson.state for lesson in skills[1].lessons] == [
        LessonState.COMPLETED,
        LessonState.AVAILABLE,
        LessonState.AVAILABLE,
    ]
    assert all(lesson.state is LessonState.LOCKED for s in skills[2:] for lesson in s.lessons)


def test_seeded_learner_has_the_expected_mixed_state(seeded: Session) -> None:
    learner = seeded.scalars(select(User).where(User.username == "learner")).one()
    path = build_path(seeded, learner)
    assert skill_states(path) == [C, C, P, L, L, L, L, L, L]
    assert [u.state for u in path.units] == [P, L, L]
    basic_words = all_skills(path)[2]
    assert basic_words.is_current
    assert [lesson.state for lesson in basic_words.lessons] == [
        LessonState.COMPLETED,
        LessonState.AVAILABLE,
    ]
    assert path.current_lesson_id == basic_words.lessons[1].id
    assert (path.progress.completed, path.progress.total, path.progress.percent) == (7, 22, 31)
    first_unit = unit(path, 1)
    assert (first_unit.progress.completed, first_unit.progress.total) == (7, 8)
    assert first_unit.progress.percent == 87


def test_only_one_skill_is_current(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, lessons_of(seeded, 1))
    current = [skill for skill in all_skills(build_path(seeded, newbie)) if skill.is_current]
    assert [skill.id for skill in current] == [2]


def test_completing_the_whole_course(seeded: Session, newbie: User) -> None:
    complete(seeded, newbie, seeded.scalars(select(Lesson.id)))
    path = build_path(seeded, newbie)
    assert set(skill_states(path)) == {C}
    assert path.current_skill_id is None and path.current_lesson_id is None
    assert path.progress.percent == 100


def test_other_learners_progress_does_not_leak(seeded: Session, newbie: User) -> None:
    # The seeded learner has 7 completions; the newbie must still see a fresh path.
    assert skill_states(build_path(seeded, newbie)) == [A] + [L] * 8


def test_path_never_loads_exercises(seeded: Session, newbie: User) -> None:
    statements: list[str] = []
    engine = seeded.get_bind()

    def record(*args: object) -> None:
        statements.append(str(args[2]))  # (conn, cursor, statement, ...)

    event.listen(engine, "before_cursor_execute", record)
    try:
        build_path(seeded, newbie)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert statements, "expected queries"
    assert not any("exercises" in sql for sql in statements)
    assert len(statements) <= 6  # course, units, skills, lessons, completions


def test_skill_ids_in_path_order(seeded: Session, newbie: User) -> None:
    expected = seeded.scalars(select(Skill.id).order_by(Skill.unit_id, Skill.order_index)).all()
    assert [skill.id for skill in all_skills(build_path(seeded, newbie))] == list(expected)
