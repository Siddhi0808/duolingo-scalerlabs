#!/bin/sh
# Production entry point for any host that provides $PORT (Render, Railway, a VM...).
#
# 1. Create tables and load the demo data if the database is empty. On every later start
#    this is a no-op, so learner progress stored on the persistent disk is kept.
#    It must run here, at start-up, because hosts mount persistent disks only at runtime,
#    not during the build.
# 2. Serve the API on $PORT with a single process: SQLite allows one writer at a time.
#
# Set DATABASE_URL to a file on the persistent disk, e.g. sqlite:////var/data/lingo.db.
set -e
cd "$(dirname "$0")"

if [ -z "$DATABASE_URL" ]; then
  echo "WARNING: DATABASE_URL is not set; using the default path, which is not persistent on most hosts." >&2
fi

python -m app.db.seed
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
