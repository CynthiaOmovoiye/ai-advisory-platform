import os
import time
import unittest

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.api.app import create_app
from app.api.deps import get_db
from app.infra.config import get_settings
from app.infra.db import Base, make_engine, make_session_factory

SECRET = "test-secret-please-change"


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

        self.app = create_app()
        self.app.dependency_overrides[get_db] = override_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        os.environ.pop("AUTH_SECRET", None)
        os.environ.pop("LOCAL_EMAIL_VERIFICATION_TOKENS", None)
        get_settings.cache_clear()

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
