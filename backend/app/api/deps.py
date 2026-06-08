"""API dependency injection (the wiring layer).

Everything the routers need is injected here (ADR-0002): the DB session, the
authenticated caller, the default-deny authorization guard, and the assembled
service. Nothing is reached for globally.

Two security-critical pieces live here:

  * :func:`get_caller` — resolves the authenticated principal **and** their active
    organization from the verified session. By default it **fails closed** (401): a
    request with no established caller is rejected, never treated as anonymous-allowed.
    In production this verifies the Auth.js/Better Auth session (ADR-0007); in tests
    it is overridden via FastAPI ``dependency_overrides``.
  * :func:`require` — the **default-deny guard** (ADR-0007). Every protected route
    declares ``Depends(require(Permission.X))``; the guard authorizes the caller in
    their org and yields the :class:`TenantScope`. A route with no guard is, by
    construction, unreachable as "authorized" — and a test asserts every route has one.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.domain.access import Permission, authorize
from app.domain.rules.models import Ruleset, ruleset_from_dict
from app.infra.auth import CallerContext, decode_session, extract_token
from app.infra.config import Settings, get_settings
from app.infra.db import make_engine, make_session_factory
from app.llm.mock import MockLLMProvider
from app.llm.openrouter import ModelPricing, OpenRouterConfig, OpenRouterProvider
from app.llm.provider import LLMProvider
from app.infra.storage import ObjectStorage, S3Storage
from app.repositories.base import TenantScope
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlEvaluationRunRepository,
    SqlRecommendationRepository,
    SqlReportRepository,
)
from app.reports.renderer import PlaywrightRenderer
from app.reports.service import ReportService
from app.services.assessment_service import AssessmentService
from app.services.evaluation_service import EvaluationService
from app.services.metrics_service import SqlMetricsRepository
from app.services.recommendation_service import RecommendationService

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parents[2] / "data"


# CallerContext is defined in app.infra.auth (the verifier produces it) and re-exported
# here for the routers/guards that depend on it.

# --------------------------------------------------------------------------- #
# Database session (one per request, with commit/rollback handled by the route).
# --------------------------------------------------------------------------- #
@lru_cache
def _session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    return make_session_factory(engine)


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Authentication — fails closed.
# --------------------------------------------------------------------------- #
def get_caller(request: Request) -> CallerContext:
    """Resolve the caller from the signed session token (ADR-0007/0009).

    Fails closed: no token, bad signature, wrong issuer/audience, or expiry ⇒ 401
    (raised inside :func:`decode_session`). Identity, roles, and tenant come only from
    the verified token — never from spoofable client input. Tests override this
    dependency to inject a principal directly.
    """
    settings = get_settings()
    token = extract_token(
        cookies=request.cookies, authorization=request.headers.get("authorization")
    )
    if not token:
        from app.errors import Unauthorized

        raise Unauthorized("no session")
    return decode_session(
        token,
        secret=settings.auth_secret,
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
    )


# --------------------------------------------------------------------------- #
# Authorization — default-deny guard.
# --------------------------------------------------------------------------- #
def require(permission: Permission) -> Callable[..., TenantScope]:
    def guard(caller: CallerContext = Depends(get_caller)) -> TenantScope:
        # Default deny: raises Forbidden unless the caller explicitly holds this
        # permission in their active org. Tenant scope falls out of the same check.
        authorize(caller.principal, permission, caller.organization_id)
        return TenantScope(
            organization_id=caller.organization_id, acting_user_id=caller.principal.user_id
        )

    return guard


# --------------------------------------------------------------------------- #
# Service assembly (DI) — picks the real or mock LLM provider from config.
# --------------------------------------------------------------------------- #
@lru_cache
def _baseline_ruleset() -> Ruleset:
    return ruleset_from_dict(json.loads((_DATA / "rulesets" / "baseline-v1.json").read_text()))


@lru_cache
def _baseline_eval_dataset() -> tuple:
    raw = json.loads((_DATA / "eval" / "baseline-readiness.json").read_text())
    return tuple(raw["items"])


def get_storage(settings: Settings = Depends(get_settings)) -> ObjectStorage:
    return S3Storage(
        endpoint=settings.storage_endpoint,
        bucket=settings.storage_bucket,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        region=settings.storage_region,
    )


def _llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_enabled:
        return OpenRouterProvider(
            OpenRouterConfig(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                timeout_seconds=settings.llm_request_timeout_seconds,
                max_retries=settings.llm_max_retries,
            ),
            ModelPricing(model_id=settings.llm_default_model),
        )
    # No API key configured ⇒ deterministic mock, so the system still runs end-to-end
    # (an LLM outage / absence degrades polish, not function — ADR-0003).
    return MockLLMProvider()


def get_assessment_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AssessmentService:
    return AssessmentService(
        assessments=SqlAssessmentRepository(db),
        recommendations=SqlRecommendationRepository(db),
        audit=SqlAuditSink(db),
        ruleset=_baseline_ruleset(),
        llm=_llm_provider(settings),
    )


def get_recommendation_service(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(
        recommendations=SqlRecommendationRepository(db),
        audit=SqlAuditSink(db),
    )


def get_report_service(
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> ReportService:
    return ReportService(
        assessments=SqlAssessmentRepository(db),
        recommendations=SqlRecommendationRepository(db),
        reports=SqlReportRepository(db),
        audit=SqlAuditSink(db),
        storage=storage,
        renderer=PlaywrightRenderer(),  # heavy render; overridden in tests
    )


def get_evaluation_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EvaluationService:
    return EvaluationService(
        runs=SqlEvaluationRunRepository(db),
        ruleset=_baseline_ruleset(),
        llm=_llm_provider(settings),
    )


def get_metrics_repository(db: Session = Depends(get_db)) -> SqlMetricsRepository:
    return SqlMetricsRepository(db)


def baseline_eval_dataset() -> tuple:
    return _baseline_eval_dataset()
