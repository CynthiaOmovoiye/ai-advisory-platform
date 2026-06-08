"""add review status + edited_by to recommendations (consultant workspace)

Revision ID: 0003_recommendation_status
Revises: 0002_reports
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_recommendation_status"
down_revision: str | None = "0002_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
    )
    op.add_column("recommendations", sa.Column("edited_by", sa.String(), nullable=True))
    op.create_index("ix_recommendations_status", "recommendations", ["assessment_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_column("recommendations", "edited_by")
    op.drop_column("recommendations", "status")
