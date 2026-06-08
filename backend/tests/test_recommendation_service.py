"""Tests for the consultant workspace (Module 9): edit, approve, reject —
authorization, tenant scope, audit, and the invariant that provenance is preserved."""

import unittest

from app.domain.access import Principal, Role
from app.domain.rules.models import Severity
from app.errors import Forbidden, NotFound
from app.llm.enhancement import Recommendation
from app.repositories.base import TenantScope
from app.repositories.memory import AuditLog, InMemoryRecommendationRepository
from app.services.recommendation_service import InvalidStatus, RecommendationService

ORG = "org-a"


def _rec(code="SEC-MFA-001"):
    return Recommendation(
        finding_id=code,
        rule_code=code,
        category="security",
        severity=Severity.HIGH,
        title="Enforce MFA",
        finding="MFA off",
        rationale="r",
        remediation="m",
        source="llm",
        grounding_passed=True,
        status="draft",
    )


consultant = Principal(user_id="c1", global_roles=frozenset({Role.CONSULTANT}))
org_user = Principal(user_id="u1", org_roles={ORG: frozenset({Role.ORG_USER})})


class TestRecommendationService(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRecommendationRepository()
        self.audit = AuditLog()
        self.scope = TenantScope(ORG, "c1")
        self.repo.save_for_assessment("a1", [_rec()], self.scope)
        self.rec_id = "a1:SEC-MFA-001"
        self.svc = RecommendationService(recommendations=self.repo, audit=self.audit)

    def test_edit_updates_narrative_and_marks_edited(self):
        out = self.svc.edit(consultant, ORG, self.rec_id, rationale="clearer rationale")
        self.assertEqual(out.rationale, "clearer rationale")
        self.assertEqual(out.status, "edited")
        self.assertEqual(out.edited_by, "c1")
        # provenance preserved — the consultant cannot change which rule fired
        self.assertEqual(out.rule_code, "SEC-MFA-001")
        self.assertEqual(out.severity, Severity.HIGH)
        self.assertEqual(out.source, "llm")
        self.assertEqual(self.audit.entries[-1]["action"], "recommendation.edited")

    def test_approve(self):
        out = self.svc.set_status(consultant, ORG, self.rec_id, "approved")
        self.assertEqual(out.status, "approved")
        self.assertEqual(self.audit.entries[-1]["action"], "recommendation.approved")

    def test_reject(self):
        out = self.svc.set_status(consultant, ORG, self.rec_id, "rejected")
        self.assertEqual(out.status, "rejected")

    def test_invalid_status_rejected(self):
        with self.assertRaises(InvalidStatus):
            self.svc.set_status(consultant, ORG, self.rec_id, "draft")

    def test_org_user_cannot_edit_or_approve(self):
        with self.assertRaises(Forbidden):
            self.svc.edit(org_user, ORG, self.rec_id, title="x")
        with self.assertRaises(Forbidden):
            self.svc.set_status(org_user, ORG, self.rec_id, "approved")

    def test_cross_tenant_recommendation_not_found(self):
        with self.assertRaises(NotFound):
            self.svc.edit(consultant, "org-b", self.rec_id, title="x")


if __name__ == "__main__":
    unittest.main()
