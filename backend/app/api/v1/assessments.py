"""Assessment routes.

Routers do HTTP only (ADR-0002): authorize (via the injected guard), delegate to the
service, serialize to DTOs. No business logic, no SQL. Every route declares an
explicit authorization guard — default-deny (ADR-0007).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import (
    CallerContext,
    get_assessment_service,
    get_caller,
    get_db,
    get_template_service,
    require,
)
from app.domain.access import Permission
from app.schemas.recommendation import CompleteAssessmentResponse, RecommendationOut
from app.schemas.template import (
    AssessmentDetailOut,
    AssessmentOut,
    CreateAssessmentRequest,
    SaveResponsesRequest,
)
from app.services.assessment_service import AssessmentService
from app.services.template_service import TemplateService

router = APIRouter(tags=["Assessments"])


@router.get("/assessments", response_model=list[AssessmentOut])
def list_assessments(
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: AssessmentService = Depends(get_assessment_service),
) -> list[AssessmentOut]:
    items = svc.list_assessments(caller.principal, caller.organization_id)
    return [AssessmentOut.from_domain(a) for a in items]


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailOut)
def get_assessment(
    assessment_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: AssessmentService = Depends(get_assessment_service),
    templates: TemplateService = Depends(get_template_service),
) -> AssessmentDetailOut:
    a = svc.get_assessment(caller.principal, caller.organization_id, assessment_id)
    template = None
    if a.template_id:
        template = templates.get_template(caller.principal, caller.organization_id, a.template_id)
    return AssessmentDetailOut.from_domain(a, template)


@router.post("/assessments", status_code=status.HTTP_201_CREATED, response_model=AssessmentOut)
def create_assessment(
    body: CreateAssessmentRequest,
    _scope=Depends(require(Permission.ASSESSMENT_COMPLETE)),
    caller: CallerContext = Depends(get_caller),
    db: Session = Depends(get_db),
    svc: AssessmentService = Depends(get_assessment_service),
) -> AssessmentOut:
    """Start an assessment in the caller's org from a published template (Module 3)."""
    a = svc.create_from_template(caller.principal, caller.organization_id, body.template_id)
    db.commit()
    return AssessmentOut.from_domain(a)


@router.put("/assessments/{assessment_id}/responses", status_code=status.HTTP_204_NO_CONTENT)
def save_responses(
    assessment_id: str,
    body: SaveResponsesRequest,
    _scope=Depends(require(Permission.ASSESSMENT_COMPLETE)),
    caller: CallerContext = Depends(get_caller),
    db: Session = Depends(get_db),
    svc: AssessmentService = Depends(get_assessment_service),
) -> None:
    svc.save_responses(
        caller.principal,
        caller.organization_id,
        assessment_id,
        [r.model_dump() for r in body.responses],
    )
    db.commit()


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
