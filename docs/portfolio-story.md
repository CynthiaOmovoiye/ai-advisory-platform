# Portfolio Story — why this is built the way it is

This document exists to answer one question a senior engineering leader will ask:
*"Does the author understand how production AI systems are actually designed,
governed, evaluated, observed, and operated — or did they wrap an LLM and call it a
product?"*

Every section below is a decision and the reasoning behind it. The short version:
**this system treats the LLM as the least-trusted component, not the most important
one.** Everything else follows from that.

---

## The one decision everything hangs on

> **A deterministic rule engine is the source of truth. The LLM only explains its
> output. It never decides, and it cannot invent findings.**
> ([ADR-0003](adr/0003-rule-engine-then-llm.md))

Why this, and not the obvious "let the LLM generate recommendations"?

Because the product gives **consequential, high-stakes advice** — security,
governance, compliance, risk. A buyer needs that advice to be **correct, consistent,
auditable, and defensible in front of their own auditors.** Those four properties are
exactly the ones an LLM cannot guarantee on its own: it hallucinates, it varies
run-to-run, and you cannot unit-test or audit a generation the way you can a rule.

So the data flows `rules → LLM`, and the LLM is boxed in three ways:

1. It runs **after** findings already exist and are persisted — so the system
   produces a complete answer even if the model is down.
2. It writes **named narrative fields only** (summary, rationale, remediation prose),
   given the findings as structured input.
3. Its output must pass a **grounding check** — a programmatic verification that the
   narrative asserts nothing absent from the deterministic findings — or it's
   rejected in favor of a template-rendered fallback.

This is the difference between *prompt engineering* and *AI systems engineering*:
hallucination here is **structurally bounded**, not wished away with a better prompt.
Everything downstream — the schema, the eval framework, the threat model — is
shaped by protecting this invariant.

---

## Why these architectural choices

**Four-layer architecture with a pure domain core** ([ADR-0002](adr/0002-layered-architecture.md)).
The rule engine is the most important code in the system, so it lives in a domain
layer that imports no I/O and can be tested exhaustively without a database. Routers
do HTTP, services do use-cases and transactions, repositories are the only place SQL
exists. This isn't ceremony — it's what makes the rule engine testable and the LLM
mockable, which is what makes the evaluation framework possible. I deliberately did
*not* go full hexagonal/ports-everywhere: I invert only the LLM provider and storage,
where swapping matters. Avoiding premature abstraction is itself a decision.

**A separate worker tier** (architecture §2). LLM calls and PDF rendering take
seconds to tens of seconds and are bursty. Putting them behind Celery keeps API
latency flat and lets the two tiers scale on different signals (request load vs queue
depth). It also isolates blast radius: a stuck LLM call can't consume request
capacity.

**Provider abstraction over OpenRouter** ([ADR-0004](adr/0004-openrouter-llm-gateway.md)).
Routing all LLM traffic through OpenRouter behind a narrow `LLMProvider` interface
turns *model choice into configuration*. That single decision is what lets the
evaluation framework run the same dataset across models, gives one choke point for
cost/latency/token capture, and makes the test suite hermetic via a deterministic
mock. One monitored egress is also simpler to secure.

---

## Why the data model looks like this

**Postgres for everything, JSONB only where the schema is genuinely dynamic, pgvector
reserved** ([ADR-0008](adr/0008-postgres-jsonb-pgvector.md)). The data has three
shapes — stable relational (users, rules, reports), genuinely dynamic (assessment
definitions and responses), and future-vector (RAG). One boring datastore handles all
three: relational columns keep integrity where the shape is stable; JSONB absorbs the
dynamic assessment schema so consultants can author question types without a
migration; pgvector is *enabled but unused*, with the `knowledge_chunks` table
designed and commented out. That last point is the brief's "design the extension
points, don't build them" made concrete — RAG becomes a migration *within* Postgres,
not a new system to operate.

**Provenance lives on the recommendation row.** Each `recommendations` row carries the
deterministic fields, the LLM narrative, *which* prompt and model version produced it,
and whether it passed grounding. That single row is the reproducibility and audit
story: you can always answer "what did the rule decide, what did the model say, and
how was it made." The same instinct drives versioned `prompt_versions`,
`model_versions` (with pricing, for cost accounting), and `rulesets`.

---

## Why evaluation is a first-class subsystem, not a script

([ADR-0005](adr/0005-evaluation-framework.md)) In a real AI system "is the output
good?" has to be *measured, version-pinned, and regression-tested* — not vibes-checked
in a notebook that rots in a week. This design exploits something most LLM products
don't have: a **ground truth**. Because the LLM only enhances deterministic findings,
the rule-engine output *is* the gold standard, so correctness can be checked
programmatically (set comparison) rather than with a flaky LLM judge.

The framework measures accuracy, completeness, consistency (re-run variance, aimed
squarely at LLM non-determinism), and hallucination/grounding rate. Crucially, **the
grounding check is the same code in eval and in production** — so I have real
confidence the safety control works, not just a benchmark number. Runs pin a
`(prompt_version, model_version)`, so comparing runs *is* the regression test, and it
runs in CI against the mock provider. It also regression-tests the rule engine itself
— which matters because rules are editable without a deploy and therefore need a
safety net.

---

## Why observability is in from day one

([architecture §7](architecture/system-architecture.md#observability)) An AI system
you can't see the cost of is a liability. Every LLM call writes latency, tokens, and
**estimated cost** (tokens × per-model rates from `model_versions`) to `llm_calls`,
tied by a correlation id from web → api → worker → model. That's what powers the admin
dashboard's spend-by-org/model/time view and the denial-of-wallet alerting. Tracking
cost and reliability as first-class signals — not just "does it return a string" — is
the line between operating an AI system and demoing one.

---

## Why security looks the way it does

Security is treated as a feature and designed in from Phase 1, not bolted on at
Phase 12 (even though there's a Phase 12 review). The decisions that matter most:

- **Cross-tenant isolation is the highest-severity risk, so it's defended twice**
  ([ADR-0006](adr/0006-multi-tenancy-isolation.md)): tenant id derived from the
  session (never the request), central repository scoping so a dev *can't* forget the
  filter, **and** Postgres RLS as an independent backstop. Two layers must both fail
  to leak data, and a mandatory test suite proves tenant A can't see tenant B.
- **Default-deny RBAC** ([ADR-0007](adr/0007-auth-choice.md)): every route declares
  its guard; an undeclared route is forbidden, and CI fails the build if any route
  lacks one. Authentication is delegated to a managed library because hand-rolling it
  is how you ship CVEs; authorization stays in-house because it's product logic.
- **The LLM's blast radius is structural, not just prompt-level.** Prompt injection in
  assessment text can't change a recommendation, because the LLM can't change findings
  and its output is grounding-checked and human-reviewed. Prompts never contain
  secrets or cross-tenant data, so there's nothing to exfiltrate. See the
  [threat model](security/threat-model.md).
- **Rules are data, so rule conditions are a sandboxed expression tree — never
  `eval()`.** Editability-without-deploy is a feature; arbitrary code execution is
  not.

---

## Extension points (designed, not built)

The brief asks for the architecture to support future AI features without building
them. These are real, named seams, not vapor:

- **RAG / semantic search:** pgvector enabled, `knowledge_chunks` table designed,
  access already routes through the repository + `llm/` layers.
- **Agent workflows / memory:** the worker + Celery topology already does multi-step
  async orchestration; agent state would land as `agent_runs`/`agent_steps`.
- **Human-in-the-loop:** already partially present via `recommendations.status` +
  consultant approval; a dedicated review queue is the natural next table.

Reserving these as seams rather than speculative tables *is* the engineering judgment
— ready to grow, not bloated now.

---

## Build phases & validation gates

The work is sequenced so each phase is internally validated before the next. Phases
1–3 plus the design of 4–12 are captured in this documentation set; code lands against
this design.

| Phase | Output | Gate before moving on |
|---|---|---|
| 1 Requirements | scope, risks, this doc set's premises | thesis (rules→LLM) agreed |
| 2 Architecture | [system-architecture](architecture/system-architecture.md), [ADRs 1–8](adr/) | boundaries reviewed |
| 3 Database | [ERD](architecture/erd.md), [schema.sql](../db/schema.sql) | schema models all modules + future seams |
| 4 AuthN/Z | managed auth, default-deny RBAC | every-route-guarded test |
| 5 Assessment engine | dynamic schemas, 7 categories | dynamic schema round-trips |
| 6 Rule engine | DB-driven, editable, sandboxed conditions | unit-tested evaluator |
| 7 AI layer | OpenRouter enhancement + grounding + fallback | grounding rejects ungrounded output |
| 8 Evaluation | datasets, runs, metrics, regression in CI | regression gate green |
| 9 Observability | latency/tokens/cost/eval dashboards | cost visible per org/model |
| 10 Reporting | HTML→PDF via Playwright | sanitized render, no XSS |
| 11 Testing | pytest + Playwright + isolation + eval | coverage of critical paths |
| 12 Security review | [security-review](security/security-review.md), [threat-model](security/threat-model.md) | top-5 controls verified |

At each phase boundary: review the decisions, name the risks, refactor if needed,
update the docs, and write an ADR for anything significant.

---

## What I'd want a reviewer to take away

1. The author put the LLM **behind** a deterministic, auditable core — and shaped the
   whole system to keep it there.
2. Evaluation, observability, and security are **first-class subsystems with ground
   truth and gates**, not afterthoughts.
3. The boring choices (one Postgres, four layers, managed auth, no premature
   abstraction) are **deliberate** and defended in ADRs.
4. The hard parts of *operating* AI — cost, reliability, regression, tenant isolation,
   hallucination control — are designed for, not hand-waved.

That's the difference between an Applied AI Engineer who understands production
systems and a hobbyist who understands prompts.
