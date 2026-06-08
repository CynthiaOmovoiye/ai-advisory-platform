"""create a non-superuser app_role so RLS actually applies (ADR-0006)

Revision ID: 0010_app_role
Revises: 0009_row_level_security
Create Date: 2026-06-08

Superusers (and table owners, without FORCE) bypass RLS. The application therefore
connects as this dedicated, least-privilege role: it has DML on the app tables but no
DDL and no superuser, so the RLS policies from 0009 are enforced against it.

Postgres-only; no-op on SQLite (tests).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_app_role"
down_revision: str | None = "0009_row_level_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Dev password; in production this comes from a secrets manager and the role is created
# out-of-band. Must match APP_DATABASE_URL.
_APP_ROLE_PASSWORD = "app_role_pw"  # noqa: S105 - local-dev placeholder


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_role') THEN
            CREATE ROLE app_role LOGIN PASSWORD '{_APP_ROLE_PASSWORD}';
          END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO app_role")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role")
    # Future tables created by the owner are auto-granted to the app role.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_role"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_role"
    )
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_role")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_role")
    # Role left in place (other databases/objects may depend on it).
