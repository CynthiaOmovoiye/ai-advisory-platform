"""add evaluation_runs table (eval dashboard)

Revision ID: 0004_evaluation_runs
Revises: 0003_recommendation_status
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_evaluation_runs"
down_revision: str | None = "0003_recommendation_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dataset_name", sa.String(), nullable=False),
        sa.Column("ruleset_name", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="completed"),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("consistency", sa.Float(), nullable=True),
        sa.Column("completeness", sa.Float(), nullable=True),
        sa.Column("hallucination_rate", sa.Float(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evaluation_runs_created", "evaluation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("evaluation_runs")
