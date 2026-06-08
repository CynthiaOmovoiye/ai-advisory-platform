"""Assessment service — the `complete-assessment` use-case.

This is the service layer from ADR-0002: it owns the *use-case* and the transaction
boundary, orchestrating authorization + repositories + the domain rule engine + the
LLM enhancement pipeline. It contains **no SQL** (that's the repositories) and **no
HTTP** (that's the API layer). It is where the architecture's headline flow lives:

    authorize → load (tenant-scoped) → rule engine → enhance (grounded) → persist → audit

Dependencies are injected (the ruleset, the LLM provider, the repositories), so the
service is testable with the in-memory repos and the mock provider — no DB, no
network, no API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.access import Permission, Principal, authorize
from app.domain.rules import engine
from app.domain.rules.models import Ruleset, facts_from_responses
from app.errors import Conflict, NotFound
from app.llm.enhancement import Recommendation, enhance_findings
from app.llm.provider import LLMProvider
from app.repositories.base import (
    AssessmentRepository,
    AuditSink,
    RecommendationRepository,
    TenantScope,
)


@dataclass
class AssessmentService:
    # Depend on the Protocols, not concrete classes — the in-memory and SQLAlchemy
    # repositories are interchangeable here (ADR-0002, repository abstraction).
    assessments: AssessmentRepository
    recommendations: RecommendationRepository
    audit: AuditSink
    ruleset: Ruleset
    llm: LLMProvider

    def complete(
        self, principal: Principal, organization_id: str, assessment_id: str
    ) -> list[Recommendation]:
        """Complete an assessment and produce recommendations.

        ``organization_id`` is the tenant context established by the auth layer (from
        the session), not free request input. The two isolation layers both apply:
        the authorization check refuses a principal with no rights in this org, and
        the tenant-scoped repository refuses a cross-org assessment id.
        """
        # 1) Authorize — default deny (ADR-0007). An org_user of another org has no
        #    rights here and is refused before any data is touched.
        authorize(principal, Permission.ASSESSMENT_COMPLETE, organization_id)

        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)

        # 2) Load, tenant-scoped (ADR-0006). A cross-org id resolves to NotFound,
        #    never to another tenant's row.
        record = self.assessments.get(assessment_id, scope)
        if record is None:
            raise NotFound("assessment not found")
        if record.status == "completed":
            raise Conflict("assessment already completed")  # idempotency guard

        # 3) Rule engine — deterministic source of truth (ADR-0003).
        facts = facts_from_responses(record.responses)
        findings = engine.evaluate(self.ruleset, facts)

        # 4) LLM enhancement, gated by grounding, with deterministic fallback.
        recommendations = enhance_findings(findings, self.llm)

        # 5) Persist + advance status (the transaction boundary).
        self.recommendations.save_for_assessment(assessment_id, recommendations, scope)
        self.assessments.set_status(assessment_id, "completed", scope)

        # 6) Audit (append-only) — who completed what, in which org.
        self.audit.record(
            actor_user_id=principal.user_id,
            organization_id=organization_id,
            action="assessment.completed",
            entity_id=assessment_id,
        )
        # Return the *persisted* recommendations so callers get their stable ids and
        # review status (the freshly-built objects carry no id yet).
        return self.recommendations.list_for_assessment(assessment_id, scope)

    def list_recommendations(
        self, principal: Principal, organization_id: str, assessment_id: str
    ) -> list[Recommendation]:
        authorize(principal, Permission.ASSESSMENT_READ, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        if self.assessments.get(assessment_id, scope) is None:
            raise NotFound("assessment not found")
        return self.recommendations.list_for_assessment(assessment_id, scope)
