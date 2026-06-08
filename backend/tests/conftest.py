"""Shared test fixtures/helpers.

Loads the seed ruleset and eval dataset from ``backend/data`` so tests exercise the
*real* shipped data, not hand-built duplicates.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.rules.models import Ruleset, ruleset_from_dict

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_baseline_ruleset() -> Ruleset:
    raw = json.loads((DATA_DIR / "rulesets" / "baseline-v1.json").read_text())
    return ruleset_from_dict(raw)


def load_baseline_dataset() -> list[dict]:
    raw = json.loads((DATA_DIR / "eval" / "baseline-readiness.json").read_text())
    return raw["items"]
