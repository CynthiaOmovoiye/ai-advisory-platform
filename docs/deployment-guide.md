# Deployment Guide

**Status:** Design baseline
**Audience:** Whoever runs this — locally, in staging, or in production.

This describes the target operational shape. The local path works against the
Compose topology; the production path is the intended design.

---

## 1. Prerequisites

- Docker + Docker Compose
- An `OPENROUTER_API_KEY` (for LLM enhancement; the system runs without it but reports
  fall back to deterministic narratives — see [ADR-0003](adr/0003-rule-engine-then-llm.md))
- SMTP credentials for production email verification and password reset delivery

## 2. Local

```bash
cp .env.example .env
# Fill in: secrets (AUTH_SECRET, FIELD_ENCRYPTION_KEY), OPENROUTER_API_KEY if used
docker compose up -d
```

The `api` container entrypoint runs **Alembic migrations** and then an **idempotent
seed**: a real local account (`demo@example.com` / `ChangeMe123!`), `Demo
Organization`, an org-scoped `consultant` membership, and an assessment with
responses. When healthy:

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API + OpenAPI docs | http://localhost:8000/v1 , http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |

Verify:

```bash
curl -fsS http://localhost:8000/healthz        # liveness
curl -fsS http://localhost:8000/readyz         # readiness (db, redis, storage)
docker compose logs -f api worker
```

## 3. Configuration

All configuration is environment-driven (12-factor); see
[`.env.example`](../.env.example) for the full surface. Secrets come from the
environment or a secrets manager — never committed. Key groups: database, redis,
object storage, auth, field-encryption key, OpenRouter + cost guardrails, API
security limits.

Auth is real credential verification in all environments. Email (verification +
password reset) is delivered by a pluggable provider set via `EMAIL_PROVIDER`:

- `console` — logs the message (the verification/reset link appears in the API logs);
  the dev default, no credentials required.
- `smtp` — any SMTP server. **Mailtrap** works directly: set `SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` from your Mailtrap inbox's SMTP tab.
- `resend` — the Resend HTTP API: set `RESEND_API_KEY` and a verified `EMAIL_FROM`.

`APP_BASE_URL` must be the public web URL so emailed links resolve. Local dev can also
return the verification token from signup (`LOCAL_EMAIL_VERIFICATION_TOKENS=true`) for a
no-SMTP loop; production should set that false and rely on the email provider. A
provider selected without its credentials degrades to `console` rather than blocking
signup.

## 4. Migrations & seed

- **Migrations:** Alembic, run on deploy before the app serves traffic. Forward-only;
  destructive changes are two-phase (expand → migrate → contract).
- **Seed:** idempotent; safe to re-run. Seeds reference data only (roles, permissions,
  templates, starter ruleset, prompt/model versions), never tenant data.
- `db/schema.sql` is the readable canonical schema and must stay in sync with the ORM models (CI applies migrations on a fresh DB and asserts every ORM table exists — see scripts/check_migrations.py).

## 5. Production topology (intended)

```
            ┌── CDN/edge (TLS, WAF/bot mgmt — env concern) ──┐
 Internet ─►│  web (Next.js, N replicas, stateless)          │
            │  api (FastAPI, N replicas, stateless)          │
            └──────────────┬────────────────────────────────┘
                           │
        ┌──────────────────┼─────────────────────┐
   managed Postgres   managed Redis        object store (S3)
   (pgvector, RLS,    (cache + broker)     (private bucket)
    PITR backups)
                           │
                     worker (Celery, M replicas) ──► OpenRouter
```

- **API and workers scale horizontally and are stateless.** Scale workers on queue
  depth (LLM/PDF load), API on request load — independently (see architecture §9).
- **Postgres** managed, with PITR backups, RLS enabled, and a least-privilege app role
  (no DDL; no UPDATE/DELETE on `audit_logs`).
- **Object storage** is a private bucket; documents/PDFs served only via short-lived
  pre-signed URLs after authorization.
- **Secrets** via the platform secrets manager; rotation procedure below.

## 6. Health, observability, alerting

- `GET /healthz` (liveness), `GET /readyz` (dependencies).
- Metrics exported for: request latency/error rate, **LLM latency/tokens/cost**,
  queue depth, evaluation scores (architecture §7).
- Dashboards: usage, **cost by org/model/time**, reliability. The admin dashboard
  surfaces the product-facing slice (`GET /v1/admin/metrics`).
- Alert on: error-rate spikes, LLM cost anomalies (denial-of-wallet), queue backlog,
  eval regression (hallucination-rate increase), readiness failures.

## 7. Backups & DR

- Postgres: automated backups + PITR; periodic restore drills.
- Object storage: versioning + lifecycle policy.
- Audit logs are append-only and included in backups.
- RPO/RTO targets set per environment; documented in the runbook.

## 8. Zero-downtime deploys

1. Apply expand-phase migrations (additive, backward compatible).
2. Roll out new api/worker replicas; health-gate.
3. Apply contract-phase migrations once old replicas are drained.
4. Roll back = redeploy previous image; never run destructive migrations in the
   forward step.

## 9. Secret rotation

- `OPENROUTER_API_KEY`, DB creds, `AUTH_SECRET`, `FIELD_ENCRYPTION_KEY`, storage keys.
- Rotate via the secrets manager; `AUTH_SECRET` rotation supports an overlap window so
  existing sessions aren't all invalidated at once. `FIELD_ENCRYPTION_KEY` rotation
  uses key-versioning (decrypt-old/encrypt-new) — never a hard cutover.

## 10. Pre-production checklist

- [ ] RLS policies enabled and tested (cross-tenant test suite green).
- [ ] Every route has an authorization guard (CI check green).
- [ ] `LOCAL_EMAIL_VERIFICATION_TOKENS=false`; SMTP-backed verification/reset delivery configured.
- [ ] Rate limits, body/upload size limits, secure headers, CSP set.
- [ ] Malware-scan integration wired (documents gate on `scan_status = clean`).
- [ ] LLM cost guardrails + alerts configured.
- [ ] Backups + a successful restore drill.
- [ ] Error responses sanitized (no stack traces) in production mode.
