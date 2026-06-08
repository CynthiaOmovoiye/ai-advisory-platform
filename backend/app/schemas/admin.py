"""Admin + evaluation DTOs (Modules 6 & 10)."""

from __future__ import annotations

from pydantic import BaseModel

from app.services.evaluation_service import EvaluationRunRecord
from app.services.metrics_service import AdminMetrics


class AdminMetricsOut(BaseModel):
    organizations: int
    assessments_total: int
    assessments_by_status: dict[str, int]
    reports_published: int
    ai_usage: dict[str, object]
    evaluation: dict[str, object]

    @classmethod
    def from_domain(cls, m: AdminMetrics) -> AdminMetricsOut:
        return cls(
            organizations=m.organizations,
            assessments_total=m.assessments_total,
            assessments_by_status=m.assessments_by_status,
            reports_published=m.reports_published,
            ai_usage=m.ai_usage,
            evaluation=m.evaluation,
        )


class EvaluationRunOut(BaseModel):
    id: str
    dataset_name: str
    ruleset_name: str
    model_id: str
    status: str
    accuracy: float
    consistency: float
    completeness: float
    hallucination_rate: float
    item_count: int

    @classmethod
    def from_domain(cls, r: EvaluationRunRecord) -> EvaluationRunOut:
        return cls(
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
        )


class TriggerEvaluationRequest(BaseModel):
    dataset_name: str | None = "baseline-readiness"
