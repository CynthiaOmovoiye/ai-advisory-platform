"""API DTOs (Pydantic v2) for recommendations — the API contract types.

These are the *only* shapes that cross the HTTP boundary. Domain/ORM objects never
do (ADR-0002). Matches the `Recommendation` schema in docs/api/openapi.yaml.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.llm.enhancement import Recommendation


class Provenance(BaseModel):
    source: Literal["llm", "fallback"]
    grounding_passed: bool | None


class RecommendationOut(BaseModel):
    id: str | None
    rule_code: str
    category: str
    severity: str
    title: str
    finding: str
    rationale: str
    remediation: str
    status: str
    provenance: Provenance

    @classmethod
    def from_domain(cls, rec: Recommendation) -> RecommendationOut:
        return cls(
            id=rec.id,
            rule_code=rec.rule_code,
            category=rec.category,
            severity=rec.severity.name.lower(),
            title=rec.title,
            finding=rec.finding,
            rationale=rec.rationale,
            remediation=rec.remediation,
            status=rec.status,
            provenance=Provenance(source=rec.source, grounding_passed=rec.grounding_passed),
        )


class RecommendationPatch(BaseModel):
    """Consultant edit + review action. Narrative fields are editable; status moves the
    review forward. Deterministic provenance (rule, severity, source) is NOT editable."""

    title: str | None = None
    finding: str | None = None
    rationale: str | None = None
    remediation: str | None = None
    status: Literal["approved", "rejected"] | None = None


class CompleteAssessmentResponse(BaseModel):
    assessment_id: str
    status: str
    recommendations: list[RecommendationOut]
