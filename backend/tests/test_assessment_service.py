"""Tests for the assessment service — the end-to-end use-case, and the two
independent isolation layers (ADR-0006), proven together."""

import unittest

from app.domain.access import Principal, Role
from app.errors import Conflict, Forbidden, NotFound
from app.llm.mock import MockLLMProvider
from app.repositories.base import TenantScope
from app.repositories.memory import (
    AssessmentRecord,
    AuditLog,
    InMemoryAssessmentRepository,
    InMemoryRecommendationRepository,
)
from app.services.assessment_service import AssessmentService

from tests.conftest import load_baseline_ruleset

ORG_A = "org-a"
ORG_B = "org-b"

# Org A's assessment with responses that should trigger findings.
ASSESSMENT_A = AssessmentRecord(
    id="assess-a",
    organization_id=ORG_A,
    template_name="ai_readiness",
    ruleset_name="baseline",
    ruleset_version=1,
    responses=(
        {"key": "mfa_enabled", "value": False},
        {"key": "sensitive_data_present", "value": True},
        {"key": "ai_governance_owner", "value": "none"},
    ),
)
ASSESSMENT_B = AssessmentRecord(
    id="assess-b",
    organization_id=ORG_B,
    template_name="ai_readiness",
    ruleset_name="baseline",
    ruleset_version=1,
    responses=({"key": "ai_governance_owner", "value": "none"},),
)

org_user_a = Principal(user_id="u-a", org_roles={ORG_A: frozenset({Role.ORG_USER})})
org_user_b = Principal(user_id="u-b", org_roles={ORG_B: frozenset({Role.ORG_USER})})
admin = Principal(user_id="admin", global_roles=frozenset({Role.ADMIN}))


class TestAssessmentService(unittest.TestCase):
    def setUp(self):
        self.assessments = InMemoryAssessmentRepository([ASSESSMENT_A, ASSESSMENT_B])
        self.recs = InMemoryRecommendationRepository()
        self.audit = AuditLog()
        self.svc = AssessmentService(
            assessments=self.assessments,
            recommendations=self.recs,
            audit=self.audit,
            ruleset=load_baseline_ruleset(),
            llm=MockLLMProvider(),
        )

    def test_happy_path_completes_and_produces_recommendations(self):
        recs = self.svc.complete(org_user_a, ORG_A, "assess-a")
        codes = {r.rule_code for r in recs}
        # SEC-MFA-001 (no MFA + sensitive data), GOV-OWN-002 (no owner), and
        # OPS-OBS-005 (no model_monitoring key present) all fire on this fixture.
        self.assertEqual(codes, {"SEC-MFA-001", "GOV-OWN-002", "OPS-OBS-005"})
        # status advanced + audit recorded
        scope_a = TenantScope(organization_id=ORG_A, acting_user_id="u-a")
        self.assertEqual(self.assessments.get("assess-a", scope_a).status, "completed")
        self.assertEqual(len(self.audit.entries), 1)
        self.assertEqual(self.audit.entries[0]["action"], "assessment.completed")
        self.assertEqual(self.audit.entries[0]["actor_user_id"], "u-a")

    def test_authz_layer_blocks_foreign_org_user(self):
        # Org B's user has no rights in org A ⇒ Forbidden, before any data is touched.
        with self.assertRaises(Forbidden):
            self.svc.complete(org_user_b, ORG_A, "assess-a")

    def test_repo_layer_blocks_cross_tenant_id_even_when_authorized(self):
        # Defense in depth: org A's user IS authorized in org A, but asks for org B's
        # assessment id under an org-A scope. The repository refuses → NotFound,
        # never org B's data. (This is the layer that catches an authz bug.)
        with self.assertRaises(NotFound):
            self.svc.complete(org_user_a, ORG_A, "assess-b")

    def test_no_cross_tenant_data_leak_on_read(self):
        admin_recs = self.svc.complete(admin, ORG_A, "assess-a")
        self.assertTrue(admin_recs)
        # org_user_b cannot read org A's recommendations at all.
        with self.assertRaises(Forbidden):
            self.svc.list_recommendations(org_user_b, ORG_A, "assess-a")

    def test_completion_is_idempotent_guarded(self):
        self.svc.complete(org_user_a, ORG_A, "assess-a")
        with self.assertRaises(Conflict):
            self.svc.complete(org_user_a, ORG_A, "assess-a")

    def test_admin_is_cross_tenant(self):
        # Admin can complete in either org (an audited widening, not a hole).
        self.assertTrue(self.svc.complete(admin, ORG_B, "assess-b"))


if __name__ == "__main__":
    unittest.main()
