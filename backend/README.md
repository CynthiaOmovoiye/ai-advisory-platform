# Backend

FastAPI backend for the AI Advisory Platform. This phase ships the **rule-engine
domain core** — the heart of the thesis (ADR-0003) — as runnable, tested code.

## What's implemented now

Two tiers. The **domain core runs with zero third-party dependencies** (ADR-0002), so
it tests anywhere with just Python 3.12+. The **application tier** (OpenRouter client,
SQLAlchemy persistence, FastAPI API) adds the real stack and is fully tested offline
(httpx `MockTransport`, SQLite, FastAPI `TestClient`).

### Domain core (no deps)

| Package | What |
|---|---|
| `app/domain/rules/conditions.py` | **Safe condition evaluator** — fixed operator set, no `eval`/`exec`. The security-critical core (threat-model: rule-condition injection). |
| `app/domain/rules/models.py` | Rule / Ruleset / Finding entities; JSON loaders. |
| `app/domain/rules/engine.py` | `evaluate(ruleset, facts) -> findings` — pure, deterministic, reproducible. Format-string-safe template rendering. |
| `app/domain/grounding.py` | **Grounding check** — the hallucination control (ADR-0005). |
| `app/llm/provider.py` | The narrow `LLMProvider` interface (ADR-0004). |
| `app/llm/mock.py` | Deterministic mock + a fabricating + a failing provider (to test the safety paths). |
| `app/llm/enhancement.py` | findings → recommendations, gated by grounding, with deterministic fallback. |
| `app/eval/` | Metrics + a regression-gate runner (ADR-0005). |
| `app/domain/access.py` | **Authorization kernel** — default-deny RBAC composed with tenant scope (ADR-0007 + half of ADR-0006). |
| `app/repositories/` | Tenant-scoped repository contract + in-memory impl. Isolation enforced mechanically (ADR-0006). |
| `app/services/assessment_service.py` | The `complete-assessment` **use-case**: authorize → load (scoped) → rule engine → enhance → persist → audit (ADR-0002). |
| `app/errors.py` | Sanitized error taxonomy (Unauthorized / Forbidden / NotFound / Conflict). |
| `data/` | Seed `baseline-v1` ruleset and a gold eval dataset. |

### Application tier (needs the dev/runtime deps)

| Package | What |
|---|---|
| `app/llm/openrouter.py` | **Real OpenRouter provider** (ADR-0004): structured output, bounded retries + exponential backoff, and token/cost/latency telemetry (`llm_calls`). Pure helpers split from httpx I/O. |
| `app/infra/` | Settings (env-driven) + DB engine/session plumbing (JSONB on Postgres, JSON on SQLite). |
| `app/repositories/orm.py`, `sql.py` | SQLAlchemy ORM + **SQL repositories** satisfying the same Protocols as the in-memory ones — tenant scope enforced in every query (ADR-0006). |
| `app/services/auth_service.py` | Real credential auth: signup, Argon2 password hashing, email verification, signin, password reset (with session invalidation via `session_version`), and membership-derived session claims. |
| `app/infra/email.py`, `app/services/notification_service.py` | Pluggable email transport (console / SMTP / Resend) + the verification/reset email templates. |
| `migrations/` | **Alembic** setup + initial migration (`0001_initial`). |
| `app/api/` | FastAPI app: DI (`deps.py`), the default-deny guard, assessment routes, sanitized error handlers, secure headers, correlation ids. |
| `app/schemas/` | Pydantic v2 API DTOs. |

## Run it

**Domain core — no install required:**

```bash
cd backend

# the 45 domain tests — stdlib unittest, zero dependencies
PYTHONPATH=. python3 -m unittest tests.test_conditions tests.test_engine \
  tests.test_grounding tests.test_enhancement tests.test_eval \
  tests.test_access tests.test_assessment_service

# end-to-end domain demo: rule engine → grounded enhancement → eval gate
PYTHONPATH=. python3 scripts/demo.py
```

**Full suite (66 tests) — with the app stack:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                       # 66 passed  (httpx MockTransport + SQLite + TestClient)

# apply the Alembic migration to any DB
DATABASE_URL="sqlite+pysqlite:///./dev.db" alembic upgrade head
```

`ruff` / `black` / `mypy --strict` are configured in `pyproject.toml`. The full app
runs against Postgres in Docker — see [../docs/deployment-guide.md](../docs/deployment-guide.md).

## The invariant these modules protect

> The rule engine produces findings (the source of truth). The LLM only writes
> narrative *over* those findings, and only narrative that passes the grounding
> check survives. An LLM that is down, slow, or hallucinating degrades polish, never
> correctness — every finding still yields a complete recommendation.

The tests prove each leg of that: `test_enhancement.py` shows the grounded / rejected
/ outage paths all yield valid recommendations; `test_eval.py` shows a hallucinating
model is caught by the regression gate while the deterministic accuracy stays at 1.0.

## What's implemented (the full application)

Beyond the pure domain core above, the application is wired end to end:

- **FastAPI app + routers** (`app/api/`) — assessments, templates, organizations/members,
  recommendations (consultant workspace), reports, documents (uploads), admin metrics,
  evaluation, with default-deny guards, sanitized errors, secure headers, CORS, rate
  limiting, request-size limits, and `/healthz` + `/readyz`.
- **Service layer** (`app/services/`) — auth, assessment, template, organization,
  recommendation, evaluation, document, metrics.
- **SQLAlchemy repositories + Alembic migrations** (`app/repositories/`, `migrations/`) —
  11 migrations, incl. Postgres Row-Level Security (`0009`), a non-superuser
  `app_role` (`0010`) so RLS is actually enforced, and persisted users/verification
  tokens (`0011`).
- **Real OpenRouter provider** (`app/llm/openrouter.py`) with retries + token/cost telemetry,
  plus the deterministic mock used by default offline.
- **Celery worker** (`app/worker/tasks.py`) — async report rendering (HTML→PDF, Playwright)
  and the document malware-scan task.

Verification: `pytest -q` (158 tests), `ruff check .`, `ruff format --check .`, `mypy app`,
`alembic upgrade head` + `python scripts/check_migrations.py` — all green in CI.

## Intentional extension points (designed, not built)

RAG/pgvector knowledge base, agent workflows, a human-in-the-loop review-queue table,
and a real malware scanner behind the scan interface. (Email delivery — SMTP/Resend —
and password reset are now implemented; see `app/infra/email.py` and the
`/auth/forgot-password` + `/auth/reset-password` routes.)
