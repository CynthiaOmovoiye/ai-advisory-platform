# Backend image: FastAPI API + Celery worker (same image, different entrypoints).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# Install deps from the stable parts first (pyproject + the `app` package) so that
# editing scripts/migrations/data doesn't bust the pip + Chromium layers.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install -e ".[worker,postgres]"

# Chromium for HTML -> PDF report rendering (Playwright). --with-deps pulls the OS libs.
RUN python -m playwright install --with-deps chromium

# The rest (scripts, migrations, alembic.ini, data) — changes here rebuild fast.
COPY . .
RUN chmod +x scripts/start-api.sh

EXPOSE 8000
# Default: run migrations + seed, then serve. The worker service overrides this command.
CMD ["./scripts/start-api.sh"]
