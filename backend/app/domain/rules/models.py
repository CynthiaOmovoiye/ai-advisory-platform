"""Domain entities for the rule engine.

Pure dataclasses, **no I/O and no ORM** (ADR-0002): the domain layer is unit-testable
without a database. In the running system the persistence shapes are SQLAlchemy
models in ``app/repositories`` and the API DTOs are Pydantic models in
``app/schemas``; these entities are the in-memory business objects the engine works
with. Field names mirror db/schema.sql.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Mapping, Sequence

from .conditions import validate_condition

# Categories — must match the CHECK constraint in db/schema.sql.
CATEGORIES = frozenset(
    {
        "ai_readiness",
        "data_maturity",
        "security",
        "governance",
        "compliance",
        "operations",
        "infrastructure",
    }
)


class Severity(IntEnum):
    """Ordered so findings sort by importance. Names match the DB enum."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> "Severity":
        try:
            return cls[value.upper()]
        except KeyError as exc:  # pragma: no cover - guarded by validation
            raise ValueError(f"unknown severity {value!r}") from exc


@dataclass(frozen=True)
class Rule:
    """One deterministic rule (a ``rules`` row)."""

    code: str
    category: str
    severity: Severity
    condition: Mapping[str, Any]
    template: "RecommendationTemplate"
    priority: int = 100
    is_active: bool = True

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        # Validate the condition tree up front so a malformed rule fails loudly
        # at load time, never silently at evaluation time.
        validate_condition(self.condition)


@dataclass(frozen=True)
class RecommendationTemplate:
    title: str
    body: str
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class Ruleset:
    """A named, versioned collection of rules (a ``rulesets`` row + its ``rules``).

    Assessments pin a ruleset version so results are reproducible (ADR-0003).
    """

    name: str
    version: int
    rules: tuple[Rule, ...]

    @property
    def active_rules(self) -> tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.is_active)


@dataclass(frozen=True)
class Finding:
    """A deterministic result produced by the engine. The *source of truth* — the
    LLM may later wrap narrative around this but cannot change it (ADR-0003)."""

    id: str  # stable within an evaluation; here derived from the rule code
    rule_code: str
    category: str
    severity: Severity
    title: str
    detail: str


# --------------------------------------------------------------------------- #
# Loading from JSON (the ``rules``/``rulesets`` rows, or a seed file).
# --------------------------------------------------------------------------- #
def ruleset_from_dict(data: Mapping[str, Any]) -> Ruleset:
    rules: list[Rule] = []
    for r in data.get("rules", []):
        tmpl = r["recommendation_template"]
        rules.append(
            Rule(
                code=r["code"],
                category=r["category"],
                severity=Severity.parse(r["severity"]),
                condition=r["condition"],
                template=RecommendationTemplate(
                    title=tmpl["title"],
                    body=tmpl["body"],
                    references=tuple(tmpl.get("references", ())),
                ),
                priority=int(r.get("priority", 100)),
                is_active=bool(r.get("is_active", True)),
            )
        )
    return Ruleset(name=data["name"], version=int(data["version"]), rules=tuple(rules))


def facts_from_responses(responses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Flatten ``[{"key": ..., "value": ...}]`` response rows into a facts dict.

    The engine works on a flat ``key -> value`` map; this is the boundary that turns
    persisted responses into the input the pure evaluator consumes.
    """
    facts: dict[str, Any] = {}
    for r in responses:
        facts[r["key"]] = r["value"]
    return facts
