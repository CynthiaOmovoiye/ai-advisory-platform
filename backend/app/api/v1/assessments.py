"""Assessment routes.

Routers do HTTP only (ADR-0002): authorize (via the injected guard), delegate to the
service, serialize to DTOs. No business logic, no SQL. Every route declares an
explicit authorization guard — default-deny (ADR-0007).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import CallerContext, get_assessment_service, get_caller, get_db, require
from app.domain.access import Permission
from app.schemas.recommendation import CompleteAssessmentResponse, RecommendationOut
from app.services.assessment_service import AssessmentService

router = APIRouter(tags=["Assessments"])


@router.post(
    "/assessments/{assessment_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CompleteAssessmentResponse,
)
def complete_assessment(
    assessment_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_COMPLETE)),  # default-deny guard
    caller: CallerContext = Depends(get_caller),
    db: Session = Depends(get_db),
    svc: AssessmentService = Depends(get_assessment_service),
) -> CompleteAssessmentResponse:
    recommendations = svc.complete(caller.principal, caller.organization_id, assessment_id)
    db.commit()  # transaction boundary: persist the service's work
    return CompleteAssessmentResponse(
        assessment_id=assessment_id,
        status="completed",
        recommendations=[RecommendationOut.from_domain(r) for r in recommendations],
    )


@router.get(
    "/assessments/{assessment_id}/recommendations",
    response_model=list[RecommendationOut],
)
def list_recommendations(
    assessment_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: AssessmentService = Depends(get_assessment_service),
) -> list[RecommendationOut]:
    recs = svc.list_recommendations(caller.principal, caller.organization_id, assessment_id)
    return [RecommendationOut.from_domain(r) for r in recs]
