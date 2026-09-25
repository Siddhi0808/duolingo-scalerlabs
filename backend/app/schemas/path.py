"""Response schemas for GET /api/v1/path.

The path is metadata only: titles, order, states and progress counts. It never
includes exercises (so neither exercise content nor solutions can leak, including
for locked lessons). `extra="forbid"` makes schema validation of a response fail if
an unexpected field ever appears.

`position` fields are 1-based display positions within the parent ("Lesson 2 of 3").
Percentages are integers 0-100, floored.
"""

from pydantic import BaseModel, ConfigDict

from app.services.path_rules import LessonState, NodeState


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Progress(_Out):
    completed: int
    total: int
    percent: int


class LessonNode(_Out):
    id: int
    position: int
    title: str
    state: LessonState


class SkillNode(_Out):
    id: int
    position: int
    title: str
    description: str
    icon: str
    state: NodeState
    progress: Progress  # lessons completed / total
    next_lesson_id: int | None  # lesson the node's START button opens; null if locked/done
    is_current: bool  # the single skill the path highlights
    lessons: list[LessonNode]


class UnitNode(_Out):
    id: int
    position: int
    title: str
    description: str
    color: str
    state: NodeState
    progress: Progress  # lessons completed / total across the unit
    completed_skills: int
    total_skills: int
    skills: list[SkillNode]


class CourseInfo(_Out):
    id: int
    slug: str
    title: str
    learning_language: str
    from_language: str


class PathResponse(_Out):
    course: CourseInfo
    progress: Progress  # lessons completed / total across the course
    current_skill_id: int | None  # null when the whole course is completed
    current_lesson_id: int | None
    units: list[UnitNode]
