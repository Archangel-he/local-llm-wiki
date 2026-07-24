#!/bin/sh
set -eu

if [ "${AUTO_MIGRATE:-true}" = "true" ]; then
  alembic upgrade head
  python -m app.seed
  python -m app.recover_jobs
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
