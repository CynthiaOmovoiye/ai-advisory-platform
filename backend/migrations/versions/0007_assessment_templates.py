"""add assessment templates/sections/questions + assessments.template_id (Module 3)

Revision ID: 0007_assessment_templates
Revises: 0006_llm_calls
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.infra.db import JSONType

revision: str = "0007_assessment_templates"
down_revision: str | None = "0006_llm_calls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
    )
    op.create_table(
        "assessment_sections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(),
            sa.ForeignKey("assessment_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_sections_template", "assessment_sections", ["template_id"])
    op.create_table(
        "questions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "section_id",
            sa.String(),
            sa.ForeignKey("assessment_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config", JSONType, nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_questions_section", "questions", ["section_id"])
    op.add_column("assessments", sa.Column("template_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "template_id")
    op.drop_table("questions")
    op.drop_table("assessment_sections")
    op.drop_table("assessment_templates")
