"""Tests for the safe condition evaluator — the security-critical core.

These assert both correctness (every operator) and safety (structurally invalid or
hostile conditions are rejected at validation, never executed).
"""

import unittest

from app.domain.rules.conditions import (
    InvalidCondition,
    evaluate_condition,
    validate_condition,
)


class TestValidation(unittest.TestCase):
    def test_rejects_unknown_operator(self):
        with self.assertRaises(InvalidCondition):
            validate_condition({"op": "system", "key": "x", "value": 1})

    def test_rejects_eval_like_payload(self):
        # There is no operator that executes code; an "exec"/"eval" op is just unknown.
        for payload in ({"op": "eval", "value": "__import__('os')"}, {"op": "exec"}):
            with self.assertRaises(InvalidCondition):
                validate_condition(payload)

    def test_rejects_bad_arity(self):
        with self.assertRaises(InvalidCondition):
            validate_condition({"op": "and", "args": []})
        with self.assertRaises(InvalidCondition):
            validate_condition({"op": "not"})
        with self.assertRaises(InvalidCondition):
            validate_condition({"op": "eq", "key": "x"})  # missing value

    def test_rejects_non_object_node(self):
        with self.assertRaises(InvalidCondition):
            validate_condition("mfa_enabled == false")

    def test_depth_bound(self):
        node = {"op": "exists", "key": "x"}
        for _ in range(40):
            node = {"op": "not", "arg": node}
        with self.assertRaises(InvalidCondition):
            validate_condition(node)

    def test_accepts_well_formed(self):
        validate_condition(
            {
                "op": "and",
                "args": [
                    {"op": "eq", "key": "mfa_enabled", "value": False},
                    {"op": "in", "key": "tier", "value": ["a", "b"]},
                ],
            }
        )


class TestEvaluation(unittest.TestCase):
    def test_logical_ops(self):
        facts = {"a": True, "b": False}
        self.assertTrue(evaluate_condition({"op": "eq", "key": "a", "value": True}, facts))
        self.assertTrue(
            evaluate_condition(
                {"op": "or", "args": [
                    {"op": "eq", "key": "b", "value": True},
                    {"op": "eq", "key": "a", "value": True},
                ]},
                facts,
            )
        )
        self.assertTrue(evaluate_condition({"op": "not", "arg": {"op": "eq", "key": "b", "value": True}}, facts))

    def test_numeric_comparisons(self):
        facts = {"score": 2}
        self.assertTrue(evaluate_condition({"op": "lt", "key": "score", "value": 3}, facts))
        self.assertFalse(evaluate_condition({"op": "gte", "key": "score", "value": 3}, facts))

    def test_bool_is_not_a_number(self):
        # True must not be treated as 1 in ordering comparisons.
        self.assertFalse(evaluate_condition({"op": "gt", "key": "flag", "value": 0}, {"flag": True}))

    def test_type_mismatch_returns_false_not_error(self):
        # "high" > 3 must not raise — a bad data type just doesn't match.
        self.assertFalse(evaluate_condition({"op": "gt", "key": "x", "value": 3}, {"x": "high"}))

    def test_membership(self):
        self.assertTrue(evaluate_condition({"op": "in", "key": "t", "value": ["a", "b"]}, {"t": "a"}))
        self.assertTrue(evaluate_condition({"op": "contains", "key": "caps", "value": "rag"}, {"caps": ["rag", "agents"]}))
        self.assertFalse(evaluate_condition({"op": "contains", "key": "caps", "value": "rag"}, {"caps": 5}))

    def test_exists(self):
        self.assertTrue(evaluate_condition({"op": "exists", "key": "k"}, {"k": "v"}))
        self.assertFalse(evaluate_condition({"op": "exists", "key": "k"}, {"k": None}))
        self.assertFalse(evaluate_condition({"op": "exists", "key": "k"}, {}))

    def test_missing_key_eq_is_false_ne_is_true(self):
        self.assertFalse(evaluate_condition({"op": "eq", "key": "missing", "value": 1}, {}))
        self.assertTrue(evaluate_condition({"op": "ne", "key": "missing", "value": 1}, {}))


if __name__ == "__main__":
    unittest.main()
