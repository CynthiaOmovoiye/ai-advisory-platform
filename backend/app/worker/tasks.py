"""Celery tasks.

Tasks are thin wrappers: they open a DB session, assemble the service from real
infra (Playwright renderer, S3 storage), and delegate. The orchestration logic lives
in the service (tested independently with in-memory repos + a fake renderer), so the
task itself stays trivial.
"""

from __future__ import annotations

from app.infra.celery_app import celery_app
from app.infra.config import get_settings
from app.infra.db import make_engine, make_session_factory, session_scope
from app.infra.storage import S3Storage
from app.reports.renderer import PlaywrightRenderer
from app.reports.service import ReportService
from app.repositories.base import TenantScope
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlDocumentRepository,
    SqlRecommendationRepository,
    SqlReportRepository,
)
from app.services.document_service import DocumentService

_engine = None
_session_factory = None


def _factory():
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        _engine = make_engine(settings.database_url)
        _session_factory = make_session_factory(_engine)
    return _session_factory


@celery_app.task(
    name="reports.generate",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def generate_report(
    self, *, assessment_id: str, organization_id: str, organization_name: str, actor_user_id: str
) -> dict:  # pragma: no cover - requires Redis + browser
    """Render and publish a report for a completed assessment.

    Idempotent at the storage/report-row level (keyed by assessment), so a retry after
    a crash re-renders to the same key rather than duplicating (architecture §9).
    """
    settings = get_settings()
    scope = TenantScope(organization_id=organization_id, acting_user_id=actor_user_id)
    with session_scope(_factory()) as session:
        service = ReportService(
            assessments=SqlAssessmentRepository(session),
            recommendations=SqlRecommendationRepository(session),
            reports=SqlReportRepository(session),
            audit=SqlAuditSink(session),
            storage=S3Storage(
                endpoint=settings.storage_endpoint,
                bucket=settings.storage_bucket,
                access_key=settings.storage_access_key,
                secret_key=settings.storage_secret_key,
                region=settings.storage_region,
            ),
            renderer=PlaywrightRenderer(),
        )
        report = service.generate(scope, assessment_id, organization_name=organization_name)
        return {"report_id": report.id, "status": report.status, "pdf_key": report.pdf_storage_key}


@celery_app.task(name="documents.scan", bind=True, max_retries=3, default_retry_delay=10)
def scan_document(
    self, *, document_id: str, organization_id: str, actor_user_id: str
) -> dict:  # pragma: no cover - requires Redis + storage
    """Malware-scan a freshly uploaded document, off the request path. Until this runs
    and marks the document 'clean', it cannot be downloaded (the gate)."""
    settings = get_settings()
    with session_scope(_factory()) as session:
        service = DocumentService(
            documents=SqlDocumentRepository(session),
            assessments=SqlAssessmentRepository(session),
            storage=S3Storage(
                endpoint=settings.storage_endpoint,
                bucket=settings.storage_bucket,
                access_key=settings.storage_access_key,
                secret_key=settings.storage_secret_key,
                region=settings.storage_region,
            ),
            audit=SqlAuditSink(session),
        )
        doc = service.scan(organization_id, document_id, actor_user_id)
        return {"document_id": doc.id, "scan_status": doc.scan_status}
