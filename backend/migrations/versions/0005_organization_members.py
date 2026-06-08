"""add organization_members table (Module 2)

Revision ID: 0005_organization_members
Revises: 0004_evaluation_runs
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_organization_members"
down_revision: str | None = "0004_evaluation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("invited_email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="org_user"),
        sa.Column("status", sa.String(), nullable=False, server_default="invited"),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("invite_token_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "invited_email", name="uq_member_org_email"),
    )
    op.create_index("ix_org_members_org", "organization_members", ["organization_id"])


def downgrade() -> None:
    op.drop_table("organization_members")
