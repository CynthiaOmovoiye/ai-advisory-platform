import os
import time
import unittest

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.api.app import create_app
from app.api.deps import get_db, get_notifier
from app.infra.config import get_settings
from app.infra.db import Base, make_engine, make_session_factory

SECRET = "test-secret-please-change"


class _CapturingNotifier:
    def __init__(self) -> None:
        self.verifications: list[tuple[str, str]] = []
        self.resets: list[tuple[str, str]] = []

    def send_email_verification(self, email: str, token: str) -> None:
        self.verifications.append((email, token))

    def send_password_reset(self, email: str, token: str) -> None:
        self.resets.append((email, token))


class TestAuthApi(unittest.TestCase):
    def setUp(self):
        os.environ["AUTH_SECRET"] = SECRET
        os.environ["LOCAL_EMAIL_VERIFICATION_TOKENS"] = "true"
        get_settings.cache_clear()
        self.engine = make_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = make_session_factory(self.engine)

        def override_db():
            session = self.factory()
            try:
                yield session
            finally:
                session.close()

        self.notifier = _CapturingNotifier()
        self.app = create_app()
        self.app.dependency_overrides[get_db] = override_db
        self.app.dependency_overrides[get_notifier] = lambda: self.notifier
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        os.environ.pop("AUTH_SECRET", None)
        os.environ.pop("LOCAL_EMAIL_VERIFICATION_TOKENS", None)
        get_settings.cache_clear()

    def _service_token(self, user: dict, *, sv: int = 0) -> str:
        return jwt.encode(
            {
                "sub": user["id"],
                "org": user["active_org"],
                "org_roles": user["org_roles"],
                "global_roles": [],
                "sv": sv,
                "iss": "advisory-bff",
                "aud": "advisory-api",
                "exp": int(time.time()) + 300,
            },
            SECRET,
            algorithm="HS256",
        )

    def _signup_and_verify(self, email: str) -> dict:
        signup = self.client.post(
            "/v1/auth/signup",
            json={
                "email": email,
                "password": "ChangeMe123!",
                "name": "User",
                "organization_name": f"{email} Org",
            },
        )
        self.assertEqual(signup.status_code, 201, signup.text)
        token = signup.json()["verification_token"]
        self.client.post("/v1/auth/verify-email", json={"token": token})
        signin = self.client.post(
            "/v1/auth/signin", json={"email": email, "password": "ChangeMe123!"}
        )
        self.assertEqual(signin.status_code, 200, signin.text)
        return signin.json()["user"]

    def test_signup_verify_signin_and_me(self):
        signup = self.client.post(
            "/v1/auth/signup",
            json={
                "email": "api@example.com",
                "password": "ChangeMe123!",
                "name": "Api User",
                "organization_name": "Api Org",
            },
        )
        self.assertEqual(signup.status_code, 201, signup.text)
        token = signup.json()["verification_token"]
        self.assertTrue(token)
        verify = self.client.post("/v1/auth/verify-email", json={"token": token})
        self.assertEqual(verify.status_code, 200, verify.text)
        signin = self.client.post(
            "/v1/auth/signin",
            json={"email": "api@example.com", "password": "ChangeMe123!"},
        )
        self.assertEqual(signin.status_code, 200, signin.text)
        user = signin.json()["user"]
        self.assertEqual(user["global_roles"], [])
        self.assertEqual(user["org_roles"][user["active_org"]], ["consultant"])
        service_token = jwt.encode(
            {
                "sub": user["id"],
                "org": user["active_org"],
                "org_roles": user["org_roles"],
                "global_roles": [],
                "iss": "advisory-bff",
                "aud": "advisory-api",
                "exp": int(time.time()) + 300,
            },
            SECRET,
            algorithm="HS256",
        )
        me = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {service_token}"})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], "api@example.com")

    def test_forgot_password_is_generic_for_unknown_email(self):
        resp = self.client.post("/v1/auth/forgot-password", json={"email": "ghost@example.com"})
        self.assertEqual(resp.status_code, 200, resp.text)
        # Same generic body and no email sent — no account enumeration.
        self.assertIn("password reset link has been sent", resp.json()["message"])
        self.assertEqual(self.notifier.resets, [])

    def test_password_reset_flow_invalidates_existing_sessions(self):
        user = self._signup_and_verify("reset-api@example.com")
        old_token = self._service_token(user, sv=0)
        # The pre-reset session works.
        self.assertEqual(
            self.client.get(
                "/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
            ).status_code,
            200,
        )
        # Request + perform the reset.
        self.client.post("/v1/auth/forgot-password", json={"email": "reset-api@example.com"})
        self.assertEqual(len(self.notifier.resets), 1)
        _, reset_token = self.notifier.resets[0]
        reset = self.client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "password": "BrandNewPass456!"},
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        # The old session is now rejected (session_version moved on).
        self.assertEqual(
            self.client.get(
                "/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
            ).status_code,
            401,
        )
        # Old password no longer signs in; the new one does and yields sv=1.
        self.assertEqual(
            self.client.post(
                "/v1/auth/signin",
                json={"email": "reset-api@example.com", "password": "ChangeMe123!"},
            ).status_code,
            401,
        )
        new_signin = self.client.post(
            "/v1/auth/signin",
            json={"email": "reset-api@example.com", "password": "BrandNewPass456!"},
        )
        self.assertEqual(new_signin.status_code, 200, new_signin.text)
        new_user = new_signin.json()["user"]
        self.assertEqual(new_user["session_version"], 1)
        fresh_token = self._service_token(new_user, sv=1)
        self.assertEqual(
            self.client.get(
                "/v1/auth/me", headers={"Authorization": f"Bearer {fresh_token}"}
            ).status_code,
            200,
        )

    def test_duplicate_email_and_invalid_credentials(self):
        body = {
            "email": "dupe-api@example.com",
            "password": "ChangeMe123!",
            "name": None,
            "organization_name": "Dupe Org",
        }
        self.assertEqual(self.client.post("/v1/auth/signup", json=body).status_code, 201)
        self.assertEqual(self.client.post("/v1/auth/signup", json=body).status_code, 409)
        self.assertEqual(
            self.client.post(
                "/v1/auth/signin",
                json={"email": "dupe-api@example.com", "password": "wrong"},
            ).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
