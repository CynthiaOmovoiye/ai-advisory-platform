# ADR-0007: Use a managed auth library; RBAC with default-deny in the application

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

The system needs authentication (sessions, refresh-token rotation, session
invalidation, password reset, email verification) and authorization (RBAC across
Admin / Consultant / Org User). Authentication is a domain where rolling your own is
a well-known way to ship vulnerabilities. The brief is explicit: *do not build
authentication from scratch.*

## Decision

**Authentication: adopt a managed library** — Auth.js (NextAuth) on the Next.js side
and/or Better Auth — rather than hand-rolling. It provides the session and
credential machinery (secure sessions, refresh-token rotation, session
invalidation, password reset, email verification) that we treat as a solved problem.

**Authorization: implement RBAC ourselves in the application, default-deny.**

- Authorization is *business logic* and stays in our control, in the service/API
  layers — we don't outsource "who may publish a report."
- **Default deny:** every endpoint explicitly declares the role(s) and tenant scope
  it requires, via an injected guard dependency (ADR-0002). An endpoint with no
  declared authorization is treated as forbidden, not open — the absence of a rule is
  a denial, enforced by a global default and caught in tests.
- Roles: `admin` (system + cross-tenant ops), `consultant` (cross-tenant review &
  publish), `org_user` (single-tenant, their org only). The `permissions` /
  `role_permissions` tables let us grow beyond three roles without reshaping the
  model.
- Authorization composes with tenant isolation (ADR-0006): a guard checks *role*;
  the repository layer + RLS enforce *tenant scope*. Both must pass.

## Alternatives considered

- **Hand-rolled auth.** Explicitly rejected by the brief and by good sense.
- **Fully outsourced authz (e.g. external policy engine / OPA).** Powerful, but
  premature for three roles; adds an external dependency on the hot path for every
  request. We keep authz in-process and simple, revisitable if policy complexity
  grows. Violates "avoid premature abstraction" otherwise.

## Consequences

- **+** The dangerous, easy-to-botch part (credentials, sessions, tokens) is handled
  by audited, maintained code.
- **+** Authorization — which is product-specific — stays explicit, testable, and
  in-repo.
- **+** Default-deny means new endpoints are safe by omission; you must opt *in* to
  access.
- **−** Integrating the auth library with the FastAPI backend's session/principal
  model requires care at the boundary (token verification, mapping to `users`). This
  seam is documented and tested.
- A standing test asserts that **every** registered route declares an authorization
  guard — an unguarded route fails CI.
