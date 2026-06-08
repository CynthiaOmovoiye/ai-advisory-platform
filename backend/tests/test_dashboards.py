"""Tests for the admin + eval dashboards (Modules 6 & 10), on SQLite.

Seeds real rows and asserts the metrics aggregation; runs the evaluation framework
through the service and asserts it persists + surfaces in metrics.
"""

import unittest

from app.infra.db import Base, make_engine, make_session_factory
from app.llm.mock import MockLLMProvider
from app.repositories.orm import (
    Assessment,
    Organization,
    RecommendationRow,
    ReportRow,
)
from app.repositories.sql import SqlEvaluationRunRepository
from app.services.evaluation_service import EvaluationService
from app.services.metrics_service import SqlMetricsRepository
from tests.conftest import load_baseline_dataset, load_baseline_ruleset

ORG = "org-a"


def _rec(rid, source, grounding, status):
    return RecommendationRow(
        id=rid,
        organization_id=ORG,
        assessment_id="a1",
        rule_code=rid,
        category="security",
        severity="HIGH",
        title="t",
        finding="f",
        rationale="r",
        remediation="m",
        source=source,
        grounding_passed=grounding,
        grounding_reasons=[],
        status=status,
    )


class TestDashboards(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        self._seed()

    def tearDown(self):
        self.session.close()

    def _seed(self):
        s = self.session
        s.add(Organization(id=ORG, name="A", slug="a"))
        s.add(
            Assessment(
                id="a1",
                organization_id=ORG,
                template_name="AI Readiness",
                ruleset_name="baseline",
                ruleset_version=1,
                status="completed",
            )
        )
        s.add(
            Assessment(
                id="a2",
                organization_id=ORG,
                template_name="AI Readiness",
                ruleset_name="baseline",
                ruleset_version=1,
                status="in_progress",
            )
        )
        s.add_all(
            [
                _rec("r1", "llm", True, "approved"),
                _rec("r2", "llm", True, "approved"),
                _rec("r3", "fallback", False, "rejected"),  # ungrounded -> fell back
            ]
        )
        s.add(
            ReportRow(
                id="rep1",
                organization_id=ORG,
                assessment_id="a1",
                title="Report",
                status="published",
                pdf_storage_key="reports/org-a/a1.pdf",
            )
        )
        s.commit()

    def test_admin_metrics_aggregate(self):
        m = SqlMetricsRepository(self.session).collect()
        self.assertEqual(m.organizations, 1)
        self.assertEqual(m.assessments_total, 2)
        self.assertEqual(m.assessments_by_status, {"completed": 1, "in_progress": 1})
        self.assertEqual(m.reports_published, 1)
        self.assertEqual(m.ai_usage["recommendations_total"], 3)
        self.assertEqual(m.ai_usage["by_source"], {"llm": 2, "fallback": 1})
        # 2 grounded out of 3 attempted
        self.assertAlmostEqual(m.ai_usage["grounding_pass_rate"], 2 / 3, places=3)

    def test_evaluation_run_persists_and_shows_in_metrics(self):
        svc = EvaluationService(
            runs=SqlEvaluationRunRepository(self.session),
            ruleset=load_baseline_ruleset(),
            llm=MockLLMProvider(),
        )
        run = svc.run(
            "baseline-readiness", load_baseline_dataset(), model_id="mock", triggered_by="admin"
        )
        self.session.commit()
        self.assertEqual(run.accuracy, 1.0)
        self.assertEqual(run.hallucination_rate, 0.0)
        self.assertEqual(run.status, "completed")

        listed = svc.list_recent()
        self.assertEqual(len(listed), 1)

        m = SqlMetricsRepository(self.session).collect()
        self.assertEqual(m.evaluation["latest_accuracy"], 1.0)
        self.assertEqual(m.evaluation["latest_status"], "completed")


if __name__ == "__main__":
    unittest.main()
