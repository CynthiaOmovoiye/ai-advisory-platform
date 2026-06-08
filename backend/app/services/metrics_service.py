"""Admin metrics service (Module 10 → admin dashboard).

Aggregates real, persisted data into the operational view a system admin needs:
organization/assessment/report counts, **AI usage & quality** (recommendation
volume, LLM vs deterministic-fallback split, grounding pass rate), and the latest
evaluation scores. This is the operational signal that distinguishes a real AI system
from a demo (architecture §7) — built from data the system already stores.

Metrics are inherently aggregate queries, so this service talks to the session
directly (still behind a thin repository for testability).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.repositories.orm import (
    Assessment,
    EvaluationRunRow,
    Organization,
    RecommendationRow,
    ReportRow,
)


@dataclass
class AdminMetrics:
    organizations: int = 0
    assessments_total: int = 0
    assessments_by_status: dict[str, int] = field(default_factory=dict)
    reports_published: int = 0
    ai_usage: dict[str, object] = field(default_factory=dict)
    evaluation: dict[str, object] = field(default_factory=dict)


class SqlMetricsRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def collect(self) -> AdminMetrics:
        s = self._s
        orgs = s.scalar(select(func.count()).select_from(Organization)) or 0

        assessments_total = s.scalar(select(func.count()).select_from(Assessment)) or 0
        by_status = dict(
            s.execute(select(Assessment.status, func.count()).group_by(Assessment.status)).all()
        )

        reports_published = (
            s.scalar(
                select(func.count()).select_from(ReportRow).where(ReportRow.status == "published")
            )
            or 0
        )

        rec_total = s.scalar(select(func.count()).select_from(RecommendationRow)) or 0
        by_source = dict(
            s.execute(
                select(RecommendationRow.source, func.count()).group_by(RecommendationRow.source)
            ).all()
        )
        grounded = (
            s.scalar(
                select(func.count())
                .select_from(RecommendationRow)
                .where(RecommendationRow.grounding_passed.is_(True))
            )
            or 0
        )
        llm_attempted = (
            s.scalar(
                select(func.count())
                .select_from(RecommendationRow)
                .where(RecommendationRow.grounding_passed.isnot(None))
            )
            or 0
        )

        latest: EvaluationRunRow | None = s.execute(
            select(EvaluationRunRow).order_by(EvaluationRunRow.created_at.desc()).limit(1)
        ).scalar_one_or_none()

        return AdminMetrics(
            organizations=orgs,
            assessments_total=assessments_total,
            assessments_by_status={str(k): int(v) for k, v in by_status.items()},
            reports_published=reports_published,
            ai_usage={
                "recommendations_total": rec_total,
                "by_source": {str(k): int(v) for k, v in by_source.items()},
                "grounding_pass_rate": round(grounded / llm_attempted, 4)
                if llm_attempted
                else None,
            },
            evaluation={
                "latest_accuracy": latest.accuracy if latest else None,
                "latest_hallucination_rate": latest.hallucination_rate if latest else None,
                "latest_status": latest.status if latest else None,
            },
        )
