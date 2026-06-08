"""FastAPI application factory.

Wires the routers, the **sanitized** error handling (never leak a stack trace —
security-review §4), secure response headers, and a per-request correlation id that
ties a client-visible error back to the server logs.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_storage
from app.api.health import check_readiness
from app.api.middleware import build_rate_limiter
from app.api.v1 import (
    admin,
    assessments,
    documents,
    evaluation,
    organizations,
    recommendations,
    reports,
    templates,
)
from app.errors import AppError
from app.infra.config import Settings, get_settings
from app.infra.storage import ObjectStorage

SECURE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def _error_body(code: str, message: str, correlation_id: str) -> dict:
    return {"code": code, "message": message, "correlationId": correlation_id}


def _sanitized(status: int, code: str, message: str, request: Request) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", "n/a")
    return JSONResponse(
        status_code=status,
        content=_error_body(code, message, cid),
        headers={"X-Correlation-Id": cid, **SECURE_HEADERS},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Advisory Platform API", version="0.1.0")
    rate_limiter = build_rate_limiter(settings)  # one per app instance (test-isolated)

    # CORS: explicit allowlist from config; credentials only for trusted origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def context_and_headers(request: Request, call_next):
        request.state.correlation_id = str(uuid.uuid4())

        # Request-size limit (JSON bodies). Multipart uploads are exempt — the upload
        # route enforces its own (larger) cap before storing.
        content_type = request.headers.get("content-type", "")
        content_length = request.headers.get("content-length")
        if (
            request.method in ("POST", "PUT", "PATCH")
            and not content_type.startswith("multipart/")
            and content_length
            and content_length.isdigit()
            and int(content_length) > settings.max_request_bytes
        ):
            return _sanitized(413, "payload_too_large", "Request body too large.", request)

        # Rate limit per client IP (liveness/readiness probes exempt).
        if not request.url.path.startswith(("/healthz", "/readyz")):
            client_ip = request.client.host if request.client else "unknown"
            if not rate_limiter.allow(client_ip):
                return _sanitized(429, "rate_limited", "Too many requests.", request)

        response = await call_next(request)
        for k, v in SECURE_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers["X-Correlation-Id"] = request.state.correlation_id
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        cid = getattr(request.state, "correlation_id", "n/a")
        # Expected, already-sanitized errors: surface code + the (safe) message.
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, str(exc) or exc.code, cid),
            headers={"X-Correlation-Id": cid},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        cid = getattr(request.state, "correlation_id", "n/a")
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", "Request validation failed.", cid),
            headers={"X-Correlation-Id": cid},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        cid = getattr(request.state, "correlation_id", "n/a")
        # Unexpected error: log detail server-side (cid), return a GENERIC message.
        # The stack trace / internals never reach the client.
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "An unexpected error occurred.", cid),
            headers={"X-Correlation-Id": cid},
        )

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(
        db: Session = Depends(get_db),
        storage: ObjectStorage = Depends(get_storage),
        cfg: Settings = Depends(get_settings),
    ) -> JSONResponse:
        ready, checks = check_readiness(db, storage, cfg)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": checks},
        )

    app.include_router(assessments.router, prefix="/v1")
    app.include_router(organizations.router, prefix="/v1")
    app.include_router(recommendations.router, prefix="/v1")
    app.include_router(reports.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(evaluation.router, prefix="/v1")
    app.include_router(templates.router, prefix="/v1")
    app.include_router(documents.router, prefix="/v1")
    return app


app = create_app()
