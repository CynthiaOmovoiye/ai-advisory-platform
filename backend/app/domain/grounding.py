"""The grounding check — the primary hallucination control.

The LLM may only *explain* deterministic findings; it must not invent new ones
(ADR-0003). This check verifies that an LLM enhancement is grounded in the findings
that actually exist. It is pure domain logic and runs in **two** places with the same
code (ADR-0005):

  * in production, gating every enhancement before it is surfaced;
  * in the evaluation framework, as the hallucination/grounding metric.

A failing enhancement is rejected and the system falls back to a template-rendered
deterministic narrative — so a hallucination degrades polish, never correctness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .rules.models import Finding

# Rule codes look like SEC-MFA-001 / GOV-DLP-002. If the model's prose cites a code,
# it had better be a code that is actually in the finding set — otherwise it has
# fabricated a finding.
_RULE_CODE = re.compile(r"\b[A-Z]{2,5}-[A-Z]{2,6}-\d{2,4}\b")


@dataclass(frozen=True)
class Enhancement:
    """Structured LLM output for one finding (schema-constrained — ADR-0004).

    The model returns narrative for a *specific* finding id and declares which
    findings it referenced. Free-form prose is bounded to these fields.
    """

    finding_id: str
    rationale: str
    remediation: str
    referenced_finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundingResult:
    passed: bool
    reasons: tuple[str, ...] = ()

    @property
    def failed(self) -> bool:
        return not self.passed


def check_grounding(enhancement: Enhancement, findings: Sequence[Finding]) -> GroundingResult:
    """Return whether ``enhancement`` is grounded in ``findings``.

    Fails (closed) if the enhancement:
      1. targets a finding id that does not exist;
      2. references a finding id that does not exist;
      3. cites a rule code in its prose that is not among the real findings
         (i.e. it asserts a finding that was never produced).
    """
    valid_ids = {f.id for f in findings}
    valid_codes = {f.rule_code for f in findings}
    reasons: list[str] = []

    if enhancement.finding_id not in valid_ids:
        reasons.append(f"targets unknown finding id {enhancement.finding_id!r}")

    for ref in enhancement.referenced_finding_ids:
        if ref not in valid_ids:
            reasons.append(f"references unknown finding id {ref!r}")

    cited_codes = set(_RULE_CODE.findall(f"{enhancement.rationale}\n{enhancement.remediation}"))
    for code in sorted(cited_codes - valid_codes):
        reasons.append(f"cites fabricated finding code {code!r}")

    return GroundingResult(passed=not reasons, reasons=tuple(reasons))
