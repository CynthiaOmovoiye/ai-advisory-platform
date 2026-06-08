"""The LLM provider interface.

All LLM access goes through this narrow interface (ADR-0004). The production
implementation wraps OpenRouter; a deterministic mock backs tests and CI so the suite
is hermetic and free. Keeping the surface this small is deliberate: it is the single
choke point for structured output, timeouts/retries, the circuit-breaker to the
deterministic fallback, input redaction, and token/cost/latency capture.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.grounding import Enhancement
from app.domain.rules.models import Finding


@runtime_checkable
class LLMProvider(Protocol):
    """Enhance a single finding into narrative fields.

    Implementations MUST return an :class:`Enhancement` whose ``finding_id`` is the
    id of the finding passed in. The enhancement is *not* trusted — the caller runs
    the grounding check on it regardless of which provider produced it.
    """

    name: str

    def enhance(self, finding: Finding) -> Enhancement: ...


class LLMError(RuntimeError):
    """Raised by a provider on timeout/transport/HTTP error. The enhancement pipeline
    catches this and falls back to the deterministic narrative."""
