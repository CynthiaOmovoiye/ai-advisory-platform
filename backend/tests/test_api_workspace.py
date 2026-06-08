"""API tests for the consultant workspace, report endpoint, and dashboards.

Exercises the full lifecycle through HTTP: complete → review/approve → publish report
(approval gate) → fetch report; plus admin metrics and evaluation runs. Uses SQLite +
a FakeRenderer + InMemoryStorage so it runs offline.
"""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.app import create_app
from app.api.deps import (
    get_caller,
    get_db,
    get_report_service,
    get_storage,
)
from app.infra.auth import CallerContext
from app.infra.db import Base, make_session_factory
from app.infra.storage import InMemoryStorage
from app.domain.access import Principal, Role
from app.repositories.orm import Assessment, Organization, Response
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlRecommendationRepository,
    SqlReportRepository,
)
from app.reports.renderer import FakeRenderer
from app.reports.service import ReportService

from tests.conftest import load_baseline_ruleset

ORG = "org-a"


def _caller(user_id, *, org_roles=None, global_roles=None):
    return CallerContext(
        principal=Principal(
            user_id=user_id,
            global_roles=frozenset(global_roles or []),
            org_roles={ORG: frozenset(org_roles)} if org_roles else {},
        ),
        organization_id=ORG,
    )


ORG_USER = _caller("u-a", org_roles={Role.ORG_USER})
CONSULTANT = _caller("c-1", global_roles={Role.CONSULTANT})
ADMIN = _caller("admin", global_roles={Role.ADMIN})


class TestWorkspaceApi(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionFactory = make_session_factory(self.engine)
        self.storage = InMemoryStorage()
        self._seed()

        self.app = create_app()
        self.app.dependency_overrides[get_db] = self._override_db
        self.app.dependency_overrides[get_storage] = lambda: self.storage
        self.app.dependency_overrides[get_report_service] = self._override_report_service
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override_db(self):
        s = self.SessionFactory()
        try:
            yield s
        finally:
            s.close()

    def _override_report_service(self):
        s = self.SessionFactory()
        try:
            yield ReportService(
                assessments=SqlAssessmentRepository(s),
                recommendations=SqlRecommendationRepository(s),
                reports=SqlReportRepository(s),
                audit=SqlAuditSink(s),
                storage=self.storage,
                renderer=FakeRenderer(),
            )
            s.commit()
        finally:
            s.close()

    def _seed(self):
        s = self.SessionFactory()
        s.add(Organization(id=ORG, name="A", slug="a"))
        s.add(Assessment(id="assess-a", organization_id=ORG, template_name="AI Readiness",
                         ruleset_name="baseline", ruleset_version=1))
        s.add_all([
            Response(id="r1", assessment_id="assess-a", question_key="mfa_enabled", value=False),
            Response(id="r2", assessment_id="assess-a", question_key="sensitive_data_present", value=True),
        ])
        s.commit()
        s.close()

    def _as(self, caller):
        self.app.dependency_overrides[get_caller] = lambda: caller

    # -- the full lifecycle ------------------------------------------------ #
    def test_complete_review_approve_then_publish(self):
        # 1) org user completes -> draft recommendations
        self._as(ORG_USER)
        completed = self.client.post("/v1/assessments/assess-a/complete")
        self.assertEqual(completed.status_code, 202)
        recs = completed.json()["recommendations"]
        self.assertTrue(all(r["status"] == "draft" for r in recs))
        ids = [r["id"] for r in recs]

        # 2) consultant tries to publish while drafts pending -> 409 (approval gate)
        self._as(CONSULTANT)
        blocked = self.client.post("/v1/assessments/assess-a/report")
        self.assertEqual(blocked.status_code, 409)

        # 3) consultant edits one and approves all
        edit = self.client.patch(f"/v1/recommendations/{ids[0]}",
                                 json={"rationale": "sharper rationale", "status": "approved"})
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.json()["status"], "approved")
        for rid in ids[1:]:
            self.assertEqual(
                self.client.patch(f"/v1/recommendations/{rid}", json={"status": "approved"}).status_code,
                200,
            )

        # 4) now publishing succeeds
        published = self.client.post("/v1/assessments/assess-a/report")
        self.assertEqual(published.status_code, 201)
        self.assertEqual(published.json()["status"], "published")

        # 5) report is fetchable with a (stand-in) pre-signed URL
        got = self.client.get("/v1/assessments/assess-a/report")
        self.assertEqual(got.status_code, 200)
        self.assertIn("reports/org-a/assess-a.pdf", got.json()["pdf_url"])

    def test_org_user_cannot_approve(self):
        self._as(ORG_USER)
        self.client.post("/v1/assessments/assess-a/complete")
        rid = "assess-a:SEC-MFA-001"
        resp = self.client.patch(f"/v1/recommendations/{rid}", json={"status": "approved"})
        self.assertEqual(resp.status_code, 403)

    def test_admin_metrics(self):
        self._as(ORG_USER)
        self.client.post("/v1/assessments/assess-a/complete")
        self._as(ADMIN)
        resp = self.client.get("/v1/admin/metrics")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["organizations"], 1)
        self.assertGreaterEqual(body["ai_usage"]["recommendations_total"], 1)

    def test_org_user_cannot_view_admin_metrics(self):
        self._as(ORG_USER)
        self.assertEqual(self.client.get("/v1/admin/metrics").status_code, 403)

    def test_evaluation_run_and_list(self):
        self._as(ADMIN)
        run = self.client.post("/v1/evaluation/runs", json={})
        self.assertEqual(run.status_code, 201)
        self.assertEqual(run.json()["accuracy"], 1.0)
        self.assertEqual(run.json()["hallucination_rate"], 0.0)
        listed = self.client.get("/v1/evaluation/runs")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)


if __name__ == "__main__":
    unittest.main()
