"""End-to-end demo of the rule-engine → LLM-enhancement → recommendation pipeline.

Runs entirely offline (deterministic mock provider) — no DB, no OPENROUTER_API_KEY,
no network. Shows the thesis in action: deterministic findings first, grounded
narrative second, full provenance throughout.

    PYTHONPATH=. python3 scripts/demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.rules import engine
from app.domain.rules.models import ruleset_from_dict
from app.eval import runner
from app.llm.enhancement import enhance_findings
from app.llm.mock import MockLLMProvider

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    ruleset = ruleset_from_dict(json.loads((DATA / "rulesets" / "baseline-v1.json").read_text()))

    # A partially-mature organisation's assessment responses.
    facts = {
        "mfa_enabled": False,
        "sensitive_data_present": True,
        "ai_governance_owner": "none",
        "data_quality_score": 2,
        "dpia_completed": False,
        "planned_capabilities": ["rag", "agents"],
    }

    print("=" * 78)
    print("STEP 1 — deterministic rule engine (the source of truth)")
    print("=" * 78)
    findings = engine.evaluate(ruleset, facts)
    for f in findings:
        print(f"  [{f.severity.name:8}] {f.rule_code}  {f.title}")

    print()
    print("=" * 78)
    print("STEP 2 — LLM enhancement, gated by the grounding check")
    print("=" * 78)
    recs = enhance_findings(findings, MockLLMProvider())
    top = recs[0]
    print(f"  {top.rule_code} — {top.title}  (source={top.source}, grounding_passed={top.grounding_passed})")
    print(f"    finding    : {top.finding}")
    print(f"    rationale  : {top.rationale}")
    print(f"    remediation: {top.remediation}")

    print()
    print("=" * 78)
    print("STEP 3 — evaluation run (the regression gate)")
    print("=" * 78)
    dataset = json.loads((DATA / "eval" / "baseline-readiness.json").read_text())["items"]
    result = runner.run(dataset, ruleset, MockLLMProvider())
    print(f"  accuracy           : {result.accuracy:.3f}")
    print(f"  completeness       : {result.completeness:.3f}")
    print(f"  consistency        : {result.consistency:.3f}")
    print(f"  hallucination_rate : {result.hallucination_rate:.3f}")
    print(f"  GATE PASSED        : {result.passed}")


if __name__ == "__main__":
    main()
