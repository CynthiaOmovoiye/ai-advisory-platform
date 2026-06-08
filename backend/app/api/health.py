"""Readiness checks for /readyz (deployment-guide §6).

Distinguishes liveness (/healthz — is the process up?) from readiness (/readyz — can
it actually serve: database reachable, storage + broker reachable). The database is
**required**; storage and Redis are best-effort and reported but don't fail readiness
on their own (the API still serves reads/writes without them, just not uploads/jobs).
Pure function over injected dependencies, so it's testable with fakes.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.config import Settings
from app.infra.storage import ObjectStorage


def check_readiness(db: Session, storage: ObjectStorage, settings: Settings) -> tuple[bool, dict]:
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        checks["storage"] = "ok" if storage.ping() else "error"
    except Exception:
        checks["storage"] = "error"

    if settings.redis_url:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
            checks["redis"] = "ok" if client.ping() else "error"
        except Exception:
            checks["redis"] = "error"
    else:
        checks["redis"] = "not_configured"

    ready = checks["database"] == "ok"
    return ready, checks
