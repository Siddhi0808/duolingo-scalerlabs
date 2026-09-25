"""Engine and session factory.

One engine per process. `create_db_engine` is a function so tests can build an
isolated engine on a temporary file with exactly the same connection settings.
"""

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def _apply_sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    # SQLite ships with FK enforcement OFF; without this, every FK is decorative.
    cursor.execute("PRAGMA foreign_keys=ON")
    # Wait up to 5s for a lock instead of failing immediately with "database is locked".
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _enable_wal(dbapi_connection: Any, _record: Any) -> None:
    # Write-ahead log: readers don't block the writer. Only meaningful for file DBs.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def create_db_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        # FastAPI runs sync endpoints in a threadpool, so a connection may be used by
        # a different thread than the one that opened it.
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        event.listen(engine, "connect", _apply_sqlite_pragmas)
        if ":memory:" not in url:
            event.listen(engine, "connect", _enable_wal)
    return engine


engine = create_db_engine(get_settings().database_url)

# expire_on_commit=False: objects stay readable after commit (e.g. when building a
# response), which avoids surprise lazy reloads.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
