# Developer Onboarding Guide

Welcome. This gets you productive and, more importantly, gets you to *understand the
system* — which here is the actual point. Read in this order:

1. [`README.md`](../README.md) — the thesis (rules → LLM, not LLM → everything).
2. [`docs/architecture/system-architecture.md`](architecture/system-architecture.md) — the shape.
3. [`docs/portfolio-story.md`](portfolio-story.md) — why every decision was made.
4. The [ADRs](adr/) — the decisions themselves.

If you internalize one thing: **the rule engine is the source of truth; the LLM only
explains it.** Most of the codebase's structure exists to protect that invariant.

---

## Get it running

See the [deployment guide §2](deployment-guide.md). TL;DR:

```bash
cp .env.example .env       # fill secrets + OPENROUTER_API_KEY (optional locally)
docker compose up -d
open http://localhost:3000
```

You do **not** need an `OPENROUTER_API_KEY` to develop most things — the LLM client
has a deterministic mock implementation (ADR-0004) that the app and the entire test
suite use by default. Set a real key only when working on enhancement quality.

---

## Where things live (and the rules that keep it clean)

See [ADR-0002](adr/0002-layered-architecture.md). The map:

```
backend/app/
├── api/          HTTP only. Parse → authorize → call a service → serialize. No logic.
├── services/     Use-cases + transactions. No SQL, no Request/Response objects.
├── domain/       Pure logic: rule engine, scoring, entities. NO I/O. Test without a DB.
├── repositories/ The ONLY place SQLAlchemy lives. Enforces tenant scope.
├── llm/          OpenRouter client + mock, versioned prompts, enhancement pipeline.
├── eval/         Datasets, metrics, runners. Regression tests for rules + LLM.
├── observability/ tracing, metrics, cost accounting, structured logs.
├── infra/        config, db, redis, storage, celery.
└── schemas/      Pydantic v2 DTOs (the API contract types).
frontend/         Next.js (App Router), TS, Tailwind, React Query, Zod.
```

"Where does my code go?" decision tree:

- Touches HTTP / status codes? → `api/` (and only that).
- A user-facing operation spanning multiple steps/tables? → `services/`.
- A pure decision/calculation with no I/O? → `domain/` (write exhaustive unit tests).
- Reads/writes the database? → `repositories/` (never elsewhere).
- Talks to a model? → `llm/` (behind the provider interface).

If you're tempted to write SQL in a service or business logic in a router, stop —
that's the one thing this architecture exists to prevent.

---

## Daily workflow

```bash
# Backend
ruff check . && black --check . && mypy app        # lint, format, types
pytest                                             # unit + integration (mock LLM)
alembic revision --autogenerate -m "msg"           # new migration
alembic upgrade head

# Frontend
pnpm lint && pnpm typecheck
pnpm test          # component/unit
pnpm playwright test   # e2e
```

CI gates the same checks plus two project-specific ones:

- **Every route is guarded** (default-deny RBAC; ADR-0007) — an unguarded route fails.
- **Cross-tenant isolation suite** (ADR-0006) — tenant A must never see tenant B.
- **`db/schema.sql` matches the Alembic head.**
- **Evaluation regression** (against the mock provider) — accuracy can't drop /
  hallucination rate can't rise past thresholds (ADR-0005).

---

## How to make common changes

| Task | What to do | Notes |
|---|---|---|
| Add a recommendation rule | Insert a `rules` row (API or seed) — **no deploy** | Conditions are a safe expression tree, not code. Add an eval fixture. |
| Add a question type | Extend the `questions.type` enum + server-side validator + a Zod schema | JSONB `value` keeps the DB stable (ADR-0008). |
| Tune a prompt | New `prompt_versions` row; run an eval run to compare before activating | Never edit prompts in code as strings. |
| Swap/compare models | New `model_versions` row (model id + pricing); eval run | Model is config, not code (ADR-0004). |
| Add an endpoint | Router + DTO + service + repository; **declare its RBAC guard** | Undeclared = forbidden. Add a tenant-isolation test. |

---

## Gotchas / house rules

- **Never read tenant id from the request.** It comes from the session. (ADR-0006)
- **Never `eval()` a rule condition.** Use the safe interpreter. (threat model: tampering)
- **Never put cross-tenant data or secrets in an LLM prompt.** (threat model: disclosure)
- **Never return a stack trace.** The global handler sanitizes; detail goes to logs.
- **Treat LLM output as untrusted data** — it can't change findings and must pass the
  grounding check before it's surfaced. (ADR-0003/0005)
- **Documents are unusable until `scan_status = clean`.** (security review §5)

---

## Glossary

- **Finding** — a deterministic result from the rule engine. The source of truth.
- **Recommendation** — a finding + optional LLM narrative + provenance.
- **Enhancement** — the LLM step that writes narrative fields over findings.
- **Grounding check** — verifies the narrative asserts nothing the findings don't.
- **Ruleset version** — a pinned, versioned set of rules an assessment is evaluated against.
- **Eval run** — a dataset executed against a (prompt version, model version); the unit
  of regression testing.
