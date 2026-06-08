"""Safe condition evaluator for the rule engine.

Rules are *data* (the ``rules`` table), editable without a deployment. Their
conditions are therefore untrusted input from the rule-author surface. This module
evaluates them with a **fixed, non-Turing-complete operator set** — there is no
``eval``/``exec``, no attribute access, no name resolution. A malicious or malformed
condition can at worst fail validation or evaluate to ``False``; it can never execute
code.

See ADR-0003 (rule engine → LLM) and docs/security/threat-model.md (Tampering:
rule-condition injection).

Condition tree shape (matches ``rules.condition`` JSONB in db/schema.sql)::

    {"op": "and", "args": [ <node>, ... ]}
    {"op": "or",  "args": [ <node>, ... ]}
    {"op": "not", "arg":  <node>}
    {"op": "eq" | "ne" | "gt" | "gte" | "lt" | "lte", "key": <str>, "value": <literal>}
    {"op": "in",       "key": <str>, "value": [<literal>, ...]}  # facts[key] in value
    {"op": "contains", "key": <str>, "value": <literal>}         # value in facts[key] (lists)
    {"op": "exists",   "key": <str>}                             # key present and not None

``facts`` is a flat ``dict[str, Any]`` derived from assessment responses (response
``key`` -> typed value).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MAX_DEPTH = 32  # bound recursion; a hostile/buggy rule cannot exhaust the stack

_LOGICAL = {"and", "or", "not"}
_COMPARE = {"eq", "ne", "gt", "gte", "lt", "lte"}
_MEMBERSHIP = {"in", "contains", "exists"}
VALID_OPS = _LOGICAL | _COMPARE | _MEMBERSHIP


class InvalidCondition(ValueError):
    """Raised when a condition tree is structurally invalid. Used at *write* time
    (validating a rule before it is stored) so bad rules never reach evaluation."""


# --------------------------------------------------------------------------- #
# Validation — run when a rule is created/updated (see /rules POST in OpenAPI).
# --------------------------------------------------------------------------- #
def validate_condition(node: Any, _depth: int = 0) -> None:
    """Validate structure/arity/operators. Raises InvalidCondition on any problem."""
    if _depth > MAX_DEPTH:
        raise InvalidCondition(f"condition nested deeper than {MAX_DEPTH}")
    if not isinstance(node, Mapping):
        raise InvalidCondition(f"condition node must be an object, got {type(node).__name__}")

    op = node.get("op")
    if op not in VALID_OPS:
        raise InvalidCondition(f"unknown operator {op!r}")

    if op in {"and", "or"}:
        args = node.get("args")
        if not isinstance(args, list) or not args:
            raise InvalidCondition(f"{op!r} requires a non-empty 'args' list")
        for child in args:
            validate_condition(child, _depth + 1)
    elif op == "not":
        if "arg" not in node:
            raise InvalidCondition("'not' requires 'arg'")
        validate_condition(node["arg"], _depth + 1)
    elif op == "exists":
        _require_key(node)
    elif op == "in":
        _require_key(node)
        if not isinstance(node.get("value"), list):
            raise InvalidCondition("'in' requires a list 'value'")
    else:  # comparisons + contains
        _require_key(node)
        if "value" not in node:
            raise InvalidCondition(f"{op!r} requires 'value'")


def _require_key(node: Mapping[str, Any]) -> None:
    key = node.get("key")
    if not isinstance(key, str) or not key:
        raise InvalidCondition(f"{node.get('op')!r} requires a non-empty string 'key'")


# --------------------------------------------------------------------------- #
# Evaluation — run at assessment-completion time against the response facts.
# Lenient on data-type mismatches (returns False, does not crash an assessment);
# strict on structure (assumes the tree was validated on write).
# --------------------------------------------------------------------------- #
def evaluate_condition(node: Mapping[str, Any], facts: Mapping[str, Any], _depth: int = 0) -> bool:
    if _depth > MAX_DEPTH:
        return False
    op = node["op"]

    if op == "and":
        return all(evaluate_condition(c, facts, _depth + 1) for c in node["args"])
    if op == "or":
        return any(evaluate_condition(c, facts, _depth + 1) for c in node["args"])
    if op == "not":
        return not evaluate_condition(node["arg"], facts, _depth + 1)

    if op == "exists":
        return node["key"] in facts and facts[node["key"]] is not None

    present = node["key"] in facts
    actual = facts.get(node["key"])
    expected = node.get("value")

    if op == "eq":
        return present and actual == expected
    if op == "ne":
        # absent key is treated as "not equal" — a missing control is not the value.
        return (not present) or actual != expected
    if op in {"gt", "gte", "lt", "lte"}:
        # Inline the numeric guard (rather than a helper) so the type narrows: bool is
        # excluded because it subclasses int and we don't want True to compare as 1.
        if (
            not isinstance(actual, (int, float))
            or isinstance(actual, bool)
            or not isinstance(expected, (int, float))
            or isinstance(expected, bool)
        ):
            return False  # type mismatch -> no match, never an exception
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        return actual <= expected
    if op == "in":
        return present and isinstance(expected, (list, tuple, set, str)) and actual in expected
    if op == "contains":
        return present and _safe_contains(actual, expected)

    return False  # unreachable for validated trees


def _safe_contains(container: Any, value: Any) -> bool:
    if isinstance(container, (list, tuple, set, str)):
        return value in container
    return False
