"""add reports table

Revision ID: 0002_reports
Revises: 0001_initial
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_reports"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", sa.String(), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("pdf_storage_key", sa.String(), nullable=True),
    )
    op.create_index("ix_reports_org", "reports", ["organization_id"])
    op.create_index("ix_reports_assessment", "reports", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("reports")
