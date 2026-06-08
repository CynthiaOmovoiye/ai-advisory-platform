# ADR-0004: OpenRouter as the single LLM gateway, behind a provider interface

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

The system needs LLM access for the enhancement layer (ADR-0003) and, later, for
evaluation-as-judge. Requirements: switch models without code changes, A/B prompts
and models for the evaluation framework, capture token usage and cost for
observability, and avoid lock-in to a single vendor's SDK. We also want a single,
controllable egress point for security and cost governance.

## Decision

Route **all** LLM traffic through **OpenRouter**, accessed via a thin internal
`LLMProvider` interface in `app/llm/`.

- **OpenRouter** gives one API across many providers/models. Model selection becomes
  *configuration* (`model_versions.model_id`, e.g. `anthropic/claude-...`), not code.
  This directly enables the evaluation framework to run the same dataset across
  models.
- A narrow **`LLMProvider` interface** wraps it: `complete(prompt, schema, model,
  params) -> StructuredResult`. The OpenRouter client is one implementation; a
  **deterministic mock implementation** backs tests and CI so the suite never makes
  a network call or spends money.
- The wrapper is the **single choke point** for: structured-output enforcement,
  timeouts + retry/backoff, the circuit-breaker to the deterministic fallback,
  redaction of inputs in logs, and **token/cost/latency capture** written to
  `llm_calls`.
- **One egress.** All model traffic leaves through this client to OpenRouter, which
  simplifies the threat model (one external dependency to allowlist, rate-limit, and
  monitor) and centralizes spend.

## Alternatives considered

- **Direct Anthropic/OpenAI SDKs.** Simpler for one model, but every model swap is a
  code change and the eval framework can't fan a dataset across providers. Rejected
  for this system's needs.
- **LangChain / heavier orchestration framework.** Brings abstractions we don't need
  yet (chains, agents) and obscures the cost/latency capture we *do* need. Violates
  "prefer boring, explicit." Rejected; we can adopt targeted pieces later behind the
  same interface.

## Consequences

- **+** Model is configuration; the eval framework can compare models trivially.
- **+** Cost, tokens, latency, and failures are captured in one place for every call.
- **+** Tests are hermetic and free (mock provider).
- **+** Single egress point is easier to secure, rate-limit, and budget.
- **−** OpenRouter is an added dependency and a potential single point of failure for
  *enhancement*. Mitigated: the deterministic fallback means LLM/gateway downtime
  never blocks core function; we can add a second provider implementation behind the
  same interface if needed.
- **−** Slightly less access to provider-specific features. Acceptable for the
  enhancement use-case.
- **Security note:** `OPENROUTER_API_KEY` is a high-value secret — see threat model
  (secrets handling) and the data-protection section of the security review.
