#!/usr/bin/env bash
# API container entrypoint: apply migrations, seed reference/demo data, then serve.
set -euo pipefail

echo "[start-api] applying database migrations..."
alembic upgrade head

echo "[start-api] seeding demo data (idempotent)..."
python scripts/seed.py

echo "[start-api] starting uvicorn on :8000"
exec uvicorn app.api.app:app --host 0.0.0.0 --port 8000
