"""The evaluation runner (ADR-0005).

Executes a dataset of gold cases against a pinned ruleset + LLM provider and produces
per-item and aggregate scores. Comparing two runs' aggregates *is* the regression
test: a prompt/model/rule change that drops accuracy or raises the hallucination rate
fails the gate. In CI this runs against the deterministic mock provider so results are
reproducible; on demand it can run against a live model via the same interface.

A dataset item (mirrors ``evaluation_dataset_items`` in db/schema.sql)::

    {"input": {"facts": {...}}, "expected": {"finding_codes": ["SEC-MFA-001", ...]}}
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.rules import engine
from app.domain.rules.models import Ruleset
from app.llm.enhancement import enhance_findings
from app.llm.provider import LLMProvider

from . import metrics


@dataclass(frozen=True)
class ItemResult:
    accuracy: float
    completeness: float
    consistency: float
    hallucination_rate: float
    passed: bool


@dataclass
class RunResult:
    accuracy: float = 0.0
    completeness: float = 0.0
    consistency: float = 0.0
    hallucination_rate: float = 0.0
    items: list[ItemResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(i.passed for i in self.items)


# Gate thresholds. A run that violates these fails CI (ADR-0005).
ACCURACY_FLOOR = 1.0  # the rule engine must reproduce the gold findings exactly
HALLUCINATION_CEIL = 0.0  # no ungrounded enhancement may slip through


def run(
    dataset: Sequence[Mapping[str, Any]],
    ruleset: Ruleset,
    provider: LLMProvider,
    *,
    consistency_repeats: int = 3,
) -> RunResult:
    results: list[ItemResult] = []
    for item in dataset:
        facts = item["input"]["facts"]
        expected = item["expected"]["finding_codes"]

        # Run the engine multiple times to measure consistency.
        runs = [
            [f.rule_code for f in engine.evaluate(ruleset, facts)]
            for _ in range(consistency_repeats)
        ]
        produced = runs[0]

        recs = enhance_findings(engine.evaluate(ruleset, facts), provider)

        acc = metrics.accuracy(produced, expected)
        comp = metrics.completeness(produced, expected)
        cons = metrics.consistency(runs)
        hall = metrics.hallucination_rate(recs)

        results.append(
            ItemResult(
                accuracy=acc,
                completeness=comp,
                consistency=cons,
                hallucination_rate=hall,
                passed=(acc >= ACCURACY_FLOOR and hall <= HALLUCINATION_CEIL and cons == 1.0),
            )
        )

    n = len(results) or 1
    return RunResult(
        accuracy=sum(r.accuracy for r in results) / n,
        completeness=sum(r.completeness for r in results) / n,
        consistency=sum(r.consistency for r in results) / n,
        hallucination_rate=sum(r.hallucination_rate for r in results) / n,
        items=results,
    )
