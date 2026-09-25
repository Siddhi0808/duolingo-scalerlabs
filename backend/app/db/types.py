"""Custom column types."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Stores datetimes as UTC and always returns timezone-aware UTC values.

    SQLite has no timezone-aware datetime type: it stores text and hands back naive
    values. This type makes the rule explicit at the boundary:
      * writing a naive datetime is an error (its timezone would be a guess);
      * aware values are converted to UTC before storage;
      * values read back are tagged as UTC.
    """

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Naive datetime {value!r} rejected; pass a timezone-aware value.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
