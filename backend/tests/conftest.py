"""Shared test fixtures.

Every DB test gets its own SQLite *file* in a temp directory, built with the same
`create_db_engine` as production (so FK enforcement and pragmas are identical).
A file rather than ":memory:" because in-memory DBs are per-connection.
"""

import os
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

# Point the app at a throwaway DB before any app module creates the global engine,
# so running tests never touches backend/lingo.db.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'app.db'}"

from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_database  # noqa: E402
from app.db.session import create_db_engine  # noqa: E402

# Fixed reference day for seeded learner history in tests.
SEED_DAY = date(2026, 9, 25)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seeded(db: Session) -> Session:
    """The M2 seed dataset (course, learner, bots) in the test database."""
    result = seed_database(db, SEED_DAY)
    db.commit()
    assert not result.skipped
    return db
