"""Report routes (Module 8).

POST generates & publishes a report (consultant/admin) — it enforces the approval gate
(all recommendations reviewed) in the service. GET returns the report metadata plus a
short-lived pre-signed PDF URL.

In production the POST enqueues the heavy Playwright render onto the Celery worker; the
synchronous path here keeps the surface testable. Either way the same ReportService is
the orchestrator.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CallerContext,
    get_caller,
    get_db,
    get_report_service,
    get_storage,
    require,
)
from app.domain.access import Permission
from app.errors import NotFound
from app.infra.storage import ObjectStorage
from app.repositories.base import TenantScope
from app.repositories.sql import SqlReportRepository
from app.schemas.report import ReportOut
from app.reports.service import ReportService

router = APIRouter(tags=["Reports"])


@router.post(
    "/assessments/{assessment_id}/report",
    status_code=status.HTTP_201_CREATED,
    response_model=ReportOut,
)
def generate_report(
    assessment_id: str,
    _scope=Depends(require(Permission.REPORT_PUBLISH)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: ReportService = Depends(get_report_service),
    storage: ObjectStorage = Depends(get_storage),
) -> ReportOut:
    scope = TenantScope(caller.organization_id, caller.principal.user_id)
    report = svc.generate(scope, assessment_id, organization_name=caller.organization_id)
    db.commit()
    pdf_url = storage.presigned_url(report.pdf_storage_key) if report.pdf_storage_key else None
    return ReportOut.from_domain(report, pdf_url)


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
