"""Declarative base shared by every model."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, MetaData
from sqlalchemy.orm import DeclarativeBase

from app.db.types import UTCDateTime

# Deterministic constraint names (e.g. uq_lessons_skill_id, fk_units_course_id_courses).
# Readable in error messages and stable if migrations are added later.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Python type -> column type defaults. Every `Mapped[datetime]` column is
    # automatically a UTCDateTime, so no model can accidentally store naive time.
    type_annotation_map = {
        datetime: UTCDateTime(),
        date: Date(),
        dict[str, Any]: JSON(),
        list[int]: JSON(),
    }
