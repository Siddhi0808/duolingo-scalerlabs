"""Seed command.

    python -m app.db.seed                      # seed an empty database (no-op if seeded)
    python -m app.db.seed --reset              # wipe all rows, then seed again
    python -m app.db.seed --reset --today 2026-09-25   # pin the reference day

Everything runs in one transaction: if anything fails, nothing is written.
"""

import argparse
from collections.abc import Sequence
from datetime import date

from app.db.init_db import init_db
from app.db.seed.seeder import default_reference_day, seed_database
from app.db.session import SessionLocal, engine


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.db.seed", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete all learner state and content, then reseed",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="reference day for learner history (default: today in the learner's timezone)",
    )
    args = parser.parse_args(argv)
    reference_day: date = args.today or default_reference_day()

    init_db(engine)  # make sure tables exist
    with SessionLocal() as db, db.begin():  # commits on success, rolls back on error
        result = seed_database(db, reference_day, reset=args.reset)

    if result.skipped:
        print("Database already seeded; nothing changed. Use --reset to reseed.")
    else:
        action = "Reset and seeded" if args.reset else "Seeded"
        print(f"{action} {engine.url.database} (reference day {reference_day.isoformat()})")
    for table, count in result.counts.items():
        print(f"  {table:<20} {count:>4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
