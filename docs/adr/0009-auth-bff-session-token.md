# ADR-0009: Next.js as a BFF that mints a signed service token the API verifies

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering
- **Relates to:** [ADR-0007](0007-auth-choice.md) (managed auth + RBAC)

## Context

[ADR-0007](0007-auth-choice.md) chose a managed auth library (Auth.js / Better Auth)
for sessions/credentials, with RBAC kept in our application. That leaves one concrete
question: **how does the FastAPI backend learn who the caller is?** Auth.js owns the
session in the Next.js app, and its session token is an *encrypted* JWE in a cookie,
in a format internal to Auth.js. We need the backend to authenticate requests without
(a) re-implementing Auth.js's token format, (b) trusting spoofable client input, or
(c) coupling the API to one specific auth vendor.

## Decision

**The Next.js app acts as a Backend-for-Frontend (BFF).** It verifies its own Auth.js
session, and then mints a **short-lived, signed service token** (HS256 over the shared
``AUTH_SECRET``) carrying a *narrow, explicit* claim set, which it forwards to the API.
The API trusts **only** this token.

Token claims (verified in `app/infra/auth.py`):

```
{ "sub": <user id>, "org": <active organization id>,
  "global_roles": [...], "org_roles": { "<org>": [...] },
  "iss": "advisory-bff", "aud": "advisory-api", "exp": <short> }
```

The API's `get_caller` dependency:

1. extracts the token from the Auth.js cookie (or a bearer header for service calls);
2. verifies **signature, issuer, audience, and expiry** — any failure ⇒ 401 (fails
   closed);
3. maps claims to a `Principal` + active organization, ignoring unrecognised roles
   (an unknown role grants nothing).

Identity, roles, and tenant therefore come **only** from a signed token the BFF
produced — never from raw request input (upholds [ADR-0006](0006-multi-tenancy-isolation.md)/[ADR-0007](0007-auth-choice.md)).

## Alternatives considered

- **Decrypt the Auth.js JWE directly in Python.** Couples the backend to Auth.js's
  internal token format (HKDF + A256GCM), which can change between versions, and pulls
  the full session blob into the API. Rejected for fragility and coupling.
- **Shared session database lookup** (Auth.js database-session strategy; API reads the
  session table). Workable, but puts an auth read on every API request's hot path and
  couples the API schema to the auth library's. Rejected as premature.
- **Trust headers set by the Next.js proxy** (`X-User-Id`, `X-Roles`). Spoofable if
  anything can reach the API directly; "trust the proxy" is a classic isolation hole.
  Rejected — we sign and verify instead.

## Consequences

- **+** API authentication is provider-agnostic: swapping Auth.js for Better Auth or
  another IdP changes only the BFF, not the API's verification.
- **+** Narrow, auditable claim set; short expiry limits replay; freshness is enforced
  by the BFF re-checking the real session.
- **+** Verification is pure and fully unit-testable (mint a token, assert the
  outcome) — no auth server needed in tests.
- **−** Two secrets/relationships to manage (the Auth.js session **and** the shared
  signing secret). Mitigated: `AUTH_SECRET` rotation is documented (deployment guide),
  and an empty secret fails closed.
- **−** Roles are snapshotted into the token, so a revocation isn't instant — bounded
  by the short token lifetime. Acceptable; sensitive actions are re-authorized
  server-side and audited.
