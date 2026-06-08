"""Evaluation service (Module 6 → eval dashboard).

Runs the existing evaluation framework (app/eval) against a dataset + the active
ruleset + an LLM provider, then **persists the aggregate scores** so the admin
dashboard can show eval performance over time and detect regression (ADR-0005).

The heavy lifting is the pure runner; this service just orchestrates it, applies the
pass/fail gate, and stores the result.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.rules.models import Ruleset
from app.eval import runner
from app.eval.runner import RunResult
from app.llm.provider import LLMProvider


@dataclass(frozen=True)
class EvaluationRunRecord:
    id: str
    dataset_name: str
    ruleset_name: str
    model_id: str
    status: str
    accuracy: float
    consistency: float
    completeness: float
    hallucination_rate: float
    item_count: int
    triggered_by: str | None


class EvaluationRunRepository(Protocol):
    def save(self, run: EvaluationRunRecord) -> None: ...
    def list_recent(self, limit: int = 50) -> list[EvaluationRunRecord]: ...


@dataclass
class EvaluationService:
    runs: EvaluationRunRepository
    ruleset: Ruleset
    llm: LLMProvider

    def run(
        self,
        dataset_name: str,
        dataset: Sequence[dict],
        *,
        model_id: str,
        triggered_by: str | None,
    ) -> EvaluationRunRecord:
        result: RunResult = runner.run(dataset, self.ruleset, self.llm)
        record = EvaluationRunRecord(
            id=str(uuid.uuid4()),
            dataset_name=dataset_name,
            ruleset_name=self.ruleset.name,
            model_id=model_id,
            status="completed" if result.passed else "failed",
            accuracy=round(result.accuracy, 4),
            consistency=round(result.consistency, 4),
            completeness=round(result.completeness, 4),
            hallucination_rate=round(result.hallucination_rate, 4),
            item_count=len(result.items),
            triggered_by=triggered_by,
        )
        self.runs.save(record)
        return record

    def list_recent(self, limit: int = 50) -> list[EvaluationRunRecord]:
        return self.runs.list_recent(limit)
