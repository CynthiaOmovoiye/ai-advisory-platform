"""Tests for session verification (ADR-0007/0009).

Mints real HS256 tokens and verifies the full fail-closed behaviour: valid token →
principal; tampered / expired / wrong-audience / missing-claims → 401. Also tests
get_caller end-to-end through a constructed request (no DB needed).
"""

import time
import unittest

import jwt

from app.domain.access import Permission, Role, has_permission
from app.errors import Unauthorized
from app.infra.auth import decode_session, extract_token

SECRET = "test-secret-please-change"
ISS = "advisory-bff"
AUD = "advisory-api"


def mint(**overrides) -> str:
    claims = {
        "sub": "user-1",
        "org": "org-a",
        "org_roles": {"org-a": ["org_user"]},
        "iss": ISS,
        "aud": AUD,
        "exp": int(time.time()) + 300,
        **overrides,
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


def decode(token: str):
    return decode_session(token, secret=SECRET, issuer=ISS, audience=AUD)


class TestDecodeSession(unittest.TestCase):
    def test_valid_token_yields_principal_and_org(self):
        caller = decode(mint())
        self.assertEqual(caller.principal.user_id, "user-1")
        self.assertEqual(caller.organization_id, "org-a")
        self.assertTrue(has_permission(caller.principal, Permission.ASSESSMENT_COMPLETE, "org-a"))
        # roles only apply in the named org
        self.assertFalse(has_permission(caller.principal, Permission.ASSESSMENT_READ, "org-b"))

    def test_global_admin_claim(self):
        caller = decode(mint(global_roles=["admin"], org_roles={}))
        self.assertIn(Role.ADMIN, caller.principal.global_roles)
        self.assertTrue(has_permission(caller.principal, Permission.RULE_EDIT, "any-org"))

    def test_unknown_role_is_ignored(self):
        caller = decode(mint(org_roles={"org-a": ["superuser", "org_user"]}))
        self.assertEqual(caller.principal.org_roles["org-a"], frozenset({Role.ORG_USER}))

    def test_bad_signature_fails_closed(self):
        forged = jwt.encode({"sub": "x", "org": "org-a", "iss": ISS, "aud": AUD,
                             "exp": int(time.time()) + 60}, "WRONG-SECRET", algorithm="HS256")
        with self.assertRaises(Unauthorized):
            decode(forged)

    def test_expired_fails_closed(self):
        with self.assertRaises(Unauthorized):
            decode(mint(exp=int(time.time()) - 10))

    def test_wrong_audience_fails_closed(self):
        with self.assertRaises(Unauthorized):
            decode(mint(aud="some-other-api"))

    def test_missing_org_fails_closed(self):
        with self.assertRaises(Unauthorized):
            decode(mint(org=None))

    def test_empty_secret_fails_closed(self):
        with self.assertRaises(Unauthorized):
            decode_session(mint(), secret="", issuer=ISS, audience=AUD)


class TestExtractToken(unittest.TestCase):
    def test_from_authjs_cookie(self):
        self.assertEqual(extract_token(cookies={"authjs.session-token": "abc"}, authorization=None), "abc")

    def test_from_secure_cookie(self):
        self.assertEqual(
            extract_token(cookies={"__Secure-authjs.session-token": "xyz"}, authorization=None), "xyz"
        )

    def test_from_bearer_header(self):
        self.assertEqual(extract_token(cookies={}, authorization="Bearer tok123"), "tok123")

    def test_none_when_absent(self):
        self.assertIsNone(extract_token(cookies={}, authorization=None))


class TestGetCallerThroughRequest(unittest.TestCase):
    def test_get_caller_reads_cookie_and_verifies(self):
        import os

        from starlette.requests import Request

        from app.api.deps import get_caller
        from app.infra.config import get_settings

        os.environ["AUTH_SECRET"] = SECRET
        get_settings.cache_clear()
        try:
            token = mint()
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "query_string": b"",
                "headers": [(b"cookie", f"authjs.session-token={token}".encode())],
            }
            caller = get_caller(Request(scope))
            self.assertEqual(caller.principal.user_id, "user-1")
            self.assertEqual(caller.organization_id, "org-a")
        finally:
            os.environ.pop("AUTH_SECRET", None)
            get_settings.cache_clear()

    def test_get_caller_without_token_is_unauthorized(self):
        from starlette.requests import Request

        from app.api.deps import get_caller

        scope = {"type": "http", "method": "POST", "path": "/", "query_string": b"", "headers": []}
        with self.assertRaises(Unauthorized):
            get_caller(Request(scope))


if __name__ == "__main__":
    unittest.main()
