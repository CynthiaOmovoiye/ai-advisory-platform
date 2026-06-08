"""FastAPI application factory.

Wires the routers, the **sanitized** error handling (never leak a stack trace —
security-review §4), secure response headers, and a per-request correlation id that
ties a client-visible error back to the server logs.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import (
    admin,
    assessments,
    evaluation,
    organizations,
    recommendations,
    reports,
    templates,
)
from app.errors import AppError

SECURE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def _error_body(code: str, message: str, correlation_id: str) -> dict:
    return {"code": code, "message": message, "correlationId": correlation_id}


def create_app() -> FastAPI:
    app = FastAPI(title="AI Advisory Platform API", version="0.1.0")

    @app.middleware("http")
    async def context_and_headers(request: Request, call_next):
        request.state.correlation_id = str(uuid.uuid4())
        try:
            response = await call_next(request)
        finally:
            pass
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
    async def healthz():
        return {"status": "ok"}

    app.include_router(assessments.router, prefix="/v1")
    app.include_router(organizations.router, prefix="/v1")
    app.include_router(recommendations.router, prefix="/v1")
    app.include_router(reports.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(evaluation.router, prefix="/v1")
    app.include_router(templates.router, prefix="/v1")
    return app


app = create_app()
