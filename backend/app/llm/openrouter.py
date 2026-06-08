"""OpenRouter implementation of :class:`LLMProvider` (ADR-0004).

This is the single egress point for all LLM traffic. It is the production
implementation of the same interface the mock providers satisfy, so the enhancement
pipeline, the grounding gate, and the eval framework are all unchanged.

What this module guarantees:

  * **Structured output** — requests JSON and parses it into a bounded
    :class:`Enhancement`. The model returns only the fields we ask for.
  * **Resilience** — timeouts, bounded retries with exponential backoff on transient
    failures, and a clean :class:`LLMError` on exhaustion so the pipeline falls back
    deterministically (an LLM outage degrades polish, never correctness — ADR-0003).
  * **Observability** — every call records latency, token usage, and **estimated
    cost** (tokens × per-model rates) to a telemetry sink, mirroring the ``llm_calls``
    table (architecture §7).

The HTTP I/O is a thin shell around pure helpers (``build_messages``,
``parse_enhancement``, ``compute_cost``, ``should_retry``) so the important logic is
unit-tested with zero network. The client is injectable, so the provider is fully
tested offline with ``httpx.MockTransport``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from app.domain.grounding import Enhancement
from app.domain.rules.models import Finding

from .provider import LLMError

# Transient HTTP statuses worth retrying. 4xx (except 429) are caller errors and are
# not retried.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

_SYSTEM_PROMPT = (
    "You are an assistant that writes clear, executive-facing explanations of "
    "security and governance findings. You are given ONE finding that a deterministic "
    "rule engine has already produced. Explain it; do NOT invent new findings, do NOT "
    "change its severity, and do NOT reference any finding other than the one given. "
    "Respond with a JSON object: "
    '{"rationale": str, "remediation": str}. No prose outside the JSON.'
)


# --------------------------------------------------------------------------- #
# Configuration & telemetry (mirror model_versions + llm_calls in db/schema.sql)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModelPricing:
    """A model as configured, with pricing for cost accounting (a model_versions row)."""

    model_id: str  # e.g. "anthropic/claude-..." routed via OpenRouter
    input_cost_per_1k: Decimal = Decimal("0")
    output_cost_per_1k: Decimal = Decimal("0")
    temperature: float = 0.2
    max_tokens: int = 1024


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.5
    referer: str = "https://github.com/your-org/ai-advisory-platform"
    title: str = "AI Advisory Platform"


@dataclass(frozen=True)
class LLMCall:
    """One LLM invocation — the observability/cost record (an llm_calls row)."""

    model_id: str
    status: str  # "success" | "timeout" | "error"
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate: Decimal | None = None
    correlation_id: str | None = None


class TelemetrySink(Protocol):
    def record(self, call: LLMCall) -> None: ...


@dataclass
class ListTelemetrySink:
    """Default in-memory sink. In production this writes to the llm_calls table."""

    calls: list[LLMCall] = field(default_factory=list)

    def record(self, call: LLMCall) -> None:
        self.calls.append(call)


# --------------------------------------------------------------------------- #
# Pure helpers — no I/O, unit-tested directly.
# --------------------------------------------------------------------------- #
def build_messages(finding: Finding) -> list[dict[str, str]]:
    user = (
        f"Finding id: {finding.id}\n"
        f"Rule: {finding.rule_code}\n"
        f"Category: {finding.category}\n"
        f"Severity: {finding.severity.name.lower()}\n"
        f"Title: {finding.title}\n"
        f"Detail: {finding.detail}\n\n"
        "Explain why this matters and how to remediate it."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def should_retry(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS


def compute_cost(usage: dict[str, Any], pricing: ModelPricing) -> Decimal:
    inp = Decimal(int(usage.get("prompt_tokens", 0)))
    out = Decimal(int(usage.get("completion_tokens", 0)))
    return (inp / Decimal(1000)) * pricing.input_cost_per_1k + (
        out / Decimal(1000)
    ) * pricing.output_cost_per_1k


def parse_enhancement(finding: Finding, content: str) -> Enhancement:
    """Parse the model's JSON content into a bounded Enhancement.

    We set ``finding_id`` ourselves (we never trust the model to identify the finding)
    and default ``referenced_finding_ids`` to the one finding in context. Whatever the
    model writes is still run through the grounding check by the pipeline.
    """
    payload = _loads_lenient(content)
    if not isinstance(payload, dict):
        raise LLMError("model did not return a JSON object")
    rationale = payload.get("rationale")
    remediation = payload.get("remediation")
    if not isinstance(rationale, str) or not isinstance(remediation, str):
        raise LLMError("model response missing 'rationale'/'remediation' strings")
    refs = payload.get("referenced_finding_ids")
    referenced = tuple(refs) if isinstance(refs, list) else (finding.id,)
    return Enhancement(
        finding_id=finding.id,
        rationale=rationale,
        remediation=remediation,
        referenced_finding_ids=referenced,
    )


def _loads_lenient(content: str) -> Any:
    content = content.strip()
    if content.startswith("```"):  # tolerate ```json fenced blocks
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model returned non-JSON content: {exc}") from exc


# --------------------------------------------------------------------------- #
# The provider — thin I/O shell over the pure helpers.
# --------------------------------------------------------------------------- #
class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        config: OpenRouterConfig,
        pricing: ModelPricing,
        *,
        client: Any | None = None,  # httpx.Client; injected in tests
        telemetry: TelemetrySink | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        correlation_id: str | None = None,
    ) -> None:
        self._config = config
        self._pricing = pricing
        self._telemetry = telemetry or ListTelemetrySink()
        self._sleeper = sleeper
        self._correlation_id = correlation_id
        self._client = client or self._build_client(config)
        # The most recent call's stats — read by the enhancement pipeline so it can
        # persist token/cost telemetry at a single point (app/llm/enhancement.py).
        self.last_call: LLMCall | None = None

    @staticmethod
    def _build_client(config: OpenRouterConfig) -> Any:
        import httpx  # lazy: pure helpers import without httpx installed

        return httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "HTTP-Referer": config.referer,
                "X-Title": config.title,
                "Content-Type": "application/json",
            },
        )

    def enhance(self, finding: Finding) -> Enhancement:
        import httpx

        body = {
            "model": self._pricing.model_id,
            "messages": build_messages(finding),
            "temperature": self._pricing.temperature,
            "max_tokens": self._pricing.max_tokens,
            "response_format": {"type": "json_object"},
        }

        start = time.perf_counter()
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._client.post("/chat/completions", json=body)
            except httpx.TimeoutException as exc:
                last_exc = exc
                self._maybe_backoff(attempt)
                continue
            except httpx.TransportError as exc:
                last_exc = exc
                self._maybe_backoff(attempt)
                continue

            if should_retry(response.status_code) and attempt < self._config.max_retries:
                self._maybe_backoff(attempt)
                continue

            if response.status_code >= 400:
                self._record(finding, start, status="error")
                raise LLMError(f"OpenRouter returned {response.status_code}")

            return self._handle_success(finding, response, start)

        # Retries exhausted on a transport/timeout error.
        status = "timeout" if isinstance(last_exc, httpx.TimeoutException) else "error"
        self._record(finding, start, status=status)
        raise LLMError(f"OpenRouter request failed after retries: {last_exc}")

    # -- internals --------------------------------------------------------- #
    def _handle_success(self, finding: Finding, response: Any, start: float) -> Enhancement:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        enhancement = parse_enhancement(finding, content)  # may raise LLMError
        self._record(
            finding,
            start,
            status="success",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cost=compute_cost(usage, self._pricing),
        )
        return enhancement

    def _maybe_backoff(self, attempt: int) -> None:
        # exponential backoff: base * 2**attempt. Sleeper injected for tests.
        self._sleeper(self._config.backoff_base_seconds * (2**attempt))

    def _record(
        self,
        finding: Finding,
        start: float,
        *,
        status: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: Decimal | None = None,
    ) -> None:
        call = LLMCall(
            model_id=self._pricing.model_id,
            status=status,
            latency_ms=int((time.perf_counter() - start) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=cost,
            correlation_id=self._correlation_id,
        )
        self.last_call = call
        self._telemetry.record(call)

    def close(self) -> None:
        self._client.close()
