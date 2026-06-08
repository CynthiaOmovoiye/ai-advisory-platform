"""Idempotent seed: a demo organization and a completed-ready assessment.

Safe to run on every startup — it no-ops if the demo org already exists. The seeded
assessment's responses are chosen to trigger findings across several categories, so a
fresh `docker compose up` yields a clickable end-to-end demo:

    log in (demo) -> open the assessment -> Complete -> review/approve -> Publish report

The demo login (frontend Auth.js Credentials provider) issues a token for org
`demo-org`, which is why the assessment lives there.
"""

from __future__ import annotations

from app.infra.config import get_settings
from app.infra.db import make_engine, make_session_factory, set_rls_bypass
from app.repositories.orm import Assessment, Organization, Response

DEMO_ORG = "demo-org"
DEMO_ASSESSMENT = "assess-a"

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
        if session.get(Organization, DEMO_ORG) is not None:
            print(f"[seed] {DEMO_ORG} already present — skipping")
            return

        # Flush in dependency order so the FK targets exist (Postgres enforces FKs
        # immediately; SQLite does not, which is why this matters here and not in tests).
        session.add(Organization(id=DEMO_ORG, name="Demo Organization", slug="demo-org"))
        session.flush()
        session.add(
            Assessment(
                id=DEMO_ASSESSMENT,
                organization_id=DEMO_ORG,
                template_name="AI Readiness",
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
            f"[seed] created {DEMO_ORG} + assessment '{DEMO_ASSESSMENT}' "
            f"with {len(DEMO_RESPONSES)} responses"
        )


if __name__ == "__main__":
    main()
