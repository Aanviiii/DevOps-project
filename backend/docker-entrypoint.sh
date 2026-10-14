#!/bin/sh
# Bring the schema up to date, then hand the process over to uvicorn.
#
# Every replica runs the migration step; Alembic's env.py takes a Postgres advisory lock,
# so when several pods start together only one migrates and the rest find it done.
# Set SHELFWISE_SKIP_MIGRATIONS=1 when migrations run elsewhere (a Job, for instance).
set -eu

if [ "${SHELFWISE_SKIP_MIGRATIONS:-0}" != "1" ]; then
    echo "Applying database migrations…"
    alembic upgrade head
fi

if [ "${SHELFWISE_SEED_DEMO_DATA:-0}" = "1" ]; then
    python -m app.seed
fi

# exec so uvicorn becomes PID 1 and receives SIGTERM directly for a graceful shutdown.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --log-level "${SHELFWISE_LOG_LEVEL:-info}" \
    --no-server-header
