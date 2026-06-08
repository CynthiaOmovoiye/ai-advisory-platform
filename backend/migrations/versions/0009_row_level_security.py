"""enable Postgres Row-Level Security on tenant-owned tables (ADR-0006)

Revision ID: 0009_row_level_security
Revises: 0008_documents
Create Date: 2026-06-08

The independent SECOND isolation layer: even if the application-layer tenant filter
were bypassed by a bug, Postgres itself refuses to return another tenant's rows. The
app sets a transaction-local `app.current_org` per request (from the verified session);
policies compare it to each row's organization_id. A separate `app.bypass_rls` flag
permits audited cross-org reads (admin metrics, seed). FORCE makes the policy apply to
the table owner / app role too.

Postgres-only: SQLite (the test DB) has no RLS, so this migration no-ops there and the
app-layer filter remains the (still-correct) isolation in tests.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_row_level_security"
down_revision: str | None = "0008_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tenant-owned tables that carry organization_id directly.
_TABLES = [
    "assessments",
    "recommendations",
    "reports",
    "organization_members",
    "documents",
    "llm_calls",
]

_PREDICATE = (
    "organization_id = current_setting('app.current_org', true) "
    "OR current_setting('app.bypass_rls', true) = 'on'"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # RLS is a Postgres feature; no-op on SQLite (tests)
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
