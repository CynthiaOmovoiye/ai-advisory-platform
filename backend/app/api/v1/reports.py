"""Report routes (Module 8).

POST validates the approval gate, persists a 'queued' report, and **enqueues** the
heavy Playwright render onto the Celery worker (returns 202). The worker flips the
report to 'published'. GET returns the current status + a short-lived pre-signed PDF
URL once rendered; the client polls until published.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CallerContext,
    get_caller,
    get_db,
    get_report_enqueuer,
    get_report_service,
    get_storage,
    require,
)
from app.domain.access import Permission
from app.errors import NotFound
from app.infra.storage import ObjectStorage
from app.reports.service import ReportService
from app.repositories.base import TenantScope
from app.repositories.sql import SqlReportRepository
from app.schemas.report import ReportOut

router = APIRouter(tags=["Reports"])


@router.post(
    "/assessments/{assessment_id}/report",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReportOut,
)
def request_report(
    assessment_id: str,
    _scope=Depends(require(Permission.REPORT_PUBLISH)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: ReportService = Depends(get_report_service),
    enqueue: Callable[..., None] = Depends(get_report_enqueuer),
) -> ReportOut:
    scope = TenantScope(caller.organization_id, caller.principal.user_id)
    # Validate + persist a queued row (immediate 404/409 on bad state), then enqueue.
    report = svc.queue(scope, assessment_id, organization_name=caller.organization_id)
    db.commit()
    enqueue(
        assessment_id=assessment_id,
        organization_id=caller.organization_id,
        organization_name=caller.organization_id,
        actor_user_id=caller.principal.user_id,
    )
    return ReportOut.from_domain(report, None)


@router.get("/assessments/{assessment_id}/report", response_model=ReportOut)
def get_report(
    assessment_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> ReportOut:
    scope = TenantScope(caller.organization_id, caller.principal.user_id)
    report = SqlReportRepository(db).get_for_assessment(assessment_id, scope)
    if report is None:
        raise NotFound("report not found")
    pdf_url = storage.presigned_url(report.pdf_storage_key) if report.pdf_storage_key else None
    return ReportOut.from_domain(report, pdf_url)
