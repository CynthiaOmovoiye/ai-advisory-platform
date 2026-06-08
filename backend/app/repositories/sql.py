"""SQLAlchemy implementations of the repository Protocols.

These are the production repositories. They satisfy the SAME interfaces as the
in-memory ones (app/repositories/base.py), so the service layer is unchanged — proof
that the repository abstraction (ADR-0002) pays off.

Tenant isolation (ADR-0006) is enforced here: **every** query is filtered by
``organization_id == scope.organization_id``. A cross-tenant id simply doesn't match
and resolves to ``None`` — the caller never receives another tenant's row. On Postgres
this is backed by Row-Level Security as the independent second layer; the application
filter shown here is the first.

IDs are accepted from the caller-supplied uuids in tests; in the running system they
default to ``gen_random_uuid()`` at the DB or are minted in the service. For
determinism here we derive recommendation ids from (assessment, rule_code).
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.rules.models import Severity
from app.llm.enhancement import Recommendation

from .base import (
    AssessmentRecord,
    MemberRecord,
    OrganizationRecord,
    ReportRecord,
    TenantScope,
)
from .orm import (
    Assessment,
    AuditLogRow,
    EvaluationRunRow,
    LlmCallRow,
    Organization,
    OrganizationMember,
    RecommendationRow,
    ReportRow,
)


class SqlAssessmentRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, assessment_id: str, scope: TenantScope) -> AssessmentRecord | None:
        row = self._s.execute(
            select(Assessment).where(
                Assessment.id == assessment_id,
                Assessment.organization_id == scope.organization_id,  # tenant filter
            )
        ).scalar_one_or_none()
        return _to_record(row) if row is not None else None

    def list(self, scope: TenantScope) -> list[AssessmentRecord]:
        rows = self._s.execute(
            select(Assessment).where(Assessment.organization_id == scope.organization_id)
        ).scalars()
        return [_to_record(r) for r in rows]

    def set_status(self, assessment_id: str, status: str, scope: TenantScope) -> AssessmentRecord:
        row = self._s.execute(
            select(Assessment).where(
                Assessment.id == assessment_id,
                Assessment.organization_id == scope.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise KeyError(assessment_id)
        row.status = status
        self._s.flush()
        return _to_record(row)


class SqlRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save_for_assessment(
        self, assessment_id: str, recommendations: list[Recommendation], scope: TenantScope
    ) -> None:
        # Replace any prior set for this assessment (idempotent re-completion).
        self._s.execute(
            delete(RecommendationRow).where(
                RecommendationRow.assessment_id == assessment_id,
                RecommendationRow.organization_id == scope.organization_id,
            )
        )
        for rec in recommendations:
            self._s.add(
                RecommendationRow(
                    id=rec.id or f"{assessment_id}:{rec.rule_code}",
                    organization_id=scope.organization_id,
                    assessment_id=assessment_id,
                    rule_code=rec.rule_code,
                    category=rec.category,
                    severity=rec.severity.name,
                    title=rec.title,
                    finding=rec.finding,
                    rationale=rec.rationale,
                    remediation=rec.remediation,
                    source=rec.source,
                    grounding_passed=rec.grounding_passed,
                    grounding_reasons=list(rec.grounding_reasons),
                    status=rec.status,
                    edited_by=rec.edited_by,
                )
            )
        self._s.flush()

    def get(self, recommendation_id: str, scope: TenantScope) -> Recommendation | None:
        row = self._s.execute(
            select(RecommendationRow).where(
                RecommendationRow.id == recommendation_id,
                RecommendationRow.organization_id == scope.organization_id,  # tenant filter
            )
        ).scalar_one_or_none()
        return _to_recommendation(row) if row is not None else None

    def update(self, recommendation: Recommendation, scope: TenantScope) -> Recommendation:
        row = self._s.execute(
            select(RecommendationRow).where(
                RecommendationRow.id == recommendation.id,
                RecommendationRow.organization_id == scope.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise KeyError(recommendation.id)
        row.title = recommendation.title
        row.finding = recommendation.finding
        row.rationale = recommendation.rationale
        row.remediation = recommendation.remediation
        row.status = recommendation.status
        row.edited_by = recommendation.edited_by
        self._s.flush()
        return _to_recommendation(row)

    def list_for_assessment(self, assessment_id: str, scope: TenantScope) -> list[Recommendation]:
        rows = self._s.execute(
            select(RecommendationRow)
            .where(
                RecommendationRow.assessment_id == assessment_id,
                RecommendationRow.organization_id == scope.organization_id,
            )
            .order_by(RecommendationRow.rule_code)
        ).scalars()
        return [_to_recommendation(r) for r in rows]


class SqlReportRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, report: ReportRecord, scope: TenantScope) -> None:
        row = self._s.get(ReportRow, report.id)
        if row is None:
            row = ReportRow(id=report.id, organization_id=scope.organization_id)
            self._s.add(row)
        elif row.organization_id != scope.organization_id:  # never write across tenants
            raise KeyError(report.id)
        row.assessment_id = report.assessment_id
        row.title = report.title
        row.status = report.status
        row.pdf_storage_key = report.pdf_storage_key
        self._s.flush()

    def get_for_assessment(self, assessment_id: str, scope: TenantScope) -> ReportRecord | None:
        row = self._s.execute(
            select(ReportRow).where(
                ReportRow.assessment_id == assessment_id,
                ReportRow.organization_id == scope.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return ReportRecord(
            id=row.id,
            organization_id=row.organization_id,
            assessment_id=row.assessment_id,
            title=row.title,
            status=row.status,
            pdf_storage_key=row.pdf_storage_key,
        )


class SqlEvaluationRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, run) -> None:  # run: EvaluationRunRecord (imported lazily to avoid a cycle)
        self._s.add(
            EvaluationRunRow(
                id=run.id,
                dataset_name=run.dataset_name,
                ruleset_name=run.ruleset_name,
                model_id=run.model_id,
                status=run.status,
                accuracy=run.accuracy,
                consistency=run.consistency,
                completeness=run.completeness,
                hallucination_rate=run.hallucination_rate,
                item_count=run.item_count,
                triggered_by=run.triggered_by,
            )
        )
        self._s.flush()

    def list_recent(self, limit: int = 50) -> list:
        from app.services.evaluation_service import EvaluationRunRecord

        rows = self._s.execute(
            select(EvaluationRunRow).order_by(EvaluationRunRow.created_at.desc()).limit(limit)
        ).scalars()
        return [
            EvaluationRunRecord(
                id=r.id,
                dataset_name=r.dataset_name,
                ruleset_name=r.ruleset_name,
                model_id=r.model_id,
                status=r.status,
                accuracy=r.accuracy,
                consistency=r.consistency,
                completeness=r.completeness,
                hallucination_rate=r.hallucination_rate,
                item_count=r.item_count,
                triggered_by=r.triggered_by,
            )
            for r in rows
        ]


class SqlAuditSink:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self, *, actor_user_id: str, organization_id: str, action: str, entity_id: str
    ) -> None:
        self._s.add(
            AuditLogRow(
                id=str(uuid.uuid4()),
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                action=action,
                entity_id=entity_id,
            )
        )
        self._s.flush()


# --- ORM -> domain mapping (keeps SQLAlchemy out of the service) ------------- #
def _to_record(row: Assessment) -> AssessmentRecord:
    return AssessmentRecord(
        id=row.id,
        organization_id=row.organization_id,
        template_name=row.template_name,
        ruleset_name=row.ruleset_name,
        ruleset_version=row.ruleset_version,
        responses=tuple({"key": r.question_key, "value": r.value} for r in row.responses),
        status=row.status,
    )


def _to_recommendation(row: RecommendationRow) -> Recommendation:
    return Recommendation(
        finding_id=row.rule_code,
        rule_code=row.rule_code,
        category=row.category,
        severity=Severity[row.severity],
        title=row.title,
        finding=row.finding,
        rationale=row.rationale,
        remediation=row.remediation,
        source=row.source,  # type: ignore[arg-type]
        grounding_passed=row.grounding_passed,
        grounding_reasons=tuple(row.grounding_reasons or ()),
        status=row.status,
        id=row.id,
        edited_by=row.edited_by,
    )


class SqlOrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, record: OrganizationRecord) -> None:
        self._s.add(Organization(id=record.id, name=record.name, slug=record.slug))
        self._s.flush()

    def get(self, organization_id: str) -> OrganizationRecord | None:
        row = self._s.get(Organization, organization_id)
        return OrganizationRecord(id=row.id, name=row.name, slug=row.slug) if row else None

    def slug_exists(self, slug: str) -> bool:
        return (
            self._s.execute(select(Organization.id).where(Organization.slug == slug)).first()
            is not None
        )


class SqlMemberRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        member: MemberRecord,
        scope: TenantScope,
        *,
        invite_token_hash: str | None,
        invited_by: str,
    ) -> None:
        self._s.add(
            OrganizationMember(
                id=member.id,
                organization_id=scope.organization_id,  # scope owns the org, not request input
                user_id=member.user_id,
                invited_email=member.invited_email,
                role=member.role,
                status=member.status,
                invited_by=invited_by,
                invite_token_hash=invite_token_hash,
            )
        )
        self._s.flush()

    def list(self, scope: TenantScope) -> list[MemberRecord]:
        rows = self._s.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == scope.organization_id)
            .order_by(OrganizationMember.created_at)
        ).scalars()
        return [_to_member(r) for r in rows]

    def get(self, member_id: str, scope: TenantScope) -> MemberRecord | None:
        row = self._s.execute(
            select(OrganizationMember).where(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == scope.organization_id,  # tenant filter
            )
        ).scalar_one_or_none()
        return _to_member(row) if row else None

    def set_status(self, member_id: str, status: str, scope: TenantScope) -> MemberRecord:
        row = self._s.execute(
            select(OrganizationMember).where(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == scope.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise KeyError(member_id)
        row.status = status
        self._s.flush()
        return _to_member(row)

    def email_exists(self, email: str, scope: TenantScope) -> bool:
        return (
            self._s.execute(
                select(OrganizationMember.id).where(
                    OrganizationMember.organization_id == scope.organization_id,
                    OrganizationMember.invited_email == email,
                )
            ).first()
            is not None
        )


def _to_member(row: OrganizationMember) -> MemberRecord:
    return MemberRecord(
        id=row.id,
        organization_id=row.organization_id,
        invited_email=row.invited_email,
        role=row.role,
        status=row.status,
        user_id=row.user_id,
    )


class SqlLlmCallSink:
    """Persists per-call LLM telemetry to the llm_calls table (satisfies LlmCallSink)."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        model_id: str,
        status: str,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        cost_estimate=None,
        organization_id: str | None,
        assessment_id: str | None,
        correlation_id: str | None,
    ) -> None:
        self._s.add(
            LlmCallRow(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                assessment_id=assessment_id,
                model_id=model_id,
                status=status,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate=cost_estimate,
                correlation_id=correlation_id,
            )
        )
        self._s.flush()
