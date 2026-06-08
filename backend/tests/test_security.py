"""Tests for edge security controls: rate limiting, request-size limits, CORS,
secure headers, and readiness (security-review §4, deployment-guide §6)."""

import os
import unittest

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.health import check_readiness
from app.api.middleware import InMemoryRateLimiter
from app.infra.config import Settings, get_settings
from app.infra.db import Base, make_engine, make_session_factory
from app.infra.storage import InMemoryStorage


class TestRateLimiterUnit(unittest.TestCase):
    def test_allows_up_to_limit_then_blocks(self):
        rl = InMemoryRateLimiter(limit=3)
        self.assertTrue(all(rl.allow("ip") for _ in range(3)))
        self.assertFalse(rl.allow("ip"))  # 4th blocked
        self.assertTrue(rl.allow("other"))  # different key unaffected


class TestReadinessUnit(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()

    def tearDown(self):
        self.session.close()

    def test_ready_when_db_ok(self):
        ready, checks = check_readiness(self.session, InMemoryStorage(), Settings(redis_url=""))
        self.assertTrue(ready)
        self.assertEqual(checks["database"], "ok")
        self.assertEqual(checks["redis"], "not_configured")

    def test_not_ready_when_db_fails(self):
        class _BrokenSession:
            def execute(self, *a, **k):
                raise RuntimeError("database unreachable")

        ready, checks = check_readiness(_BrokenSession(), InMemoryStorage(), Settings())
        self.assertFalse(ready)
        self.assertEqual(checks["database"], "error")


class TestMiddlewareIntegration(unittest.TestCase):
    """Spin up an app with tightened limits via env, then exercise the middleware."""

    def setUp(self):
        os.environ["RATE_LIMIT_PER_MINUTE"] = "3"
        os.environ["MAX_REQUEST_BYTES"] = "50"
        os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000"
        get_settings.cache_clear()
        self.app = create_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        for k in ("RATE_LIMIT_PER_MINUTE", "MAX_REQUEST_BYTES", "CORS_ALLOWED_ORIGINS"):
            os.environ.pop(k, None)
        get_settings.cache_clear()

    def test_request_size_limit_returns_413(self):
        # Body well over MAX_REQUEST_BYTES=50; rejected before auth/routing.
        resp = self.client.post("/v1/assessments/x/complete", json={"x": "y" * 200})
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json()["code"], "payload_too_large")

    def test_rate_limit_returns_429(self):
        # healthz is exempt; hit a real path repeatedly (401s still count toward the limit).
        codes = [self.client.get("/v1/admin/metrics").status_code for _ in range(5)]
        self.assertIn(429, codes)
        self.assertEqual(self.client.get("/v1/admin/metrics").json()["code"], "rate_limited")

    def test_healthz_exempt_from_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_cors_headers_present_for_allowed_origin(self):
        resp = self.client.get("/healthz", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://localhost:3000")

    def test_secure_headers_present(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")


if __name__ == "__main__":
    unittest.main()
