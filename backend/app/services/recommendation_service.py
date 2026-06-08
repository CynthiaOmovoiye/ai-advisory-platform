"""Recommendation service — the consultant workspace (Module 9).

Consultants review the (already grounded) recommendations, edit the narrative, and
approve or reject each one. This is the human-in-the-loop gate before a report is
published. Every mutation is authorized (RECOMMENDATION_EDIT / _APPROVE), tenant-scoped,
and audited.

Note the boundary the consultant *cannot* cross: they edit narrative fields (title,
finding text, rationale, remediation) and the review status — they do not change which
rule fired. The deterministic provenance (rule_code, severity, source, grounding) is
preserved (ADR-0003).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.access import Permission, Principal, authorize
from app.errors import AppError, NotFound
from app.llm.enhancement import Recommendation
from app.repositories.base import AuditSink, RecommendationRepository, TenantScope

_EDITABLE_STATUSES = {"draft", "edited", "approved", "rejected"}
_REVIEW_STATUSES = {"approved", "rejected"}


class InvalidStatus(AppError):
    code = "invalid_status"
    http_status = 422


@dataclass
class RecommendationService:
    recommendations: RecommendationRepository
    audit: AuditSink

    def edit(
        self,
        principal: Principal,
        organization_id: str,
        recommendation_id: str,
        *,
        title: str | None = None,
        finding: str | None = None,
        rationale: str | None = None,
        remediation: str | None = None,
    ) -> Recommendation:
        authorize(principal, Permission.RECOMMENDATION_EDIT, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        rec = self._load(recommendation_id, scope)

        updated = replace(
            rec,
            title=title if title is not None else rec.title,
            finding=finding if finding is not None else rec.finding,
            rationale=rationale if rationale is not None else rec.rationale,
            remediation=remediation if remediation is not None else rec.remediation,
            status="edited",
            edited_by=principal.user_id,
        )
        saved = self.recommendations.update(updated, scope)
        self._audit(scope, "recommendation.edited", recommendation_id)
        return saved

    def set_status(
        self, principal: Principal, organization_id: str, recommendation_id: str, status: str
    ) -> Recommendation:
        if status not in _REVIEW_STATUSES:
            raise InvalidStatus(f"status must be one of {sorted(_REVIEW_STATUSES)}")
        authorize(principal, Permission.RECOMMENDATION_APPROVE, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        rec = self._load(recommendation_id, scope)

        saved = self.recommendations.update(
            replace(rec, status=status, edited_by=principal.user_id), scope
        )
        self._audit(scope, f"recommendation.{status}", recommendation_id)
        return saved

    # -- internals --------------------------------------------------------- #
    def _load(self, recommendation_id: str, scope: TenantScope) -> Recommendation:
        rec = self.recommendations.get(recommendation_id, scope)
        if rec is None:
            raise NotFound("recommendation not found")  # cross-tenant ids resolve here too
        return rec

    def _audit(self, scope: TenantScope, action: str, entity_id: str) -> None:
        self.audit.record(
            actor_user_id=scope.acting_user_id,
            organization_id=scope.organization_id,
            action=action,
            entity_id=entity_id,
        )
