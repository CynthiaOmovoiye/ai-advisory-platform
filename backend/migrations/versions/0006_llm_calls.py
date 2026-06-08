"""add llm_calls telemetry table (observability)

Revision ID: 0006_llm_calls
Revises: 0005_organization_members
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_llm_calls"
down_revision: str | None = "0005_organization_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(12, 6), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_llm_calls_org", "llm_calls", ["organization_id"])
    op.create_index("ix_llm_calls_created", "llm_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("llm_calls")
