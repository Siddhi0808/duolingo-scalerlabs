"""Build the learner's learning path: database queries + the pure path rules.

    queries (course tree, learner completions)
        -> path_rules.derive_skills / derive_unit   (pure)
        -> PathResponse schema

Two queries' worth of data (plus relationship loads for the tree), no exercises
loaded, nothing written. All unlocking logic lives in `path_rules`; this module only
fetches inputs and shapes the output.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models import Course, Lesson, LessonCompletion, Skill, Unit, User
from app.schemas.path import (
    CourseInfo,
    LessonNode,
    PathResponse,
    Progress,
    SkillNode,
    UnitNode,
)
from app.services.path_rules import (
    LessonState,
    SkillInput,
    SkillProgress,
    current_skill,
    derive_skills,
    derive_unit,
    progress_percent,
)


def load_course_tree(db: Session, course_id: int) -> Course:
    """Course -> units -> skills -> lessons (ordered by the relationships). No exercises."""
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(selectinload(Course.units).selectinload(Unit.skills).selectinload(Skill.lessons))
    )
    if course is None:
        raise NotFoundError("COURSE_NOT_FOUND", f"Course {course_id} does not exist.")
    return course


def completed_lesson_ids(db: Session, user_id: int) -> set[int]:
    return set(
        db.scalars(select(LessonCompletion.lesson_id).where(LessonCompletion.user_id == user_id))
    )


def derive_course_progress(course: Course, completed: set[int]) -> dict[int, SkillProgress]:
    """Skill id -> derived progress, for every skill in the course's path order."""
    ordered = [skill for unit in course.units for skill in unit.skills]
    inputs = [SkillInput(s.id, tuple(lesson.id for lesson in s.lessons)) for s in ordered]
    return {progress.skill_id: progress for progress in derive_skills(inputs, completed)}


def build_path(db: Session, user: User) -> PathResponse:
    if user.current_course_id is None:
        raise NotFoundError("NO_ACTIVE_COURSE", "The learner is not enrolled in a course.")
    course = load_course_tree(db, user.current_course_id)
    completed = completed_lesson_ids(db, user.id)
    skills = derive_course_progress(course, completed)
    current = current_skill(list(skills.values()))

    units: list[UnitNode] = []
    for unit in course.units:
        unit_skills = [skills[skill.id] for skill in unit.skills]
        summary = derive_unit(unit_skills)
        units.append(
            UnitNode(
                id=unit.id,
                position=unit.order_index + 1,
                title=unit.title,
                description=unit.description,
                color=unit.color,
                state=summary.state,
                progress=Progress(
                    completed=summary.completed_lessons,
                    total=summary.total_lessons,
                    percent=summary.percent,
                ),
                completed_skills=summary.completed_skills,
                total_skills=summary.total_skills,
                skills=[_skill_node(skill, skills[skill.id], current) for skill in unit.skills],
            )
        )

    done = sum(p.completed_lessons for p in skills.values())
    total = sum(p.total_lessons for p in skills.values())
    return PathResponse(
        course=CourseInfo(
            id=course.id,
            slug=course.slug,
            title=course.title,
            learning_language=course.learning_language,
            from_language=course.from_language,
        ),
        progress=Progress(completed=done, total=total, percent=progress_percent(done, total)),
        current_skill_id=current.skill_id if current else None,
        current_lesson_id=current.next_lesson_id if current else None,
        units=units,
    )


def _skill_node(skill: Skill, progress: SkillProgress, current: SkillProgress | None) -> SkillNode:
    return SkillNode(
        id=skill.id,
        position=skill.order_index + 1,
        title=skill.title,
        description=skill.description,
        icon=skill.icon,
        state=progress.state,
        progress=Progress(
            completed=progress.completed_lessons,
            total=progress.total_lessons,
            percent=progress.percent,
        ),
        next_lesson_id=progress.next_lesson_id,
        is_current=current is not None and current.skill_id == skill.id,
        lessons=[
            LessonNode(
                id=lesson.id,
                position=lesson.order_index + 1,
                title=lesson.title,
                state=progress.lesson_states[lesson.id],
            )
            for lesson in skill.lessons
        ],
    )


def lesson_access(db: Session, user: User, lesson: Lesson) -> LessonState:
    """The learner's state for one lesson, using exactly the same rules as GET /path.

    Raises LESSON_NOT_FOUND if the lesson is not part of the learner's current course,
    so lessons from other courses are indistinguishable from nonexistent ones.
    """
    if user.current_course_id is None or lesson.skill.unit.course_id != user.current_course_id:
        raise NotFoundError("LESSON_NOT_FOUND", f"Lesson {lesson.id} does not exist.")
    course = load_course_tree(db, user.current_course_id)
    progress = derive_course_progress(course, completed_lesson_ids(db, user.id))
    return progress[lesson.skill_id].lesson_states[lesson.id]
