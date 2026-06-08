# Security Review

**Status:** Design baseline (Phase 12, applied from Phase 1 onward)
**Scope:** The AI Advisory Platform as designed in this repository.

Security is treated as a feature and designed in from the start, not reviewed at the
end. This document is the control inventory; attack analysis is in the
[threat model](threat-model.md). Where a control maps to a decision, the ADR is
linked.

## Security principles

1. **Default deny.** No access without an explicit grant (ADR-0007).
2. **Derive trust from the server, never the client.** Tenant id, identity, and roles
   come from the authenticated session, never request input (ADR-0006).
3. **Defense in depth.** The worst failure (cross-tenant leak) is defended at two
   independent layers (repository scoping *and* Postgres RLS).
4. **Fail closed and quiet.** Errors deny access and never leak internals.
5. **Least privilege** for users, services, and database roles.
6. **Auditable.** Security-relevant actions are append-only logged.

---

## 1. Authentication

Managed library (Auth.js / Better Auth), not hand-rolled (ADR-0007).

| Control | Design |
|---|---|
| Sessions | Secure, httpOnly, SameSite cookies; short-lived access + rotating refresh. |
| Refresh-token rotation | Each refresh issues a new token and invalidates the prior; reuse of a rotated token revokes the session family (theft detection). |
| Session invalidation | Server-side session revocation on logout, password reset, and role change. |
| Password reset | Single-use, time-boxed, hashed reset tokens; reset invalidates existing sessions. |
| Email verification | Required before privileged actions; verification token hashed and time-boxed. |
| Credential storage | Owned by the auth library (strong adaptive hashing); the app stores no raw passwords. |

---

## 2. Authorization (RBAC)

Default-deny RBAC in the application (ADR-0007), composed with tenant isolation
(ADR-0006).

- Roles: `admin`, `consultant`, `org_user`. Permissions table allows finer grants.
- **Every endpoint declares required role + tenant scope** via an injected guard. An
  undeclared route is forbidden by default; a CI test fails the build if any
  registered route lacks a guard.
- Authorization (role) and isolation (tenant) are **separate, both-must-pass** checks.
- Object-level checks: a consultant editing a finding is verified against that
  finding's assessment/org, not just their global role.

---

## 3. Multi-tenant isolation

The highest-severity control. See [ADR-0006](../adr/0006-multi-tenancy-isolation.md).

- `organization_id` on every tenant-owned table; tenant context derived from the
  principal.
- Repository-layer scoping applied centrally (devs don't hand-write tenant filters).
- **PostgreSQL Row-Level Security** as an independent backstop.
- Mandatory test suite: for every tenant-owned resource, assert tenant A cannot read,
  list, mutate, or enumerate tenant B's data through any endpoint.

---

## 4. API security

| Control | Design |
|---|---|
| Input validation | Zod at the client (UX), **Pydantic v2 at the server (authority)**. Reject-by-default schemas. |
| Request size limits | Max body size enforced at the gateway and in the app; large/streaming inputs bounded. |
| Rate limiting | Redis-backed, per-principal and per-IP; stricter limits on auth and LLM-triggering endpoints. |
| Secure headers | HSTS, `X-Content-Type-Options`, `X-Frame-Options`/frame-ancestors, a strict CSP on the web app, `Referrer-Policy`. |
| Error sanitization | Global handler returns a generic message + correlation id. **Stack traces and internals are never exposed.** Detail goes to logs only. |
| Audit logging | Security-relevant actions → append-only `audit_logs` (actor, action, entity, ip, time). |
| CORS | Explicit allowlist; credentials only for trusted origins. |
| Idempotency | State-changing, cost-bearing operations (assessment completion, report/LLM jobs) are idempotency-keyed. |

---

## 5. File upload security

PDF and DOCX only. See threat model (malicious upload).

- **Validate extension *and* sniffed MIME type** server-side; reject on mismatch.
  Never trust the client-supplied content type.
- **Size limits** enforced before and during streaming to storage.
- Stored in object storage (MinIO/S3) under opaque keys, **outside any public path**;
  served only via short-lived pre-signed URLs after authorization.
- **Malware-scan integration point**: a document is `scan_status = pending` on upload
  and is **never servable or processed until `clean`**. The scanner (e.g. ClamAV/
  vendor) is a designed seam in the worker pipeline.
- Filenames are sanitized; content is never rendered inline in a trusted context.

---

## 6. Data protection

- **Encryption in transit:** TLS everywhere (web↔api, api↔db where applicable,
  api↔object-store, api↔OpenRouter).
- **Encryption at rest:** database and object-store volume encryption; **sensitive
  application fields encrypted at the column level** (app-layer/KMS) beyond
  volume encryption.
- **PII minimization:** we collect the minimum (email, display name). Assessment
  content is the sensitive asset and is tenant-scoped and access-controlled.
- **Soft deletes** (`deleted_at`) where audit/recovery matters; hard-delete paths for
  true data-subject erasure requests are explicit and audited.
- **Audit logs are append-only** (no UPDATE/DELETE grants to app roles).

---

## 7. LLM-specific security

The LLM is an untrusted, external dependency processing tenant data. See threat
model (prompt injection, data exfiltration).

- **Single egress** through the OpenRouter client (ADR-0004) — one path to allowlist,
  rate-limit, budget, and monitor.
- **Structurally bounded blast radius:** the LLM cannot change findings or take
  actions; it writes narrative fields that pass a grounding check (ADR-0003/0005).
  Prompt injection in assessment text therefore cannot cause a wrong *recommendation*
  — at worst it degrades prose, which the grounding check and human review catch.
- **No secrets or cross-tenant data in prompts:** prompt construction includes only
  the current assessment's findings; inputs are redacted in logs.
- **Output is schema-constrained** and treated as untrusted data (never `eval`'d,
  never rendered as trusted HTML — see report XSS note in the threat model).
- **Cost guardrails:** per-org budgets and rate limits; runaway usage is capped and
  alertable via `llm_calls` telemetry.

---

## 8. Secrets & configuration

- Secrets (`OPENROUTER_API_KEY`, DB creds, session secret, storage keys) come from
  the environment / a secrets manager, never committed. `.env.example` documents the
  surface with no real values.
- Least-privilege DB roles: the application role has no DDL and no
  UPDATE/DELETE on `audit_logs`.
- Key rotation procedures documented in the deployment guide.

---

## 9. Supply chain & build

- Pinned dependencies; automated vulnerability scanning of Python and JS deps in CI.
- Static analysis: Ruff + MyPy (Python), type-checking and lint on the web app.
- Container images built from pinned bases, run as non-root, minimal surface.

---

## Open items / explicitly deferred

- WAF / bot management at the edge — deployment-environment concern, noted not built.
- Full DLP on LLM egress — current control is structural (grounding + no-secrets);
  content-inspection DLP is a future enhancement.
- Pen-test and external review — would precede any real production launch.
