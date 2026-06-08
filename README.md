# AI Advisory Platform

[![CI](https://github.com/CynthiaOmovoiye/ai-advisory-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/CynthiaOmovoiye/ai-advisory-platform/actions/workflows/ci.yml)

> A platform that assesses an organization's readiness for AI adoption and produces
> architecture, security, governance, and risk recommendations — combining a
> **deterministic rule engine** with **LLM-assisted reasoning**, wrapped in
> production-grade evaluation, observability, security, and governance.

This repository is a **design-first portfolio project that is now fully implemented**.
It was built the way a real system is: design and decisions first (the `docs/` package),
then a working full-stack application against that design. Both halves ship together —
the ADRs/threat-model explain *why*, and the code (140 backend tests, CI green, a
runnable `docker compose` stack) is the *what*.

If you only read three files, read these:

1. [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) — how the system is shaped and why.
2. [`docs/portfolio-story.md`](docs/portfolio-story.md) — the reasoning behind every major decision.
3. [`docs/security/threat-model.md`](docs/security/threat-model.md) — how it can be attacked and how that's mitigated.

---

## The core thesis

Most "AI products" put an LLM in the critical path and hope. This one does the opposite.

```
Structured assessment data
        │
        ▼
  ┌───────────────┐     deterministic, auditable, testable
  │  RULE ENGINE  │ ──► findings + recommendations (the source of truth)
  └───────────────┘
        │
        ▼
  ┌───────────────┐     LLM *explains* and *narrates* findings —
  │ LLM ENHANCEMENT│ ──► it never invents them
  └───────────────┘
        │
        ▼
   Reviewed report (consultant-in-the-loop) ──► PDF
```

The LLM is a **presentation and reasoning layer over a deterministic core**, not the
decision-maker. Every recommendation can be traced to a rule, an input, and a
rule version. This is the single most important design decision in the project and
it propagates everywhere — see [ADR-0003](docs/adr/0003-rule-engine-then-llm.md).

---

## What this demonstrates

| Capability | Where to look |
|---|---|
| AI systems design (rules → LLM, not LLM → everything) | [ADR-0003](docs/adr/0003-rule-engine-then-llm.md), [system-architecture](docs/architecture/system-architecture.md) |
| Production AI evaluation (accuracy, consistency, hallucination, regression) | [ADR-0005](docs/adr/0005-evaluation-framework.md) |
| LLM gateway / provider abstraction (OpenRouter) | [ADR-0004](docs/adr/0004-openrouter-llm-gateway.md) |
| Observability for AI (latency, tokens, cost, eval scores) | [system-architecture](docs/architecture/system-architecture.md#observability) |
| Multi-tenant isolation | [ADR-0006](docs/adr/0006-multi-tenancy-isolation.md) |
| Security-first engineering | [security-review](docs/security/security-review.md), [threat-model](docs/security/threat-model.md) |
| Layered architecture & domain boundaries | [ADR-0002](docs/adr/0002-layered-architecture.md) |
| Data modeling (Postgres, JSONB, pgvector) | [ERD](docs/architecture/erd.md), [schema](db/schema.sql), [ADR-0008](docs/adr/0008-postgres-jsonb-pgvector.md) |

---

## Technology stack

**Frontend** — Next.js (App Router), TypeScript, TailwindCSS, React Query, Zod
**Backend** — FastAPI, Python 3.12+, Pydantic v2, SQLAlchemy 2.x, Alembic
**Data** — PostgreSQL (JSONB + `pgvector`), Redis (cache + Celery broker)
**Jobs** — Celery (report generation, evaluation runs, LLM enhancement)
**Storage** — MinIO locally, S3-compatible abstraction in prod
**LLM** — OpenRouter as a single gateway across providers ([ADR-0004](docs/adr/0004-openrouter-llm-gateway.md))
**Reporting** — HTML → PDF via Playwright (Chromium)
**Infra** — Docker + Docker Compose
**Quality** — Pytest, Playwright, Ruff, Black, MyPy

Boring on purpose. Every component earns its place; see
[portfolio-story.md](docs/portfolio-story.md).

---

## System modules

1. **Identity & Access Management** — registration, login, password reset, profiles, RBAC.
2. **Organization Management** — orgs, members, invitations; hard tenant isolation.
3. **Assessment Engine** — dynamic, versioned assessment schemas across 7 categories.
4. **Rule Engine** — database-driven, editable-without-deploy deterministic recommendations.
5. **AI Recommendation Layer** — LLM enhancement over rule output, via OpenRouter.
6. **Evaluation Framework** — accuracy, consistency, completeness, hallucination rate; regression testing.
7. **Observability Layer** — request/LLM latency, tokens, cost, eval scores, dashboards.
8. **Report Generation** — executive summary, risk, security, governance, roadmap → PDF.
9. **Consultant Workspace** — review, edit findings, approve, publish.
10. **Admin Dashboard** — org/assessment/report/AI-usage/eval/system-health metrics.

---

## Repository layout

```
ai-advisory-platform/
├── README.md                          ← you are here
├── docker-compose.yml                 ← local dev topology (design)
├── .env.example                       ← required configuration surface
├── db/
│   └── schema.sql                     ← canonical PostgreSQL schema (DDL)
└── docs/
    ├── portfolio-story.md             ← why every decision was made
    ├── architecture/
    │   ├── system-architecture.md     ← C4-ish views + data flow
    │   └── erd.md                     ← entity-relationship model
    ├── adr/                           ← Architecture Decision Records
    │   ├── 0001 … record ADRs
    │   ├── 0002 … layered architecture
    │   ├── 0003 … rule engine → LLM
    │   ├── 0004 … OpenRouter gateway
    │   ├── 0005 … evaluation framework
    │   ├── 0006 … multi-tenancy isolation
    │   ├── 0007 … auth choice
    │   └── 0008 … Postgres / JSONB / pgvector
    ├── security/
    │   ├── security-review.md
    │   └── threat-model.md            ← STRIDE
    ├── api/
    │   └── openapi.yaml               ← contract-first API surface
    ├── deployment-guide.md
    └── onboarding-guide.md
```

---

## Status

All ten modules are **implemented and runnable** (`docker compose up --build` → a
click-through demo). What's built:

- **Rule-engine domain core** — safe condition evaluator, grounding check, LLM provider
  interface, evaluation framework (Phase 6).
- **Authorization + tenant-isolation kernel** and a layered service/repository
  `complete-assessment` use-case (Phases 4–5).
- **Real OpenRouter provider** (retries, backoff, token/cost telemetry),
  **SQLAlchemy repositories + Alembic**, and a **FastAPI API** with default-deny
  guards, sanitized errors, and secure headers (Phase 7 + app wiring).
- **Celery worker + report generation** (HTML→PDF via Playwright, behind a renderer
  interface; XSS-escaped content), **real session-token auth** verified in the API
  (the Next-BFF contract, [ADR-0009](docs/adr/0009-auth-bff-session-token.md)), and a
  **Next.js frontend** (App Router, React Query, Zod, Auth.js) whose BFF token-minting
  is the exact counterpart of the backend verifier.
- **Consultant workspace** (edit/approve/reject recommendations) with the **approval
  gate** before a report can publish, **admin + evaluation dashboards** (real metrics
  aggregation + persisted eval runs), and the **report endpoint** wired into the API.

The domain core runs with **zero dependencies**; the full backend has **140 passing
tests**, all offline (httpx `MockTransport`, SQLite, FastAPI `TestClient`, fake PDF
renderer). The whole assessment→review→publish lifecycle is exercised through HTTP:

```bash
cd backend
# domain core, no install:
PYTHONPATH=. python3 scripts/demo.py     # rule engine → grounded enhancement → eval gate
# full suite:
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
pytest -q                                # 140 passed
```

The frontend ([`frontend/`](frontend/README.md)) is a Next.js App Router app; its
`lib/` core typechecks clean and it runs with `npm install && npm run dev`.

The tests prove the security model as *executable* behaviour: fail-closed auth,
default-deny RBAC, and cross-tenant access blocked at **two** independent layers
(authorization **and** the tenant-scoped repository) — verified through the HTTP layer.

See [`backend/README.md`](backend/README.md). The build order, validation gates, and
what each phase produces are defined in
[`docs/portfolio-story.md`](docs/portfolio-story.md#build-phases). Code lands against
this design, not ahead of it.

## Run the whole thing

One command brings up the full stack on Postgres — no `OPENROUTER_API_KEY` needed
(the LLM layer falls back to a deterministic, grounded mock when no key is set):

```bash
cp .env.example .env
docker compose up --build        # postgres + redis + minio + api + worker + web
```

The `api` entrypoint runs Alembic migrations and seeds a demo org + assessment, then:

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API + OpenAPI docs | http://localhost:8000/v1 · http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |

**Click-through demo:** open the web app → **Sign in** (any email/password — the demo
provider issues an admin session for `demo-org`) → **Assessments** → open the seeded
assessment → **Complete** (rule engine + grounded LLM enhancement) → review and
**approve** the findings → **Publish report** (HTML→PDF, stored in MinIO) → check the
**Admin** and **Evaluation** dashboards.

For production topology, secrets, and operations see
[`docs/deployment-guide.md`](docs/deployment-guide.md) and
[`docs/onboarding-guide.md`](docs/onboarding-guide.md).

---

## License

Portfolio / educational use.
