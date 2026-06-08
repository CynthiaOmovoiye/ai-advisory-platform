"""Report model assembly — pure, deterministic transformation of recommendations into
the structured sections of a report (Module 8 deliverables).

No I/O, no templating, no LLM here: this just organises the (already grounded)
recommendations into the report's shape. Because it's pure, the report's structure is
fully unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.rules.models import Severity
from app.llm.enhancement import Recommendation

_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]


@dataclass(frozen=True)
class ReportSection:
    key: str
    title: str
    recommendations: tuple[Recommendation, ...]


@dataclass(frozen=True)
class ReportModel:
    organization_name: str
    assessment_title: str
    severity_counts: dict[str, int]
    headline: str
    sections: tuple[ReportSection, ...]


# Which categories roll up into which report section (Module 8).
_SECTION_MAP: list[tuple[str, str, frozenset[str]]] = [
    ("risk", "Risk Analysis", frozenset({"compliance"})),
    ("security", "Security Findings", frozenset({"security"})),
    ("governance", "Governance Findings", frozenset({"governance"})),
    (
        "architecture",
        "Architecture Recommendations",
        frozenset({"infrastructure", "operations", "data_maturity", "ai_readiness"}),
    ),
]


def _sorted(recs: Sequence[Recommendation]) -> tuple[Recommendation, ...]:
    order = {s: i for i, s in enumerate(_SEVERITY_ORDER)}
    return tuple(sorted(recs, key=lambda r: (order[r.severity], r.rule_code)))


def build_report_model(
    organization_name: str,
    assessment_title: str,
    recommendations: Sequence[Recommendation],
) -> ReportModel:
    counts: dict[str, int] = {s.name.lower(): 0 for s in _SEVERITY_ORDER}
    for r in recommendations:
        counts[r.severity.name.lower()] += 1

    sections: list[ReportSection] = []
    for key, title, cats in _SECTION_MAP:
        matched = [r for r in recommendations if r.category in cats]
        if matched:
            sections.append(ReportSection(key=key, title=title, recommendations=_sorted(matched)))

    # Implementation roadmap: every recommendation, severity-ordered (highest first).
    if recommendations:
        sections.append(
            ReportSection(
                key="roadmap",
                title="Implementation Roadmap",
                recommendations=_sorted(recommendations),
            )
        )

    crit = counts["critical"]
    high = counts["high"]
    total = len(recommendations)
    if total == 0:
        headline = "No findings were identified. The organization is well positioned."
    elif crit or high:
        headline = (
            f"{total} findings identified, including {crit} critical and {high} high-severity "
            f"items requiring attention before AI adoption proceeds."
        )
    else:
        headline = f"{total} findings identified; none critical or high severity."

    return ReportModel(
        organization_name=organization_name,
        assessment_title=assessment_title,
        severity_counts=counts,
        headline=headline,
        sections=tuple(sections),
    )
