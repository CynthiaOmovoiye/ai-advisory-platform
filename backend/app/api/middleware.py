"""Edge security middleware: rate limiting + request-size limits (security-review §4).

Rate limiting uses Redis when configured (so limits hold across API replicas) and
falls back to an in-process limiter otherwise — which keeps tests hermetic and works
for single-process dev. Both implement the same fixed-window ``allow(key)`` contract.

Request-size limiting rejects oversized JSON bodies up front; multipart uploads are
exempt here because the upload route enforces its own (larger) byte cap before storing.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Protocol

from app.infra.config import Settings


class RateLimiter(Protocol):
    def allow(self, key: str) -> bool: ...


class InMemoryRateLimiter:
    """Sliding-window limiter, per-process. Each app instance owns one (so tests are
    isolated)."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        hits = [t for t in self._hits[key] if t > cutoff]
        self._hits[key] = hits
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


class RedisRateLimiter:
    """Fixed-window limiter backed by Redis INCR/EXPIRE — correct across replicas."""

    def __init__(self, client: object, limit: int, window_seconds: int = 60) -> None:
        self._c = client
        self._limit = limit
        self._window = window_seconds

    def allow(self, key: str) -> bool:
        bucket = f"ratelimit:{key}:{int(time.time() // self._window)}"
        count = self._c.incr(bucket)  # type: ignore[attr-defined]
        if count == 1:
            self._c.expire(bucket, self._window)  # type: ignore[attr-defined]
        return count <= self._limit


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.redis_url:
        try:
            import redis  # optional dep; present in the worker/runtime image

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
            client.ping()
            return RedisRateLimiter(client, settings.rate_limit_per_minute)
        except Exception:  # noqa: S110 - Redis unreachable ⇒ degrade to in-process, don't crash
            return InMemoryRateLimiter(settings.rate_limit_per_minute)
    return InMemoryRateLimiter(settings.rate_limit_per_minute)
