"""Evaluation routes (Module 6 → eval dashboard).

POST triggers an evaluation run against a curated dataset and persists its aggregate
scores; GET lists recent runs for regression tracking. Admin-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CallerContext,
    baseline_eval_dataset,
    get_caller,
    get_db,
    get_evaluation_service,
    get_settings,
    require,
)
from app.domain.access import Permission
from app.infra.config import Settings
from app.schemas.admin import EvaluationRunOut, TriggerEvaluationRequest
from app.services.evaluation_service import EvaluationService

router = APIRouter(tags=["Evaluation"])


@router.post("/evaluation/runs", status_code=status.HTTP_201_CREATED, response_model=EvaluationRunOut)
def trigger_run(
    body: TriggerEvaluationRequest,
    _scope=Depends(require(Permission.ADMIN_METRICS)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: EvaluationService = Depends(get_evaluation_service),
    settings: Settings = Depends(get_settings),
) -> EvaluationRunOut:
    run = svc.run(
        body.dataset_name or "baseline-readiness",
        list(baseline_eval_dataset()),
        model_id=settings.llm_default_model if settings.llm_enabled else "mock",
        triggered_by=caller.principal.user_id,
    )
    db.commit()
    return EvaluationRunOut.from_domain(run)


@router.get("/evaluation/runs", response_model=list[EvaluationRunOut])
def list_runs(
    _scope=Depends(require(Permission.ADMIN_METRICS)),
    svc: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationRunOut]:
    return [EvaluationRunOut.from_domain(r) for r in svc.list_recent()]
