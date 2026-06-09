"""Idempotent seed: a real local demo user, organization, and assessment.

Safe to run on every startup — it no-ops if the demo org already exists. The seeded
assessment's responses are chosen to trigger findings across several categories, so a
fresh `docker compose up` yields a clickable end-to-end demo:

    log in as demo@example.com / ChangeMe123! -> open the assessment -> Complete
    -> review/approve -> Publish report
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.infra.config import get_settings
from app.infra.db import make_engine, make_session_factory, set_rls_bypass
from app.repositories.orm import (
    Assessment,
    AssessmentSection,
    AssessmentTemplate,
    Organization,
    OrganizationMember,
    Question,
    Response,
    User,
)
from app.services.auth_service import hash_password

DEMO_ORG = "00000000-0000-4000-8000-000000000001"
DEMO_ASSESSMENT = "assess-a"
DEMO_USER = "00000000-0000-4000-8000-000000000002"
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "ChangeMe123!"  # noqa: S105 - documented local-dev seed credential

# A richer, multi-section published template so the template -> start -> answer ->
# complete -> review flow is demonstrable end to end. Question KEYS line up with the
# baseline-v1 ruleset, so completing an assessment from it fires real findings.
# (model_monitoring is deliberately omitted so OPS-OBS-005 — "fires when model_monitoring
# is absent" — triggers.)
DEMO_TEMPLATE = "tmpl-ai-readiness-demo"
DEMO_TEMPLATE_SECTIONS: list[tuple[str, list[tuple[str, str, str, dict[str, object]]]]] = [
    (
        "Security & Access",
        [
            (
                "mfa_enabled",
                "Is multi-factor authentication enforced for all users?",
                "single_select",
                {"required": True},
            ),
            (
                "sensitive_data_present",
                "Does the organization process sensitive or personal data?",
                "single_select",
                {"required": True},
            ),
        ],
    ),
    (
        "Data Maturity",
        [
            (
                "data_quality_score",
                "Rate your overall data quality (1 = poor, 5 = excellent).",
                "number",
                {"required": True, "min": 1, "max": 5},
            ),
        ],
    ),
    (
        "Governance",
        [
            (
                "ai_governance_owner",
                "Who owns AI governance and accountability?",
                "single_select",
                {"required": True, "options": ["none", "data_team", "executive_sponsor"]},
            ),
        ],
    ),
    (
        "Compliance & Privacy",
        [
            (
                "dpia_completed",
                "Has a Data Protection Impact Assessment (DPIA) been completed?",
                "single_select",
                {"required": True},
            ),
        ],
    ),
    (
        "AI Roadmap",
        [
            (
                "planned_capabilities",
                "Which AI capabilities are you planning to adopt?",
                "multi_select",
                {"options": ["rag", "agents", "automation", "analytics"]},
            ),
            ("ai_use_cases", "Briefly describe your top one or two AI use cases.", "long_text", {}),
        ],
    ),
]


def seed_demo_template(session) -> None:
    """Insert the published demo template (idempotent)."""
    if session.get(AssessmentTemplate, DEMO_TEMPLATE) is not None:
        return
    session.add(
        AssessmentTemplate(
            id=DEMO_TEMPLATE,
            category="ai_readiness",
            title="AI Readiness — Comprehensive (demo)",
            description="A multi-section readiness questionnaire wired to the baseline-v1 ruleset.",
            version=1,
            status="published",
        )
    )
    session.flush()
    for si, (title, questions) in enumerate(DEMO_TEMPLATE_SECTIONS):
        section_id = f"{DEMO_TEMPLATE}-s{si}"
        session.add(
            AssessmentSection(id=section_id, template_id=DEMO_TEMPLATE, title=title, order_index=si)
        )
        session.flush()
        for qi, (key, prompt, qtype, config) in enumerate(questions):
            session.add(
                Question(
                    id=f"{section_id}-q{qi}",
                    section_id=section_id,
                    key=key,
                    prompt=prompt,
                    type=qtype,
                    config=config,
                    order_index=qi,
                )
            )
    session.flush()


# Responses crafted to fire COMP-PII-004 (critical), SEC-MFA-001 (high),
# GOV-OWN-002 + DATA-QLT-003 (medium), OPS-OBS-005 (low), INF-VEC-006 (info).
DEMO_RESPONSES: dict[str, object] = {
    "mfa_enabled": False,
    "sensitive_data_present": True,
    "ai_governance_owner": "none",
    "data_quality_score": 2,
    "dpia_completed": False,
    "planned_capabilities": ["rag", "agents"],
}


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        set_rls_bypass(session)  # trusted seed: write across orgs (ADR-0006)
        # Flush in dependency order so the FK targets exist (Postgres enforces FKs
        # immediately; SQLite does not, which is why this matters here and not in tests).
        if session.get(User, DEMO_USER) is None:
            session.add(
                User(
                    id=DEMO_USER,
                    email=DEMO_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD),
                    name="Demo User",
                    email_verified_at=datetime.now(UTC),
                    status="active",
                )
            )
            session.flush()
        if session.get(Organization, DEMO_ORG) is None:
            session.add(
                Organization(id=DEMO_ORG, name="Demo Organization", slug="local-seed-organization")
            )
            session.flush()
        if session.get(OrganizationMember, "demo-member") is None:
            session.add(
                OrganizationMember(
                    id="demo-member",
                    organization_id=DEMO_ORG,
                    user_id=DEMO_USER,
                    invited_email=DEMO_EMAIL,
                    role="consultant",
                    status="active",
                    invited_by=DEMO_USER,
                )
            )
            session.flush()
        # Always ensure the demo template exists, even on an already-seeded database.
        seed_demo_template(session)
        if session.get(Assessment, DEMO_ASSESSMENT) is not None:
            session.commit()
            print("[seed] demo user/org/template present — assessment already seeded")
            return
        session.flush()
        session.add(
            Assessment(
                id=DEMO_ASSESSMENT,
                organization_id=DEMO_ORG,
                template_id=DEMO_TEMPLATE,  # link to the demo template so answers pre-fill
                template_name="AI Readiness — Comprehensive (demo)",
                ruleset_name="baseline",
                ruleset_version=1,
                status="in_progress",
            )
        )
        session.flush()
        for i, (key, value) in enumerate(DEMO_RESPONSES.items()):
            session.add(
                Response(
                    id=f"seed-r{i}",
                    assessment_id=DEMO_ASSESSMENT,
                    question_key=key,
                    value=value,
                )
            )
        session.commit()
        print(
            f"[seed] created local seed account {DEMO_EMAIL} / {DEMO_PASSWORD}, "
            f"{DEMO_ORG}, and assessment '{DEMO_ASSESSMENT}' with "
            f"{len(DEMO_RESPONSES)} responses"
        )


if __name__ == "__main__":
    main()
