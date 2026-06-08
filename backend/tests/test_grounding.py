"""Tests for the grounding check — the hallucination control."""

import unittest

from app.domain.grounding import Enhancement, check_grounding
from app.domain.rules.models import Finding, Severity

FINDING = Finding(
    id="SEC-MFA-001",
    rule_code="SEC-MFA-001",
    category="security",
    severity=Severity.HIGH,
    title="Enforce MFA",
    detail="MFA is not enforced.",
)


class TestGrounding(unittest.TestCase):
    def test_grounded_enhancement_passes(self):
        enh = Enhancement(
            finding_id="SEC-MFA-001",
            rationale="Rule SEC-MFA-001 matched because MFA is off.",
            remediation="Enable MFA.",
            referenced_finding_ids=("SEC-MFA-001",),
        )
        self.assertTrue(check_grounding(enh, [FINDING]).passed)

    def test_unknown_target_id_fails(self):
        enh = Enhancement(finding_id="NOPE-000", rationale="x", remediation="y")
        result = check_grounding(enh, [FINDING])
        self.assertTrue(result.failed)
        self.assertTrue(any("unknown finding id" in r for r in result.reasons))

    def test_unknown_referenced_id_fails(self):
        enh = Enhancement(
            finding_id="SEC-MFA-001",
            rationale="x",
            remediation="y",
            referenced_finding_ids=("SEC-MFA-001", "GHOST-123"),
        )
        self.assertTrue(check_grounding(enh, [FINDING]).failed)

    def test_fabricated_rule_code_in_prose_fails(self):
        # The model invents a finding that was never produced.
        enh = Enhancement(
            finding_id="SEC-MFA-001",
            rationale="This also relates to SEC-FAKE-999 which is urgent.",
            remediation="Fix both.",
            referenced_finding_ids=("SEC-MFA-001",),
        )
        result = check_grounding(enh, [FINDING])
        self.assertTrue(result.failed)
        self.assertTrue(any("fabricated" in r for r in result.reasons))


if __name__ == "__main__":
    unittest.main()
