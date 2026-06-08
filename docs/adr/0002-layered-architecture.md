# ADR-0002: Four-layer architecture with a pure domain core

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

The platform mixes deterministic business logic (the rule engine), external I/O
(database, object store, LLM), and an HTTP surface. Without explicit boundaries,
business logic leaks into route handlers and SQL leaks into services — the two
failure modes that make a codebase hard to test and reason about. The brief is
explicit: "keep business logic out of routes; keep persistence logic out of
services; use dependency injection; use clear domain boundaries."

## Decision

Adopt a strict four-layer architecture inside both the `api` and `worker`
processes, with dependencies pointing in one direction only:

```
API Layer  →  Service Layer  →  Domain Layer
                     │
                     └────────→  Repository Layer  →  PostgreSQL
```

- **API layer** (`app/api`): FastAPI routers. HTTP concerns only — parse, authorize
  (via DI dependencies), delegate to a service, serialize. No business logic.
- **Service layer** (`app/services`): use-cases and transaction boundaries.
  Orchestrates domain + repositories + the LLM/eval packages. No SQL, no `Request`/`Response`.
- **Domain layer** (`app/domain`): pure business logic — entities, value objects,
  the **rule engine**, scoring. **Imports no I/O.** Unit-testable without a database.
- **Repository layer** (`app/repositories`): the *only* place SQLAlchemy is used.
  Repositories also enforce tenant scoping (ADR-0006).

Wiring is via FastAPI dependency injection: DB session, current principal, tenant
context, and role guards are injected, never reached for globally.

## Alternatives considered

- **Fat routers / "FastAPI CRUD" style.** Fastest to start, but business logic and
  authorization scatter across handlers and become untestable. Rejected.
- **Hexagonal / ports-and-adapters with full interface inversion everywhere.**
  Cleaner in theory, but the indirection is overkill for this scope and violates
  "avoid premature abstraction." We invert only where it pays: the LLM provider and
  storage are behind interfaces; repositories are concrete classes.

## Consequences

- **+** The rule engine — the most important code — is pure and exhaustively
  testable. This is what makes the evaluation framework (ADR-0005) tractable.
- **+** The LLM layer can be mocked at the service boundary; business logic tests
  never call a model.
- **+** Clear answer to "where does X go?" reduces review friction.
- **−** More files and one more hop than a CRUD app. Accepted; the boundaries are the
  point. We do **not** add a layer (e.g. a separate DTO-mapping layer) unless a
  concrete need appears.
