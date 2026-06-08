"""In-memory repositories — the offline-testable implementation of the persistence
contract.

These exist so the service layer and the tenant-isolation behaviour can be tested
with zero infrastructure. They enforce the SAME tenant-scoping contract as the real
SQLAlchemy repositories (ADR-0006): a scoped lookup for a row that belongs to another
org returns ``None`` (which the service surfaces as NotFound) — it never returns the
other tenant's data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from app.llm.enhancement import Recommendation

from .base import AssessmentRecord, ReportRecord, TenantScope

__all__ = [
    "AssessmentRecord",  # re-exported for convenience; canonical home is base.py
    "InMemoryAssessmentRepository",
    "InMemoryRecommendationRepository",
    "InMemoryReportRepository",
    "AuditLog",
]


class InMemoryAssessmentRepository:
    def __init__(self, records: Optional[list[AssessmentRecord]] = None) -> None:
        self._by_id: dict[str, AssessmentRecord] = {r.id: r for r in (records or [])}

    def get(self, assessment_id: str, scope: TenantScope) -> Optional[AssessmentRecord]:
        """Tenant-scoped fetch. A row outside the scope is invisible — returns None,
        exactly as a `WHERE organization_id = scope` query (or RLS) would."""
        record = self._by_id.get(assessment_id)
        if record is None or not scope.owns(record.organization_id):
            return None
        return record

    def list(self, scope: TenantScope) -> list[AssessmentRecord]:
        return [r for r in self._by_id.values() if scope.owns(r.organization_id)]

    def set_status(self, assessment_id: str, status: str, scope: TenantScope) -> AssessmentRecord:
        record = self.get(assessment_id, scope)
        if record is None:
            raise KeyError(assessment_id)  # caller (service) maps to NotFound
        updated = replace(record, status=status)
        self._by_id[assessment_id] = updated
        return updated


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        # keyed by org to make accidental cross-tenant reads structurally impossible
        self._by_org: dict[str, dict[str, list[Recommendation]]] = {}

    def save_for_assessment(
        self, assessment_id: str, recommendations: list[Recommendation], scope: TenantScope
    ) -> None:
        org = self._by_org.setdefault(scope.organization_id, {})
        # assign a stable id if the caller didn't (mirrors the SQL repo's id scheme)
        org[assessment_id] = [
            replace(r, id=r.id or f"{assessment_id}:{r.rule_code}") for r in recommendations
        ]

    def list_for_assessment(self, assessment_id: str, scope: TenantScope) -> list[Recommendation]:
        return list(self._by_org.get(scope.organization_id, {}).get(assessment_id, []))

    def get(self, recommendation_id: str, scope: TenantScope) -> Optional[Recommendation]:
        for recs in self._by_org.get(scope.organization_id, {}).values():
            for r in recs:
                if r.id == recommendation_id:
                    return r
        return None  # not in this tenant's scope -> invisible

    def update(self, recommendation: Recommendation, scope: TenantScope) -> Recommendation:
        for recs in self._by_org.get(scope.organization_id, {}).values():
            for i, r in enumerate(recs):
                if r.id == recommendation.id:
                    recs[i] = recommendation
                    return recommendation
        raise KeyError(recommendation.id)


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._by_org: dict[str, dict[str, ReportRecord]] = {}

    def save(self, report: ReportRecord, scope: TenantScope) -> None:
        self._by_org.setdefault(scope.organization_id, {})[report.assessment_id] = report

    def get_for_assessment(self, assessment_id: str, scope: TenantScope) -> Optional[ReportRecord]:
        return self._by_org.get(scope.organization_id, {}).get(assessment_id)


@dataclass
class AuditLog:
    """Append-only audit sink (mirrors the audit_logs table). In production this is a
    repository writing to an append-only table; here it's an in-memory list."""

    entries: list[dict] = field(default_factory=list)

    def record(self, *, actor_user_id: str, organization_id: str, action: str, entity_id: str) -> None:
        self.entries.append(
            {
                "actor_user_id": actor_user_id,
                "organization_id": organization_id,
                "action": action,
                "entity_id": entity_id,
            }
        )
