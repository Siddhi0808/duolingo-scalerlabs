"""Request-scoped dependencies shared by all routers.

* `get_db`: one SQLAlchemy session per request; commit if the handler succeeds,
  roll back if it raises. Tests override this to point at a temporary database.
* `get_current_user`: mocked authentication. Every request is the default learner.
  Real auth would replace only this function; routers and services stay unchanged.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SetupError
from app.db.session import SessionLocal
from app.models import User


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession) -> User:
    username = get_settings().default_username
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise SetupError(
            "LEARNER_NOT_FOUND",
            f"Default learner {username!r} does not exist. Run: python -m app.db.seed",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
