"""Tests for the evaluation framework — the regression gate (ADR-0005)."""

import unittest

from app.eval import metrics, runner
from app.llm.mock import FabricatingLLMProvider, MockLLMProvider

from tests.conftest import load_baseline_dataset, load_baseline_ruleset


class TestMetrics(unittest.TestCase):
    def test_accuracy_exact_match(self):
        self.assertEqual(metrics.accuracy(["A", "B"], ["B", "A"]), 1.0)

    def test_accuracy_penalises_extras_and_misses(self):
        self.assertEqual(metrics.accuracy(["A", "B"], ["A"]), 0.5)  # one spurious extra
        self.assertEqual(metrics.accuracy(["A"], ["A", "B"]), 0.5)  # one miss

    def test_empty_matches_empty(self):
        self.assertEqual(metrics.accuracy([], []), 1.0)
        self.assertEqual(metrics.completeness([], []), 1.0)

    def test_consistency(self):
        self.assertEqual(metrics.consistency([["A", "B"], ["A", "B"]]), 1.0)
        self.assertEqual(metrics.consistency([["A", "B"], ["B", "A"]]), 0.0)


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.ruleset = load_baseline_ruleset()
        self.dataset = load_baseline_dataset()

    def test_clean_run_passes_the_gate(self):
        result = runner.run(self.dataset, self.ruleset, MockLLMProvider())
        self.assertEqual(result.accuracy, 1.0)          # engine reproduces gold findings
        self.assertEqual(result.hallucination_rate, 0.0)  # nothing ungrounded slipped through
        self.assertEqual(result.consistency, 1.0)        # deterministic
        self.assertTrue(result.passed)

    def test_hallucinating_model_fails_the_gate(self):
        result = runner.run(self.dataset, self.ruleset, FabricatingLLMProvider())
        # Accuracy (rule engine) is still perfect, but grounding rejects the prose,
        # so the hallucination rate is non-zero and the gate fails.
        self.assertEqual(result.accuracy, 1.0)
        self.assertGreater(result.hallucination_rate, 0.0)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
