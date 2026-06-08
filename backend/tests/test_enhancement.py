"""Tests for the enhancement pipeline — proves the three outcome paths and the core
invariant: every finding yields a recommendation regardless of LLM behaviour."""

import unittest

from app.domain.rules import engine
from app.llm.enhancement import enhance_findings
from app.llm.mock import FabricatingLLMProvider, FailingLLMProvider, MockLLMProvider
from tests.conftest import load_baseline_ruleset


class TestEnhancement(unittest.TestCase):
    def setUp(self):
        self.findings = engine.evaluate(
            load_baseline_ruleset(),
            {"mfa_enabled": False, "sensitive_data_present": True, "ai_governance_owner": "none"},
        )
        self.assertTrue(self.findings, "fixture should produce findings")

    def test_grounded_provider_yields_llm_source(self):
        recs = enhance_findings(self.findings, MockLLMProvider())
        self.assertEqual(len(recs), len(self.findings))
        self.assertTrue(all(r.source == "llm" for r in recs))
        self.assertTrue(all(r.grounding_passed is True for r in recs))

    def test_hallucinating_provider_is_rejected_and_falls_back(self):
        recs = enhance_findings(self.findings, FabricatingLLMProvider())
        self.assertTrue(all(r.source == "fallback" for r in recs))
        self.assertTrue(all(r.grounding_passed is False for r in recs))
        # Fallback narrative is deterministic and never contains the fabricated code.
        self.assertTrue(all("SEC-FAKE-999" not in r.rationale for r in recs))

    def test_provider_outage_falls_back_without_calling_grounding(self):
        recs = enhance_findings(self.findings, FailingLLMProvider())
        self.assertTrue(all(r.source == "fallback" for r in recs))
        self.assertTrue(all(r.grounding_passed is None for r in recs))

    def test_every_finding_always_yields_a_recommendation(self):
        for provider in (MockLLMProvider(), FabricatingLLMProvider(), FailingLLMProvider()):
            recs = enhance_findings(self.findings, provider)
            self.assertEqual(
                {r.finding_id for r in recs},
                {f.id for f in self.findings},
                f"{provider.name} dropped a finding",
            )
            # The deterministic finding text is always preserved (source of truth).
            self.assertTrue(all(r.finding for r in recs))


if __name__ == "__main__":
    unittest.main()
