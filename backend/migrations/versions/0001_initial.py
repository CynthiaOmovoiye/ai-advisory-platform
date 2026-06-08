"""initial schema (ORM subset for the assessment use-case)

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-08

Creates the tables backing the `complete-assessment` flow. The canonical full schema
is db/schema.sql; this migration covers the subset the running application maps via
SQLAlchemy. JSONB on Postgres, JSON elsewhere (ADR-0008).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.infra.db import JSONType

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_name", sa.String(), nullable=False),
        sa.Column("ruleset_name", sa.String(), nullable=False),
        sa.Column("ruleset_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
    )
    op.create_index("ix_assessments_org", "assessments", ["organization_id"])
    op.create_table(
        "responses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "assessment_id",
            sa.String(),
            sa.ForeignKey("assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(), nullable=False),
        sa.Column("value", JSONType, nullable=False),
    )
    op.create_index("ix_responses_assessment", "responses", ["assessment_id"])
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.String(),
            sa.ForeignKey("assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_code", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("grounding_passed", sa.Boolean(), nullable=True),
        sa.Column("grounding_reasons", JSONType, nullable=False),
    )
    op.create_index("ix_recommendations_assessment", "recommendations", ["assessment_id"])
    op.create_index("ix_recommendations_org", "recommendations", ["organization_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_logs_org", "audit_logs", ["organization_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("recommendations")
    op.drop_table("responses")
    op.drop_table("assessments")
    op.drop_table("organizations")
