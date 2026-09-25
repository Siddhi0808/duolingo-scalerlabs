"""Schema tests: inspect the real SQLite schema created from the models."""

from pathlib import Path

from sqlalchemy import Engine, inspect, text

from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import create_db_engine

EXPECTED_TABLES = {
    "courses",
    "units",
    "skills",
    "lessons",
    "exercises",
    "users",
    "lesson_sessions",
    "session_answers",
    "lesson_completions",
    "xp_events",
    "achievements",
    "user_achievements",
}

# (table, column) -> (referenced table, ON DELETE action)
EXPECTED_FOREIGN_KEYS = {
    ("units", "course_id"): ("courses", "CASCADE"),
    ("skills", "unit_id"): ("units", "CASCADE"),
    ("lessons", "skill_id"): ("skills", "CASCADE"),
    ("exercises", "lesson_id"): ("lessons", "CASCADE"),
    ("users", "current_course_id"): ("courses", "SET NULL"),
    ("lesson_sessions", "user_id"): ("users", "CASCADE"),
    ("lesson_sessions", "lesson_id"): ("lessons", "RESTRICT"),
    ("lesson_sessions", "skill_id"): ("skills", "RESTRICT"),
    ("session_answers", "session_id"): ("lesson_sessions", "CASCADE"),
    ("session_answers", "exercise_id"): ("exercises", "RESTRICT"),
    ("lesson_completions", "user_id"): ("users", "CASCADE"),
    ("lesson_completions", "lesson_id"): ("lessons", "RESTRICT"),
    ("xp_events", "user_id"): ("users", "CASCADE"),
    ("xp_events", "session_id"): ("lesson_sessions", "SET NULL"),
    ("user_achievements", "user_id"): ("users", "CASCADE"),
    ("user_achievements", "achievement_id"): ("achievements", "RESTRICT"),
}

# Column sets that must be unique (unique constraints, unique indexes or composite PKs).
EXPECTED_UNIQUE = {
    ("courses", ("slug",)),
    ("units", ("course_id", "order_index")),
    ("skills", ("unit_id", "order_index")),
    ("lessons", ("skill_id", "order_index")),
    ("exercises", ("lesson_id", "order_index")),
    ("users", ("username",)),
    ("lesson_completions", ("user_id", "lesson_id")),
    ("session_answers", ("session_id", "exercise_id")),
    ("xp_events", ("session_id",)),
    ("achievements", ("code",)),
    ("achievements", ("metric", "tier")),
    ("user_achievements", ("user_id", "achievement_id")),
}

# Indexes backing the frequent queries the services run.
EXPECTED_QUERY_INDEXES = {
    ("lessons", ("skill_id", "order_index")),  # lessons by skill, in order
    ("exercises", ("lesson_id", "order_index")),  # exercises by lesson/order
    ("lesson_sessions", ("user_id", "status")),  # sessions by user/status (resume)
    ("lesson_completions", ("user_id", "lesson_id")),  # completions by user/lesson
    ("xp_events", ("user_id", "created_at")),  # XP events by user/time
    ("xp_events", ("user_id", "local_date")),  # XP today / active days
    ("users", ("xp_total", "id")),  # leaderboard ORDER BY xp_total DESC, id
}


def index_column_sets(engine: Engine, table: str) -> set[tuple[str, ...]]:
    """Every column tuple SQLite can use as an index on `table` (explicit, unique, PK)."""
    with engine.connect() as conn:
        sets: set[tuple[str, ...]] = set()
        for row in conn.execute(text(f"PRAGMA index_list('{table}')")):
            cols = conn.execute(text(f"PRAGMA index_info('{row.name}')")).all()
            sets.add(tuple(c.name for c in sorted(cols, key=lambda c: c.seqno)))
    pk = inspect(engine).get_pk_constraint(table)["constrained_columns"]
    if pk:
        sets.add(tuple(pk))
    return sets


def test_exactly_the_expected_tables_exist(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    assert tables == EXPECTED_TABLES
    assert "skill_progress" not in tables  # progress is derived from lesson_completions


def test_every_foreign_key_and_its_delete_rule(engine: Engine) -> None:
    actual = {}
    with engine.connect() as conn:
        for table in EXPECTED_TABLES:
            for fk in conn.execute(text(f"PRAGMA foreign_key_list('{table}')")):
                actual[(table, fk[3])] = (fk[2], fk[6])  # from-col -> (table, on_delete)
    assert actual == EXPECTED_FOREIGN_KEYS


def test_every_expected_unique_constraint_exists(engine: Engine) -> None:
    inspector = inspect(engine)
    actual: set[tuple[str, tuple[str, ...]]] = set()
    for table in EXPECTED_TABLES:
        for uq in inspector.get_unique_constraints(table):
            actual.add((table, tuple(uq["column_names"])))
        for ix in inspector.get_indexes(table):
            is_partial = ix.get("dialect_options", {}).get("sqlite_where") is not None
            if ix["unique"] and not is_partial:
                actual.add((table, tuple(c for c in ix["column_names"] if c)))
        pk = inspector.get_pk_constraint(table)["constrained_columns"]
        if len(pk) > 1:
            actual.add((table, tuple(pk)))
    assert EXPECTED_UNIQUE <= actual, EXPECTED_UNIQUE - actual


def test_partial_unique_index_allows_one_active_session_per_user(engine: Engine) -> None:
    with engine.connect() as conn:
        sql: str = conn.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE name = 'uq_lesson_sessions_one_active_per_user'"
            )
        ).scalar_one()
    assert "UNIQUE INDEX" in sql and "WHERE status = 'active'" in sql


def test_frequent_query_indexes_exist(engine: Engine) -> None:
    for table, columns in EXPECTED_QUERY_INDEXES:
        assert columns in index_column_sets(engine, table), (table, columns)


def test_every_foreign_key_column_is_indexed(engine: Engine) -> None:
    """Rule: each FK column is the leftmost column of some index (SQLite doesn't auto-index)."""
    for table, column in EXPECTED_FOREIGN_KEYS:
        leftmost = {cols[0] for cols in index_column_sets(engine, table)}
        assert column in leftmost, f"{table}.{column} has no index"


def test_enum_and_range_checks_exist_in_ddl(engine: Engine) -> None:
    with engine.connect() as conn:
        ddl = " ".join(
            conn.execute(text("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")).scalars()
        )
    for name in (
        "ck_exercises_exercise_type",
        "ck_lesson_sessions_session_status",
        "ck_lesson_sessions_session_mode",
        "ck_xp_events_xp_source",
        "ck_achievements_achievement_metric",
        "ck_users_hearts_range",
    ):
        assert name in ddl, name


def test_init_db_creates_file_database_and_is_idempotent(tmp_path: Path) -> None:
    db_file = tmp_path / "lingo.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    init_db(engine)
    init_db(engine)  # second run is a no-op, not an error
    assert db_file.exists()
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    engine.dispose()
