"""Tests for the rule engine: correctness, ordering, reproducibility, and the
template-rendering safety property."""

import unittest

from app.domain.rules import engine
from app.domain.rules.models import Severity

from tests.conftest import load_baseline_ruleset


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.ruleset = load_baseline_ruleset()

    def test_full_house_produces_all_findings(self):
        facts = {
            "mfa_enabled": False,
            "sensitive_data_present": True,
            "ai_governance_owner": "none",
            "data_quality_score": 2,
            "dpia_completed": False,
            "planned_capabilities": ["rag"],
        }
        codes = [f.rule_code for f in engine.evaluate(self.ruleset, facts)]
        self.assertEqual(
            set(codes),
            {"COMP-PII-004", "SEC-MFA-001", "GOV-OWN-002", "DATA-QLT-003", "OPS-OBS-005", "INF-VEC-006"},
        )

    def test_clean_org_produces_no_findings(self):
        facts = {
            "mfa_enabled": True,
            "sensitive_data_present": True,
            "ai_governance_owner": "ciso",
            "data_quality_score": 5,
            "dpia_completed": True,
            "model_monitoring": "datadog",
            "planned_capabilities": [],
        }
        self.assertEqual(engine.evaluate(self.ruleset, facts), [])

    def test_ordering_is_severity_then_priority(self):
        facts = {
            "mfa_enabled": False,
            "sensitive_data_present": True,
            "ai_governance_owner": "none",
            "data_quality_score": 2,
            "dpia_completed": False,
            "planned_capabilities": ["rag"],
        }
        findings = engine.evaluate(self.ruleset, facts)
        # Critical first, info last; severities non-increasing.
        self.assertEqual(findings[0].rule_code, "COMP-PII-004")  # critical
        self.assertEqual(findings[0].severity, Severity.CRITICAL)
        self.assertEqual(findings[-1].rule_code, "INF-VEC-006")  # info
        sevs = [int(f.severity) for f in findings]
        self.assertEqual(sevs, sorted(sevs, reverse=True))

    def test_deterministic_reproducible(self):
        facts = {"ai_governance_owner": "none"}
        run_a = [f.rule_code for f in engine.evaluate(self.ruleset, facts)]
        run_b = [f.rule_code for f in engine.evaluate(self.ruleset, facts)]
        self.assertEqual(run_a, run_b)

    def test_template_renders_fact_placeholder(self):
        findings = engine.evaluate(self.ruleset, {"data_quality_score": 1})
        dq = next(f for f in findings if f.rule_code == "DATA-QLT-003")
        self.assertIn("1/5", dq.detail)

    def test_template_rendering_is_format_string_safe(self):
        # A fact value that looks like a format-string attack must be rendered as
        # literal text, never interpreted. (We substitute manually, not via .format.)
        from app.domain.rules.engine import render_template

        out = render_template("score is {data_quality_score}", {"data_quality_score": "{0.__class__}"})
        self.assertEqual(out, "score is {0.__class__}")


if __name__ == "__main__":
    unittest.main()
