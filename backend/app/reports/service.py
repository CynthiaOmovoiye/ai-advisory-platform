"""Report service — orchestrates report generation (Module 8).

Runs in the Celery worker, off the request path (architecture §2). Like the
assessment service it depends on the repository Protocols + interfaces (storage,
renderer), so it is testable with in-memory repos + a fake renderer.

Flow: load (tenant-scoped) → assemble model (pure) → HTML (escaped) → PDF (Playwright)
→ store under an opaque key (outside public paths) → persist the report row + audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.errors import Conflict, NotFound
from app.infra.storage import ObjectStorage
from app.repositories.base import (
    AssessmentRepository,
    AuditSink,
    RecommendationRepository,
    ReportRecord,
    ReportRepository,
    TenantScope,
)

from .html import render_report_html
from .model import build_report_model
from .renderer import ReportRenderer


@dataclass
class ReportService:
    assessments: AssessmentRepository
    recommendations: RecommendationRepository
    reports: ReportRepository
    audit: AuditSink
    storage: ObjectStorage
    renderer: ReportRenderer

    def validate_publishable(self, scope: TenantScope, assessment_id: str) -> None:
        """Raise NotFound/Conflict if the assessment can't be reported yet. Called at
        enqueue time so the caller gets an immediate error, and again inside the worker
        as defense before rendering."""
        assessment = self.assessments.get(assessment_id, scope)
        if assessment is None:
            raise NotFound("assessment not found")  # cross-tenant ids resolve here too
        if assessment.status != "completed":
            raise Conflict("assessment must be completed before reporting")
        recs = self.recommendations.list_for_assessment(assessment_id, scope)
        # Approval gate (Module 9): a report cannot be published while any recommendation
        # is still awaiting consultant review.
        pending = [r for r in recs if r.status in ("draft", "edited")]
        if pending:
            raise Conflict(
                f"{len(pending)} recommendation(s) still awaiting review; "
                "approve or reject before publishing"
            )

    def queue(
        self, scope: TenantScope, assessment_id: str, *, organization_name: str
    ) -> ReportRecord:
        """Validate, then persist a 'queued' report row. The actual render happens in the
        worker (see app/worker/tasks.py); this returns immediately so the API stays fast."""
        self.validate_publishable(scope, assessment_id)
        report = ReportRecord(
            id=f"report:{assessment_id}",
            organization_id=scope.organization_id,
            assessment_id=assessment_id,
            title=f"AI Readiness Report — {organization_name}",
            status="queued",
            pdf_storage_key=None,
        )
        self.reports.save(report, scope)
        return report

    def generate(
        self, scope: TenantScope, assessment_id: str, *, organization_name: str
    ) -> ReportRecord:
        self.validate_publishable(scope, assessment_id)  # raises if assessment is missing
        assessment = self.assessments.get(assessment_id, scope)
        assert assessment is not None  # guaranteed by validate_publishable above
        recs = self.recommendations.list_for_assessment(assessment_id, scope)
        approved = [r for r in recs if r.status == "approved"]

        model = build_report_model(
            organization_name=organization_name,
            assessment_title=assessment.template_name,
            recommendations=approved,
        )
        html = render_report_html(model)  # escaped, untrusted-safe
        pdf = self.renderer.render_pdf(html)  # Playwright in prod; offline render

        # Opaque, tenant-namespaced key — never a public path (security-review §5).
        key = f"reports/{scope.organization_id}/{assessment_id}.pdf"
        self.storage.put(key, pdf, content_type="application/pdf")

        report = ReportRecord(
            id=f"report:{assessment_id}",
            organization_id=scope.organization_id,
            assessment_id=assessment_id,
            title=f"AI Readiness Report — {organization_name}",
            status="published",
            pdf_storage_key=key,
        )
        self.reports.save(report, scope)
        self.audit.record(
            actor_user_id=scope.acting_user_id,
            organization_id=scope.organization_id,
            action="report.published",
            entity_id=report.id,
        )
        return report
