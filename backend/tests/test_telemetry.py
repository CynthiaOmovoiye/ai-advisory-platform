"""Tests for llm_calls telemetry capture + aggregation (observability)."""

import unittest

from app.domain.rules import engine
from app.infra.db import Base, make_engine, make_session_factory
from app.llm.enhancement import enhance_findings
from app.llm.mock import MockLLMProvider
from app.repositories.orm import LlmCallRow
from app.repositories.sql import SqlLlmCallSink
from app.services.metrics_service import SqlMetricsRepository
from tests.conftest import load_baseline_ruleset


class _FakeSink:
    def __init__(self):
        self.calls = []

    def record(self, **kw):
        self.calls.append(kw)


class TestTelemetryCapture(unittest.TestCase):
    def setUp(self):
        self.findings = engine.evaluate(
            load_baseline_ruleset(),
            {"mfa_enabled": False, "sensitive_data_present": True, "ai_governance_owner": "none"},
        )

    def test_pipeline_records_one_call_per_finding(self):
        sink = _FakeSink()
        enhance_findings(
            self.findings,
            MockLLMProvider(),
            telemetry=sink,
            organization_id="org-a",
            assessment_id="a1",
        )
        self.assertEqual(len(sink.calls), len(self.findings))
        c = sink.calls[0]
        self.assertEqual(c["status"], "success")  # mock is grounded
        self.assertEqual(c["model_id"], "mock")
        self.assertEqual(c["organization_id"], "org-a")
        self.assertIsInstance(c["latency_ms"], int)

    def test_no_sink_is_a_noop(self):
        # Backward compatible: enhance_findings still works with no telemetry.
        recs = enhance_findings(self.findings, MockLLMProvider())
        self.assertEqual(len(recs), len(self.findings))


class TestTelemetryAggregation(unittest.TestCase):
    def test_metrics_aggregate_llm_calls(self):
        engine_ = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine_)
        session = make_session_factory(engine_)()
        sink = SqlLlmCallSink(session)
        sink.record(
            model_id="mock",
            status="success",
            latency_ms=12,
            input_tokens=None,
            output_tokens=None,
            cost_estimate=None,
            organization_id="org-a",
            assessment_id="a1",
            correlation_id=None,
        )
        sink.record(
            model_id="anthropic/x",
            status="success",
            latency_ms=20,
            input_tokens=1000,
            output_tokens=500,
            cost_estimate=0.018,
            organization_id="org-a",
            assessment_id="a1",
            correlation_id=None,
        )
        session.commit()

        self.assertEqual(session.query(LlmCallRow).count(), 2)
        m = SqlMetricsRepository(session).collect()
        self.assertEqual(m.ai_usage["llm_calls"], 2)
        self.assertEqual(m.ai_usage["total_input_tokens"], 1000)
        self.assertEqual(m.ai_usage["total_output_tokens"], 500)
        self.assertAlmostEqual(m.ai_usage["estimated_cost_usd"], 0.018, places=4)
        self.assertEqual(m.ai_usage["avg_latency_ms"], 16.0)
        session.close()


if __name__ == "__main__":
    unittest.main()
