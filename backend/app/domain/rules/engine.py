"""The rule engine: ``(facts, ruleset) -> findings``.

Pure, deterministic, no I/O. This is the backbone of the whole product (ADR-0003)
and the thing the evaluation framework regression-tests (ADR-0005). Given the same
inputs it always produces the same findings, in the same order.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .conditions import evaluate_condition
from .models import Finding, Rule, Ruleset

# Template placeholders: {snake_case_key} substituted from facts. We deliberately do
# NOT use str.format() — on an author-supplied template that would expose
# format-string attacks (e.g. "{x.__class__}"). Manual, attribute-free substitution
# only. See docs/security/threat-model.md.
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(text: str, facts: Mapping[str, Any]) -> str:
    def repl(match: "re.Match[str]") -> str:
        key = match.group(1)
        return str(facts[key]) if key in facts else match.group(0)

    return _PLACEHOLDER.sub(repl, text)


def _finding_for(rule: Rule, facts: Mapping[str, Any]) -> Finding:
    return Finding(
        id=rule.code,  # stable per (assessment, rule); the rule code is sufficient here
        rule_code=rule.code,
        category=rule.category,
        severity=rule.severity,
        title=render_template(rule.template.title, facts),
        detail=render_template(rule.template.body, facts),
    )


def evaluate(ruleset: Ruleset, facts: Mapping[str, Any]) -> list[Finding]:
    """Evaluate ``facts`` against the active rules of ``ruleset``.

    Returns findings sorted by severity (desc) then rule priority (asc, lower runs
    first) then rule code — a total, stable order so output is byte-for-byte
    reproducible across runs (which is what makes the consistency metric meaningful).
    """
    matched = [
        (rule, _finding_for(rule, facts))
        for rule in ruleset.active_rules
        if evaluate_condition(rule.condition, facts)
    ]
    matched.sort(key=lambda pair: (-int(pair[0].severity), pair[0].priority, pair[0].code))
    return [finding for _, finding in matched]
