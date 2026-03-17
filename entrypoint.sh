#!/usr/bin/env bash
set -e

# Run Alembic migrations unless explicitly skipped
if [ "${SKIP_MIGRATIONS}" != "1" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete."
else
    echo "SKIP_MIGRATIONS=1 -- skipping Alembic migrations."
fi

# Start uvicorn (exec replaces the shell so signals reach the process)
# Workers default to 1: the grading scheduler runs in lifespan and
# multi-worker mode would duplicate it.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
