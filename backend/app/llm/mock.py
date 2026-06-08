"""Deterministic, offline LLM providers for tests, CI, and local dev.

The default :class:`MockLLMProvider` produces grounded narrative derived directly
from the finding — so it always passes the grounding check. The other two providers
exist to prove the *safety* paths actually work:

  * :class:`FabricatingLLMProvider` invents a finding code -> grounding must reject it.
  * :class:`FailingLLMProvider` raises -> the pipeline must fall back deterministically.

These let the test suite exercise the enhancement pipeline end to end without an
``OPENROUTER_API_KEY`` and without a network call (ADR-0004).
"""

from __future__ import annotations

from app.domain.grounding import Enhancement
from app.domain.rules.models import Finding

from .provider import LLMError


class MockLLMProvider:
    name = "mock"

    def enhance(self, finding: Finding) -> Enhancement:
        return Enhancement(
            finding_id=finding.id,
            rationale=(
                f"This finding was raised because the assessment responses matched "
                f"rule {finding.rule_code}. {finding.detail}"
            ),
            remediation=(
                f"Prioritise addressing '{finding.title}' given its {finding.severity.name.lower()} "
                f"severity, and re-assess once remediated."
            ),
            referenced_finding_ids=(finding.id,),
        )


class FabricatingLLMProvider:
    """Simulates a hallucinating model: cites a rule code that does not exist."""

    name = "fabricating"

    def enhance(self, finding: Finding) -> Enhancement:
        return Enhancement(
            finding_id=finding.id,
            rationale=(
                f"{finding.detail} This also relates to finding SEC-FAKE-999 which "
                f"requires immediate board attention."
            ),
            remediation="Address both findings together.",
            referenced_finding_ids=(finding.id,),
        )


class FailingLLMProvider:
    """Simulates an outage: every call raises."""

    name = "failing"

    def enhance(self, finding: Finding) -> Enhancement:
        raise LLMError("simulated upstream timeout")
