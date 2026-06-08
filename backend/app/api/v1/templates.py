"""Assessment-template authoring routes (Module 3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CallerContext, get_caller, get_db, get_template_service, require
from app.domain.access import Permission
from app.schemas.template import CreateTemplateRequest, TemplateOut
from app.services.template_service import TemplateService

router = APIRouter(tags=["Templates"])


@router.post("/templates", status_code=status.HTTP_201_CREATED, response_model=TemplateOut)
def create_template(
    body: CreateTemplateRequest,
    _scope=Depends(require(Permission.TEMPLATE_MANAGE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: TemplateService = Depends(get_template_service),
) -> TemplateOut:
    t = svc.create_template(
        caller.principal,
        caller.organization_id,
        category=body.category,
        title=body.title,
        description=body.description,
        sections=[s.model_dump() for s in body.sections],
    )
    db.commit()
    return TemplateOut.from_domain(t)


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: TemplateService = Depends(get_template_service),
) -> list[TemplateOut]:
    return [
        TemplateOut.from_domain(t)
        for t in svc.list_templates(caller.principal, caller.organization_id)
    ]


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: TemplateService = Depends(get_template_service),
) -> TemplateOut:
    return TemplateOut.from_domain(
        svc.get_template(caller.principal, caller.organization_id, template_id)
    )


@router.post("/templates/{template_id}/publish", response_model=TemplateOut)
def publish_template(
    template_id: str,
    _scope=Depends(require(Permission.TEMPLATE_MANAGE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: TemplateService = Depends(get_template_service),
) -> TemplateOut:
    t = svc.publish_template(caller.principal, caller.organization_id, template_id)
    db.commit()
    return TemplateOut.from_domain(t)
