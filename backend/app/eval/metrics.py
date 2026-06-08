"""Evaluation metrics (ADR-0005).

Because the LLM only enhances deterministic findings, the rule-engine output is a
*ground truth* we can score against programmatically — no flaky LLM-judge needed for
correctness. These are pure functions over sets/lists so they are trivially testable
and identical in CI and production.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.llm.enhancement import Recommendation


def accuracy(produced_codes: Sequence[str], expected_codes: Sequence[str]) -> float:
    """Jaccard overlap between produced and expected finding codes.

    1.0 == exactly the right findings (no misses, no spurious extras). Penalises both
    false negatives and false positives, which is what you want for a recommender.
    """
    produced, expected = set(produced_codes), set(expected_codes)
    if not produced and not expected:
        return 1.0
    union = produced | expected
    return len(produced & expected) / len(union) if union else 1.0


def completeness(produced_codes: Sequence[str], expected_codes: Sequence[str]) -> float:
    """Recall: fraction of expected findings that were produced."""
    expected = set(expected_codes)
    if not expected:
        return 1.0
    return len(set(produced_codes) & expected) / len(expected)


def consistency(runs: Sequence[Sequence[str]]) -> float:
    """1.0 if every run produced an identical (ordered) finding list, else 0.0.

    Targets LLM non-determinism / engine instability. The deterministic engine should
    score a perfect 1.0; any drift here is a real regression.
    """
    if len(runs) <= 1:
        return 1.0
    first = list(runs[0])
    return 1.0 if all(list(r) == first for r in runs[1:]) else 0.0


def hallucination_rate(recommendations: Sequence[Recommendation]) -> float:
    """Fraction of LLM-attempted enhancements that failed the grounding check.

    Provider errors (grounding_passed is None — the model was never trusted) are
    excluded from the denominator: this measures *hallucination*, not *availability*.
    """
    attempted = [r for r in recommendations if r.grounding_passed is not None]
    if not attempted:
        return 0.0
    rejected = sum(1 for r in attempted if r.grounding_passed is False)
    return rejected / len(attempted)
