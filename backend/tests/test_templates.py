"""Tests for assessment-template authoring + create-from-template (Module 3), on SQLite."""

import unittest

from app.domain.access import Principal, Role
from app.errors import Conflict, Forbidden, NotFound
from app.infra.db import Base, make_engine, make_session_factory
from app.llm.mock import MockLLMProvider
from app.repositories.orm import Organization
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlRecommendationRepository,
    SqlTemplateRepository,
)
from app.services.assessment_service import AssessmentService
from app.services.template_service import TemplateService
from tests.conftest import load_baseline_ruleset

ORG = "org-a"
consultant = Principal(user_id="c1", global_roles=frozenset({Role.CONSULTANT}))
org_user = Principal(user_id="u1", org_roles={ORG: frozenset({Role.ORG_USER})})

TEMPLATE_PAYLOAD = dict(
    category="ai_readiness",
    title="AI Readiness v2",
    description="Demo",
    sections=[
        {
            "title": "Security",
            "questions": [
                {
                    "key": "mfa_enabled",
                    "prompt": "Is MFA enabled?",
                    "type": "single_select",
                    "config": {"options": [True, False]},
                },
                {
                    "key": "sensitive_data_present",
                    "prompt": "Sensitive data?",
                    "type": "single_select",
                    "config": {},
                },
            ],
        }
    ],
)


class TestTemplates(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        self.session.add(Organization(id=ORG, name="A", slug="a"))
        self.session.commit()
        self.templates = TemplateService(templates=SqlTemplateRepository(self.session))
        self.assessments = AssessmentService(
            assessments=SqlAssessmentRepository(self.session),
            recommendations=SqlRecommendationRepository(self.session),
            audit=SqlAuditSink(self.session),
            ruleset=load_baseline_ruleset(),
            llm=MockLLMProvider(),
            templates=SqlTemplateRepository(self.session),
        )

    def tearDown(self):
        self.session.close()

    def test_create_template_with_sections_and_questions(self):
        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        self.assertEqual(t.status, "draft")
        self.assertEqual(len(t.sections), 1)
        self.assertEqual(len(t.sections[0].questions), 2)
        self.assertEqual(t.sections[0].questions[0].key, "mfa_enabled")
        # round-trips via the repository
        fetched = self.templates.get_template(consultant, ORG, t.id)
        self.assertEqual(fetched.title, "AI Readiness v2")

    def test_org_user_cannot_author(self):
        with self.assertRaises(Forbidden):
            self.templates.create_template(org_user, ORG, **TEMPLATE_PAYLOAD)

    def test_unknown_question_type_rejected(self):
        bad = {
            **TEMPLATE_PAYLOAD,
            "sections": [
                {
                    "title": "x",
                    "questions": [{"key": "k", "prompt": "p", "type": "rating", "config": {}}],
                }
            ],
        }
        with self.assertRaises(Conflict):
            self.templates.create_template(consultant, ORG, **bad)

    def test_cannot_start_assessment_from_unpublished_template(self):
        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        with self.assertRaises(Conflict):
            self.assessments.create_from_template(consultant, ORG, t.id)

    def test_full_authoring_to_findings_flow(self):
        # author -> publish -> start assessment -> save responses -> complete -> findings
        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        self.templates.publish_template(consultant, ORG, t.id)
        a = self.assessments.create_from_template(consultant, ORG, t.id)
        self.assertEqual(a.template_id, t.id)
        self.assessments.save_responses(
            consultant,
            ORG,
            a.id,
            [
                {"key": "mfa_enabled", "value": False},
                {"key": "sensitive_data_present", "value": True},
            ],
        )
        recs = self.assessments.complete(consultant, ORG, a.id)
        codes = {r.rule_code for r in recs}
        self.assertIn("SEC-MFA-001", codes)  # the saved responses drove the rule engine

    def test_create_from_unknown_template_not_found(self):
        with self.assertRaises(NotFound):
            self.assessments.create_from_template(consultant, ORG, "nope")

    def test_list_and_get_assessment_with_template(self):
        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        self.templates.publish_template(consultant, ORG, t.id)
        a = self.assessments.create_from_template(consultant, ORG, t.id)
        listed = self.assessments.list_assessments(consultant, ORG)
        self.assertIn(a.id, [x.id for x in listed])
        got = self.assessments.get_assessment(consultant, ORG, a.id)
        self.assertEqual(got.template_id, t.id)

    def test_get_unknown_assessment_not_found(self):
        with self.assertRaises(NotFound):
            self.assessments.get_assessment(consultant, ORG, "nope")

    def test_save_responses_rejects_unknown_key(self):
        from app.errors import Unprocessable

        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        self.templates.publish_template(consultant, ORG, t.id)
        a = self.assessments.create_from_template(consultant, ORG, t.id)
        # a key the template never asked for must be rejected (422)
        with self.assertRaises(Unprocessable):
            self.assessments.save_responses(
                consultant, ORG, a.id, [{"key": "totally_made_up", "value": True}]
            )

    def test_save_responses_accepts_template_keys(self):
        t = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        self.templates.publish_template(consultant, ORG, t.id)
        a = self.assessments.create_from_template(consultant, ORG, t.id)
        self.assessments.save_responses(
            consultant, ORG, a.id, [{"key": "mfa_enabled", "value": False}]
        )  # no error

    def test_draft_templates_hidden_from_ordinary_readers(self):
        # consultant authors a draft + a published template
        draft = self.templates.create_template(consultant, ORG, **TEMPLATE_PAYLOAD)
        pub = self.templates.create_template(
            consultant, ORG, **{**TEMPLATE_PAYLOAD, "title": "Published One"}
        )
        self.templates.publish_template(consultant, ORG, pub.id)

        # an org_user (ASSESSMENT_READ, no TEMPLATE_MANAGE) sees only the published one
        seen = self.templates.list_templates(org_user, ORG)
        seen_ids = {t.id for t in seen}
        self.assertIn(pub.id, seen_ids)
        self.assertNotIn(draft.id, seen_ids)
        # and cannot fetch the draft directly (404, not a leak)
        with self.assertRaises(NotFound):
            self.templates.get_template(org_user, ORG, draft.id)
        # the author still sees it
        self.assertIn(draft.id, {t.id for t in self.templates.list_templates(consultant, ORG)})


if __name__ == "__main__":
    unittest.main()
