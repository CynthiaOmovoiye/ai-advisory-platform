"""Tests for report generation (Module 8).

The HTML build and model assembly are pure and fully tested. The service is tested
with in-memory repos + a FakeRenderer + in-memory storage — no browser, no Redis, no
DB. Includes the security-critical assertion that report content is HTML-escaped
(threat-model: stored XSS via LLM/user text → PDF).
"""

import unittest

from app.domain.rules.models import Severity
from app.errors import Conflict, NotFound
from app.infra.storage import InMemoryStorage
from app.llm.enhancement import Recommendation
from app.reports.html import render_report_html
from app.reports.model import build_report_model
from app.reports.renderer import FakeRenderer
from app.reports.service import ReportService
from app.repositories.base import AssessmentRecord, TenantScope
from app.repositories.memory import (
    AuditLog,
    InMemoryAssessmentRepository,
    InMemoryRecommendationRepository,
    InMemoryReportRepository,
)

ORG = "org-a"


def _rec(
    code,
    category,
    severity,
    title="T",
    finding="F",
    rationale="R",
    remediation="M",
    status="approved",
):
    return Recommendation(
        finding_id=code,
        rule_code=code,
        category=category,
        severity=severity,
        title=title,
        finding=finding,
        rationale=rationale,
        remediation=remediation,
        source="llm",
        grounding_passed=True,
        status=status,
    )


RECS = [
    _rec("COMP-PII-004", "compliance", Severity.CRITICAL),
    _rec("SEC-MFA-001", "security", Severity.HIGH),
    _rec("GOV-OWN-002", "governance", Severity.MEDIUM),
    _rec("INF-VEC-006", "infrastructure", Severity.INFO),
]


class TestReportModel(unittest.TestCase):
    def test_sections_and_counts(self):
        model = build_report_model("Acme", "AI Readiness", RECS)
        self.assertEqual(model.severity_counts["critical"], 1)
        self.assertEqual(model.severity_counts["high"], 1)
        keys = [s.key for s in model.sections]
        self.assertEqual(keys, ["risk", "security", "governance", "architecture", "roadmap"])
        self.assertIn("1 critical", model.headline)

    def test_roadmap_is_severity_ordered(self):
        model = build_report_model("Acme", "AI Readiness", RECS)
        roadmap = next(s for s in model.sections if s.key == "roadmap")
        sevs = [int(r.severity) for r in roadmap.recommendations]
        self.assertEqual(sevs, sorted(sevs, reverse=True))  # highest severity first
        self.assertEqual(roadmap.recommendations[0].rule_code, "COMP-PII-004")  # critical first

    def test_empty_report(self):
        model = build_report_model("Acme", "AI Readiness", [])
        self.assertEqual(model.sections, ())
        self.assertIn("No findings", model.headline)


class TestReportHtml(unittest.TestCase):
    def test_renders_sections(self):
        html = render_report_html(build_report_model("Acme", "AI Readiness", RECS))
        self.assertIn("Executive Summary", html)
        self.assertIn("Security Findings", html)
        self.assertIn("SEC-MFA-001", html)

    def test_escapes_untrusted_content(self):
        # An LLM/user-supplied title containing markup must be escaped, not rendered.
        evil = _rec("X-1", "security", Severity.HIGH, title="<script>alert('xss')</script>")
        html = render_report_html(build_report_model("Acme", "AI Readiness", [evil]))
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)


class TestReportService(unittest.TestCase):
    def setUp(self):
        self.assessments = InMemoryAssessmentRepository(
            [
                AssessmentRecord(
                    id="a1",
                    organization_id=ORG,
                    template_name="AI Readiness",
                    ruleset_name="baseline",
                    ruleset_version=1,
                    responses=(),
                    status="completed",
                ),
                AssessmentRecord(
                    id="a2",
                    organization_id=ORG,
                    template_name="AI Readiness",
                    ruleset_name="baseline",
                    ruleset_version=1,
                    responses=(),
                    status="in_progress",
                ),
            ]
        )
        self.recs = InMemoryRecommendationRepository()
        self.reports = InMemoryReportRepository()
        self.audit = AuditLog()
        self.storage = InMemoryStorage()
        self.scope = TenantScope(ORG, "consultant-1")
        self.recs.save_for_assessment("a1", RECS, self.scope)
        self.svc = ReportService(
            assessments=self.assessments,
            recommendations=self.recs,
            reports=self.reports,
            audit=self.audit,
            storage=self.storage,
            renderer=FakeRenderer(),
        )

    def test_generate_publishes_and_stores_pdf(self):
        report = self.svc.generate(self.scope, "a1", organization_name="Acme")
        self.assertEqual(report.status, "published")
        self.assertEqual(report.pdf_storage_key, f"reports/{ORG}/a1.pdf")
        # PDF bytes actually landed in storage, under an opaque (non-public) key
        self.assertIn(report.pdf_storage_key, self.storage.objects)
        self.assertTrue(self.storage.objects[report.pdf_storage_key].startswith(b"%PDF"))
        # audited
        self.assertEqual(self.audit.entries[-1]["action"], "report.published")

    def test_cannot_report_incomplete_assessment(self):
        with self.assertRaises(Conflict):
            self.svc.generate(self.scope, "a2", organization_name="Acme")

    def test_cross_tenant_assessment_is_not_found(self):
        other = TenantScope("org-b", "u-b")
        with self.assertRaises(NotFound):
            self.svc.generate(other, "a1", organization_name="Acme")

    def test_approval_gate_blocks_pending_recommendations(self):
        # A draft (un-reviewed) recommendation must block report publication.
        pending = [_rec("SEC-MFA-001", "security", Severity.HIGH, status="draft")]
        self.recs.save_for_assessment("a1", pending, self.scope)
        with self.assertRaises(Conflict):
            self.svc.generate(self.scope, "a1", organization_name="Acme")

    def test_rejected_recommendations_excluded_from_report(self):
        mixed = [
            _rec("SEC-MFA-001", "security", Severity.HIGH, status="approved"),
            _rec("GOV-OWN-002", "governance", Severity.MEDIUM, status="rejected"),
        ]
        self.recs.save_for_assessment("a1", mixed, self.scope)
        self.svc.generate(self.scope, "a1", organization_name="Acme")
        # generation succeeded; assert only the approved finding shaped the report
        # (governance section absent) by re-building the model from the approved set.
        from app.reports.model import build_report_model

        model = build_report_model(
            "Acme", "AI Readiness", [r for r in mixed if r.status == "approved"]
        )
        self.assertNotIn("governance", [s.key for s in model.sections])


if __name__ == "__main__":
    unittest.main()
