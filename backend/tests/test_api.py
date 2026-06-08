"""API-layer integration tests (FastAPI TestClient, no network).

Proves the security model end-to-end through HTTP: fail-closed auth (401),
default-deny RBAC (403), cross-tenant isolation (404, no leak), sanitized errors, and
secure headers. Also asserts the structural invariant that **every** v1 route declares
an authorization guard (ADR-0007).
"""

import unittest

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.app import create_app
from app.api.deps import CallerContext, get_caller, get_db
from app.domain.access import Principal, Role
from app.infra.db import Base, make_session_factory
from app.repositories.orm import Assessment, Organization, Response

ORG_A, ORG_B = "org-a", "org-b"


def _caller(user_id, org_id, roles_in_org):
    return CallerContext(
        principal=Principal(user_id=user_id, org_roles={org_id: frozenset(roles_in_org)}),
        organization_id=org_id,
    )


class TestApi(unittest.TestCase):
    def setUp(self):
        # Shared in-memory SQLite (StaticPool keeps one connection alive across sessions).
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionFactory = make_session_factory(self.engine)
        self._seed()

        self.app = create_app()
        self.app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override_db(self):
        session = self.SessionFactory()
        try:
            yield session
        finally:
            session.close()

    def _seed(self):
        s = self.SessionFactory()
        s.add_all(
            [Organization(id=ORG_A, name="A", slug="a"), Organization(id=ORG_B, name="B", slug="b")]
        )
        s.add(
            Assessment(
                id="assess-a",
                organization_id=ORG_A,
                template_name="ai_readiness",
                ruleset_name="baseline",
                ruleset_version=1,
            )
        )
        s.add_all(
            [
                Response(
                    id="r1", assessment_id="assess-a", question_key="mfa_enabled", value=False
                ),
                Response(
                    id="r2",
                    assessment_id="assess-a",
                    question_key="sensitive_data_present",
                    value=True,
                ),
            ]
        )
        s.add(
            Assessment(
                id="assess-b",
                organization_id=ORG_B,
                template_name="ai_readiness",
                ruleset_name="baseline",
                ruleset_version=1,
            )
        )
        s.commit()
        s.close()

    def _as(self, caller):
        self.app.dependency_overrides[get_caller] = lambda: caller

    # -- tests ------------------------------------------------------------- #
    def test_unauthenticated_is_401_and_sanitized(self):
        # no get_caller override -> fail closed
        resp = self.client.post("/v1/assessments/assess-a/complete")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self.assertEqual(body["code"], "unauthorized")
        self.assertIn("correlationId", body)
        self.assertNotIn("Traceback", resp.text)  # no stack trace leaked
        # secure headers present
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")

    def test_org_user_completes_their_assessment(self):
        self._as(_caller("u-a", ORG_A, {Role.ORG_USER}))
        resp = self.client.post("/v1/assessments/assess-a/complete")
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        codes = {r["rule_code"] for r in body["recommendations"]}
        # SEC-MFA-001 (no MFA + sensitive) and OPS-OBS-005 (no model_monitoring key).
        self.assertEqual(codes, {"SEC-MFA-001", "OPS-OBS-005"})
        self.assertTrue(all(r["provenance"]["source"] == "llm" for r in body["recommendations"]))

    def test_cross_tenant_id_is_404_not_a_leak(self):
        # Org B's user is authorized in their own org, but asks for org A's assessment.
        self._as(_caller("u-b", ORG_B, {Role.ORG_USER}))
        resp = self.client.post("/v1/assessments/assess-a/complete")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "not_found")
        self.assertNotIn("org-a", resp.text)  # nothing about the other tenant leaks

    def test_default_deny_returns_403(self):
        # A caller with NO roles in their active org holds no permissions.
        nobody = CallerContext(principal=Principal(user_id="x"), organization_id=ORG_A)
        self._as(nobody)
        resp = self.client.post("/v1/assessments/assess-a/complete")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "forbidden")

    def test_list_after_complete(self):
        self._as(_caller("u-a", ORG_A, {Role.ORG_USER}))
        self.client.post("/v1/assessments/assess-a/complete")
        resp = self.client.get("/v1/assessments/assess-a/recommendations")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({r["rule_code"] for r in resp.json()}, {"SEC-MFA-001", "OPS-OBS-005"})

    def test_every_v1_route_declares_an_authorization_guard(self):
        # Structural default-deny (ADR-0007): a v1 route with no guard fails this test.
        public_auth_routes = {
            ("/v1/auth/signup", "POST"),
            ("/v1/auth/signin", "POST"),
            ("/v1/auth/verify-email", "POST"),
            ("/v1/auth/forgot-password", "POST"),
            ("/v1/auth/reset-password", "POST"),
        }

        def guarded(route: APIRoute) -> bool:
            seen = []

            def walk(dep):
                seen.append(dep.call)
                for sub in dep.dependencies:
                    walk(sub)

            walk(route.dependant)
            return get_caller in seen

        v1_routes = [
            r for r in self.app.routes if isinstance(r, APIRoute) and r.path.startswith("/v1/")
        ]
        self.assertTrue(v1_routes)
        for route in v1_routes:
            methods = route.methods or set()
            if any((route.path, method) in public_auth_routes for method in methods):
                continue
            self.assertTrue(guarded(route), f"UNGUARDED ROUTE: {route.path}")


if __name__ == "__main__":
    unittest.main()
