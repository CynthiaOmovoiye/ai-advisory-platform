# ADR-0003: Deterministic rule engine is the source of truth; the LLM only enhances

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering
- **Significance:** This is the defining decision of the system.

## Context

The product makes consequential recommendations — security, governance, compliance,
risk. Buyers need those recommendations to be **correct, consistent, auditable, and
defensible**. LLMs are excellent at language and explanation and unreliable at being
a system of record: they hallucinate, vary run-to-run, and can't be unit-tested or
audited the way a rule can. A naive "LLM → everything" design would put an
unverifiable component on the critical path of high-stakes advice.

## Decision

Recommendations flow **rule engine → LLM enhancement**, never **LLM → everything.**

1. A **database-driven rule engine** (the `rules` table, editable without deploy)
   evaluates assessment responses against a *pinned ruleset version* and produces
   `findings` and `recommendations`. This is deterministic, versioned, traceable to
   the input and the rule, and the **source of truth**. It runs and persists
   *before* any LLM call.
2. The **LLM enhances named narrative fields only** — executive summary, rationale,
   remediation prose, roadmap language. It receives the deterministic findings as
   structured input and is instructed to *explain*, not to *decide* or *add*
   findings.
3. Every enhancement passes a **grounding check** (ADR-0005): the narrative must not
   assert any finding absent from the deterministic set. Fail ⇒ reject the LLM output
   and fall back to a template-rendered deterministic narrative.
4. Rule conditions are a **safe boolean expression tree** (JSONB), evaluated by a
   sandboxed interpreter. We never `eval()` rule data — see the threat model.

Example rule: `IF mfa_enabled == false AND sensitive_data_present == true THEN
recommend "Enforce MFA" (category: security, severity: high)`. The decision is the
rule's; the LLM only writes the paragraph explaining it to an executive.

## Alternatives considered

- **LLM generates recommendations directly, with a verifier.** More flexible, but the
  verifier becomes the hard problem and correctness is never guaranteed. Wrong fit
  for high-stakes, auditable advice.
- **Pure rule engine, no LLM.** Correct and auditable but the reports read like a
  linter. The LLM earns its place precisely at the language layer — explanation,
  summarization, tone — where it is strong and low-risk *because it can't change the
  findings.*

## Consequences

- **+** Recommendations are reproducible and auditable: every one traces to a rule,
  an input, and a ruleset version.
- **+** The system **degrades gracefully** — an LLM outage costs polish, not
  function.
- **+** Rules are editable by domain experts without code deployment, which is the
  Module 4 requirement.
- **+** Hallucination is *structurally* bounded, not just prompt-engineered away.
- **−** Less "magical" than an end-to-end LLM. That is the intended trade: this is a
  system a security leader can trust, not a demo.
- Implies the data model carries rule provenance and grounding state on every
  recommendation (see ERD / schema).
