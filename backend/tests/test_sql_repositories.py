"""Tests for the SQLAlchemy repositories.

Run on an in-memory SQLite database so they execute with no external infrastructure,
while exercising the real ORM + repository code. They prove two things:

  1. The SQL repositories enforce the same tenant-isolation contract as the in-memory
     ones (ADR-0006) — a cross-tenant id resolves to None, never another tenant's row.
  2. The AssessmentService runs **unchanged** against the SQL backend — proof that the
     repository abstraction (ADR-0002) holds.
"""

import unittest

from app.domain.access import Principal, Role
from app.errors import NotFound
from app.infra.db import Base, make_engine, make_session_factory
from app.llm.mock import MockLLMProvider
from app.repositories.base import TenantScope
from app.repositories.orm import Assessment, Organization, Response
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlRecommendationRepository,
)
from app.services.assessment_service import AssessmentService

from tests.conftest import load_baseline_ruleset

ORG_A, ORG_B = "org-a", "org-b"


def _seed(session):
    session.add_all([Organization(id=ORG_A, name="A", slug="a"),
                     Organization(id=ORG_B, name="B", slug="b")])
    session.add(Assessment(id="assess-a", organization_id=ORG_A, template_name="ai_readiness",
                           ruleset_name="baseline", ruleset_version=1))
    session.add_all([
        Response(id="r1", assessment_id="assess-a", question_key="mfa_enabled", value=False),
        Response(id="r2", assessment_id="assess-a", question_key="sensitive_data_present", value=True),
        Response(id="r3", assessment_id="assess-a", question_key="ai_governance_owner", value="none"),
        Response(id="r4", assessment_id="assess-a", question_key="model_monitoring", value="datadog"),
    ])
    session.add(Assessment(id="assess-b", organization_id=ORG_B, template_name="ai_readiness",
                           ruleset_name="baseline", ruleset_version=1))
    session.commit()


class TestSqlRepositories(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        _seed(self.session)

    def tearDown(self):
        self.session.close()

    def test_scoped_get_returns_own_row(self):
        repo = SqlAssessmentRepository(self.session)
        rec = repo.get("assess-a", TenantScope(ORG_A, "u-a"))
        self.assertIsNotNone(rec)
        self.assertEqual(rec.organization_id, ORG_A)
        # responses mapped back into the domain shape
        keys = {r["key"] for r in rec.responses}
        self.assertIn("mfa_enabled", keys)

    def test_cross_tenant_id_resolves_to_none(self):
        repo = SqlAssessmentRepository(self.session)
        # org A scope asking for org B's assessment -> None (no leak)
        self.assertIsNone(repo.get("assess-b", TenantScope(ORG_A, "u-a")))

    def test_list_is_scoped(self):
        repo = SqlAssessmentRepository(self.session)
        self.assertEqual([r.id for r in repo.list(TenantScope(ORG_A, "u-a"))], ["assess-a"])
        self.assertEqual([r.id for r in repo.list(TenantScope(ORG_B, "u-b"))], ["assess-b"])

    def test_service_runs_against_sql_backend_unchanged(self):
        svc = AssessmentService(
            assessments=SqlAssessmentRepository(self.session),
            recommendations=SqlRecommendationRepository(self.session),
            audit=SqlAuditSink(self.session),
            ruleset=load_baseline_ruleset(),
            llm=MockLLMProvider(),
        )
        principal = Principal(user_id="u-a", org_roles={ORG_A: frozenset({Role.ORG_USER})})
        recs = svc.complete(principal, ORG_A, "assess-a")
        self.session.commit()

        codes = {r.rule_code for r in recs}
        self.assertEqual(codes, {"SEC-MFA-001", "GOV-OWN-002"})  # monitoring present -> no OPS finding
        self.assertTrue(all(r.source == "llm" and r.grounding_passed for r in recs))

        # persisted + readable back through the scoped repository
        reread = svc.list_recommendations(principal, ORG_A, "assess-a")
        self.assertEqual({r.rule_code for r in reread}, codes)

        # cross-tenant id is still blocked at the repo layer through the service
        with self.assertRaises(NotFound):
            svc.complete(principal, ORG_A, "assess-b")


if __name__ == "__main__":
    unittest.main()
