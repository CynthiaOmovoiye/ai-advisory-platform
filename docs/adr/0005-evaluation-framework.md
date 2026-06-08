# ADR-0005: Evaluation framework as a first-class, regression-testable subsystem

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

The brief makes evaluation a first-class feature, and rightly: in a production AI
system, "is the output good?" must be a measured, version-pinned, regression-tested
property — not a vibe. Because our LLM only *enhances* deterministic findings
(ADR-0003), we have something most LLM products lack: a **ground truth** to evaluate
against (the rule-engine output). We should exploit that.

## Decision

Build an evaluation subsystem (`app/eval/`) with versioned datasets, runs pinned to a
`(prompt_version, model_version)`, and per-item + aggregate metrics persisted for
regression comparison.

**Metrics** (all stored on `evaluations.metrics` / aggregated on `evaluation_runs`):

| Metric | What it measures | How |
|---|---|---|
| **Grounding / hallucination rate** | Does the LLM narrative assert findings *not* in the deterministic set? | Programmatic check of narrative claims against the rule-engine findings for that case. This is the primary safety gate and runs **in production on every enhancement**, not only in eval. |
| **Accuracy** | Do produced findings match the gold expected findings for a fixture? | Set comparison of rule-engine output vs `expected` (also validates the rule engine itself — regression on rules). |
| **Completeness** | Are all expected findings present and addressed in the narrative? | Coverage of expected items. |
| **Consistency** | Same input ⇒ stable output across repeated runs? | Re-run N times; measure variance of findings/structure. Targets the LLM's non-determinism. |

**Mechanics:**

- **Datasets are versioned, curated fixtures** (`evaluation_datasets` /
  `_dataset_items`): gold assessment responses + expected findings + acceptable
  narrative constraints. Curated from real assessment shapes and known edge cases.
- **A run pins prompt + model versions.** Comparing runs across versions *is* the
  regression test: a new prompt or model that drops accuracy or raises hallucination
  rate fails the gate. This runs in CI against the mock provider for determinism and
  can be triggered against live models on demand.
- **Grounding doubles as a runtime control.** The same grounding check that scores an
  eval item gates every production enhancement (ADR-0003 step 3).
- **LLM-as-judge is used sparingly and only for fuzzy qualities** (e.g. clarity),
  never for correctness — correctness is checked programmatically against ground
  truth. Where a judge is used, it runs via the same OpenRouter interface and its
  prompt/model are themselves versioned.

## Alternatives considered

- **Eval as ad-hoc scripts run by hand.** The common failure mode; results aren't
  comparable or reproducible and rot immediately. Rejected — datasets and runs are
  first-class tables.
- **Pure LLM-as-judge for everything.** Circular and unreliable for correctness.
  We have real ground truth; we use it.

## Consequences

- **+** Prompt/model changes are gated by measurable regression, not hope.
- **+** Hallucination control is the same code in eval and in production — high
  confidence it actually works.
- **+** The framework also regression-tests the **rule engine** (accuracy metric),
  catching unintended changes when rules are edited (recall: rules are editable
  without deploy, so they *need* a safety net).
- **−** Curating quality datasets is real, ongoing work. Accepted — it's the cost of
  doing AI seriously, and it's exactly what the project is meant to demonstrate.
