"""The enhancement pipeline: findings -> recommendations.

This is where the thesis (ADR-0003) is operationalised. For each deterministic
finding we ask the LLM for narrative, then **gate it on the grounding check**
(ADR-0005). The LLM never gets to change a finding; it only gets to attach prose that
survives grounding. Three outcomes per finding, all of which yield a valid
recommendation:

  * grounded enhancement      -> source="llm",      grounding_passed=True
  * ungrounded enhancement     -> source="fallback", grounding_passed=False  (rejected)
  * provider error/timeout     -> source="fallback", grounding_passed=None   (never called)

So an LLM that is down, slow, or hallucinating degrades *polish*, never correctness —
every finding still produces a complete recommendation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.grounding import check_grounding
from app.domain.rules.models import Finding, Severity

from .provider import LLMError, LLMProvider


@dataclass(frozen=True)
class Recommendation:
    """A finding plus (optionally LLM-enhanced) narrative and full provenance.

    Mirrors the ``recommendations`` row in db/schema.sql, including the audit/
    governance fields that let any recommendation be traced and reproduced.
    """

    finding_id: str
    rule_code: str
    category: str
    severity: Severity
    title: str
    finding: str  # deterministic — the source of truth
    rationale: str
    remediation: str
    source: Literal["llm", "fallback"]
    grounding_passed: bool | None
    grounding_reasons: tuple[str, ...] = ()
    # Consultant-workspace lifecycle (db/schema.sql: recommendations.status). New
    # recommendations are 'draft'; a consultant edits/approves/rejects them, and only
    # 'approved' ones reach a published report (the approval gate).
    status: str = "draft"
    id: str | None = None  # set when loaded from persistence (assessment:rule_code)
    edited_by: str | None = None


def _deterministic_narrative(finding: Finding) -> tuple[str, str]:
    """Template-rendered fallback narrative, used whenever the LLM can't be trusted
    or reached. Plain, correct, and never hallucinated."""
    rationale = f"Identified by rule {finding.rule_code}: {finding.detail}"
    remediation = (
        f"Address '{finding.title}' (severity: {finding.severity.name.lower()}). "
        f"See the referenced guidance and re-assess after remediation."
    )
    return rationale, remediation


def enhance_findings(findings: Sequence[Finding], provider: LLMProvider) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for finding in findings:
        recommendations.append(_enhance_one(finding, provider))
    return recommendations


def _enhance_one(finding: Finding, provider: LLMProvider) -> Recommendation:
    # 1) Try the LLM.
    try:
        enhancement = provider.enhance(finding)
    except LLMError:
        rationale, remediation = _deterministic_narrative(finding)
        return _rec(finding, rationale, remediation, source="fallback", passed=None)

    # 2) Gate on grounding — same check used by the eval framework.
    result = check_grounding(enhancement, [finding])
    if result.passed:
        return _rec(
            finding,
            enhancement.rationale,
            enhancement.remediation,
            source="llm",
            passed=True,
        )

    # 3) Ungrounded -> reject the LLM output, fall back deterministically.
    rationale, remediation = _deterministic_narrative(finding)
    return _rec(
        finding,
        rationale,
        remediation,
        source="fallback",
        passed=False,
        reasons=result.reasons,
    )


def _rec(
    finding: Finding,
    rationale: str,
    remediation: str,
    *,
    source: Literal["llm", "fallback"],
    passed: bool | None,
    reasons: tuple[str, ...] = (),
) -> Recommendation:
    return Recommendation(
        finding_id=finding.id,
        rule_code=finding.rule_code,
        category=finding.category,
        severity=finding.severity,
        title=finding.title,
        finding=finding.detail,
        rationale=rationale,
        remediation=remediation,
        source=source,
        grounding_passed=passed,
        grounding_reasons=reasons,
    )
