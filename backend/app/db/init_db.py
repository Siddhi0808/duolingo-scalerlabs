"""Create the database schema.

Usage:  python -m app.db.init_db

`create_all` only creates missing tables, so it is safe to run repeatedly. There are
no migrations: the schema is rebuilt from the models (`python -m app.db.seed --reset`).
"""

from sqlalchemy import Engine, inspect

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base
from app.db.session import engine as default_engine


def init_db(engine: Engine = default_engine) -> None:
    Base.metadata.create_all(engine)


def main() -> None:
    init_db()
    tables = sorted(inspect(default_engine).get_table_names())
    print(f"Database ready at {default_engine.url.database}")
    print(f"{len(tables)} tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
