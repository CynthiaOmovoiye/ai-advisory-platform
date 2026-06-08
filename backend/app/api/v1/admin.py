"""Admin dashboard route (Module 10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_metrics_repository, require
from app.domain.access import Permission
from app.schemas.admin import AdminMetricsOut
from app.services.metrics_service import SqlMetricsRepository

router = APIRouter(tags=["Admin"])


@router.get("/admin/metrics", response_model=AdminMetricsOut)
def admin_metrics(
    _scope=Depends(require(Permission.ADMIN_METRICS)),  # admin-only (default-deny)
    metrics: SqlMetricsRepository = Depends(get_metrics_repository),
) -> AdminMetricsOut:
    return AdminMetricsOut.from_domain(metrics.collect())
