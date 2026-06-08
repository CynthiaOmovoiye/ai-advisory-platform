"""Application error taxonomy.

These map cleanly to sanitized HTTP responses at the API layer (see the `Error`
schema in docs/api/openapi.yaml) — the global handler turns them into a code + a
generic message + a correlation id, and **never** leaks internals
(docs/security/security-review.md §4).
"""

from __future__ import annotations


class AppError(Exception):
    """Base for expected, handled application errors."""

    code = "error"
    http_status = 400


class Unauthorized(AppError):
    """No valid authenticated principal. Raised by the auth dependency when a request
    arrives without a verified session (ADR-0007)."""

    code = "unauthorized"
    http_status = 401


class Forbidden(AppError):
    """Authorization denied. The default outcome — access must be explicitly granted
    (ADR-0007, default-deny). Deliberately generic: we do not reveal whether the
    resource exists, to avoid cross-tenant enumeration (threat-model: disclosure)."""

    code = "forbidden"
    http_status = 403


class NotFound(AppError):
    """Resource not found *within the caller's tenant scope*. A cross-tenant id
    resolves to NotFound, never to the other tenant's data (ADR-0006)."""

    code = "not_found"
    http_status = 404


class Conflict(AppError):
    code = "conflict"
    http_status = 409
