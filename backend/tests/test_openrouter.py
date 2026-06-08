"""Tests for the OpenRouter provider (ADR-0004).

Pure helpers are tested directly. The provider is tested end-to-end with
``httpx.MockTransport`` — real client code, real retry/backoff/telemetry paths, no
network. Requires the dev deps (httpx); skipped cleanly if httpx is absent.
"""

import unittest
from decimal import Decimal

from app.domain.rules.models import Finding, Severity
from app.llm.openrouter import (
    LLMError,
    ModelPricing,
    OpenRouterConfig,
    OpenRouterProvider,
    ListTelemetrySink,
    build_messages,
    compute_cost,
    parse_enhancement,
    should_retry,
)

try:
    import httpx
    HAVE_HTTPX = True
except ImportError:  # pragma: no cover
    HAVE_HTTPX = False

FINDING = Finding(
    id="SEC-MFA-001",
    rule_code="SEC-MFA-001",
    category="security",
    severity=Severity.HIGH,
    title="Enforce MFA",
    detail="MFA is not enforced.",
)
PRICING = ModelPricing(
    model_id="anthropic/claude-test",
    input_cost_per_1k=Decimal("0.003"),
    output_cost_per_1k=Decimal("0.015"),
)


class TestPureHelpers(unittest.TestCase):
    def test_should_retry(self):
        for code in (408, 429, 500, 502, 503, 504):
            self.assertTrue(should_retry(code))
        for code in (200, 400, 401, 403, 404, 422):
            self.assertFalse(should_retry(code))

    def test_compute_cost(self):
        cost = compute_cost({"prompt_tokens": 1000, "completion_tokens": 2000}, PRICING)
        # 1k input @0.003 + 2k output @0.015 = 0.003 + 0.030 = 0.033
        self.assertEqual(cost, Decimal("0.033"))

    def test_parse_enhancement_plain_json(self):
        enh = parse_enhancement(FINDING, '{"rationale": "because X", "remediation": "do Y"}')
        self.assertEqual(enh.finding_id, "SEC-MFA-001")
        self.assertEqual(enh.rationale, "because X")

    def test_parse_enhancement_fenced_json(self):
        enh = parse_enhancement(FINDING, '```json\n{"rationale": "a", "remediation": "b"}\n```')
        self.assertEqual(enh.remediation, "b")

    def test_parse_enhancement_rejects_malformed(self):
        with self.assertRaises(LLMError):
            parse_enhancement(FINDING, "not json at all")
        with self.assertRaises(LLMError):
            parse_enhancement(FINDING, '{"rationale": 123}')  # wrong types

    def test_prompt_instructs_no_new_findings(self):
        msgs = build_messages(FINDING)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("do NOT invent new findings", msgs[0]["content"])


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed")
class TestProviderWithMockTransport(unittest.TestCase):
    def _provider(self, handler, **kw):
        client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test")
        sink = ListTelemetrySink()
        provider = OpenRouterProvider(
            OpenRouterConfig(api_key="test", max_retries=2, backoff_base_seconds=0),
            PRICING,
            client=client,
            telemetry=sink,
            sleeper=lambda _s: None,  # no real sleeping in tests
            **kw,
        )
        return provider, sink

    @staticmethod
    def _ok_response():
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"rationale": "r", "remediation": "m"}'}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
            },
        )

    def test_success_returns_enhancement_and_records_cost(self):
        provider, sink = self._provider(lambda req: self._ok_response())
        enh = provider.enhance(FINDING)
        self.assertEqual(enh.rationale, "r")
        self.assertEqual(len(sink.calls), 1)
        call = sink.calls[0]
        self.assertEqual(call.status, "success")
        self.assertEqual(call.input_tokens, 1000)
        self.assertEqual(call.cost_estimate, Decimal("0.018"))  # 0.003 + 0.015

    def test_retries_transient_then_succeeds(self):
        state = {"n": 0}

        def handler(req):
            state["n"] += 1
            if state["n"] == 1:
                return httpx.Response(429, json={"error": "rate limited"})
            return self._ok_response()

        provider, sink = self._provider(handler)
        enh = provider.enhance(FINDING)
        self.assertEqual(enh.rationale, "r")
        self.assertEqual(state["n"], 2)  # one retry

    def test_persistent_5xx_raises_llmerror(self):
        provider, sink = self._provider(lambda req: httpx.Response(503, json={"e": 1}))
        with self.assertRaises(LLMError):
            provider.enhance(FINDING)
        # the final attempt was recorded as an error
        self.assertEqual(sink.calls[-1].status, "error")

    def test_timeout_raises_llmerror(self):
        def handler(req):
            raise httpx.TimeoutException("slow", request=req)

        provider, sink = self._provider(handler)
        with self.assertRaises(LLMError):
            provider.enhance(FINDING)
        self.assertEqual(sink.calls[-1].status, "timeout")

    def test_4xx_caller_error_not_retried(self):
        state = {"n": 0}

        def handler(req):
            state["n"] += 1
            return httpx.Response(401, json={"error": "unauthorized"})

        provider, _ = self._provider(handler)
        with self.assertRaises(LLMError):
            provider.enhance(FINDING)
        self.assertEqual(state["n"], 1)  # no retries on a 401


if __name__ == "__main__":
    unittest.main()
