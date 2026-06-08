"""Session verification — turning a request into an authenticated principal.

**Integration contract (ADR-0009).** Auth.js (Better Auth / NextAuth) owns the user
session in the Next.js app. The Next.js layer acts as a BFF: after it verifies its
Auth.js session, it mints a **short-lived, signed service token** (HS256 over the
shared ``AUTH_SECRET``) carrying the user's id, roles, and active organization, and
forwards it to this API. The API trusts *only* this token — it never reads identity,
roles, or tenant from arbitrary client input (ADR-0006/0007).

This module verifies that token's signature, issuer/audience, and expiry, and maps its
claims to a :class:`Principal` + active organization. Anything wrong ⇒ fail closed
(:class:`Unauthorized`).

Why a signed service token rather than decrypting the Auth.js JWE directly: it keeps
the API decoupled from Auth.js's internal token format, gives us a narrow, auditable
claim set, and lets the BFF enforce session freshness. The verification here is the
same regardless of which auth provider the BFF uses.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt

from app.domain.access import Principal, Role
from app.errors import Unauthorized

# Auth.js default cookie names, plus a bearer fallback for service-to-service calls.
_COOKIE_NAMES = (
    "__Secure-authjs.session-token",
    "authjs.session-token",
    "__Secure-next-auth.session-token",
    "next-auth.session-token",
    "session",
)


@dataclass(frozen=True)
class CallerContext:
    principal: Principal
    organization_id: str


def _roles(values: object) -> frozenset[Role]:
    """Map role strings to known Roles, ignoring anything unrecognised (fail safe —
    an unknown role grants nothing, ADR-0007)."""
    out: set[Role] = set()
    if isinstance(values, list):
        for v in values:
            try:
                out.add(Role(v))
            except ValueError:
                continue
    return frozenset(out)


def decode_session(token: str, *, secret: str, issuer: str, audience: str) -> CallerContext:
    if not secret:
        # Misconfiguration must not silently allow access.
        raise Unauthorized("auth not configured")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        # Expired, bad signature, wrong issuer/audience, missing claims — all fail closed.
        raise Unauthorized("invalid session") from exc

    user_id = claims.get("sub")
    active_org = claims.get("org")
    if not user_id or not active_org:
        raise Unauthorized("session missing subject or active organization")

    org_roles_raw = claims.get("org_roles") or {}
    org_roles = {org: _roles(roles) for org, roles in org_roles_raw.items()} if isinstance(org_roles_raw, dict) else {}

    principal = Principal(
        user_id=str(user_id),
        global_roles=_roles(claims.get("global_roles")),
        org_roles=org_roles,
    )
    return CallerContext(principal=principal, organization_id=str(active_org))


def extract_token(*, cookies: dict[str, str], authorization: str | None) -> str | None:
    for name in _COOKIE_NAMES:
        if name in cookies:
            return cookies[name]
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
