"""Database engine/session plumbing (infra layer).

Kept deliberately thin and engine-creation lazy so importing this module never
requires a live database (tests construct their own SQLite engine). The declarative
``Base`` is the metadata target for both the ORM models and Alembic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import JSON, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# JSONB on Postgres (db/schema.sql, ADR-0008); plain JSON on SQLite so the same ORM
# runs in tests without Postgres.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def make_engine(url: str, **kw: Any):
    return create_engine(url, future=True, **kw)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transaction boundary helper: commit on success, rollback on error, always close."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Row-Level Security helpers (ADR-0006). On Postgres these set transaction-local
# variables the RLS policies read; on SQLite (tests) they are no-ops, so the
# app-layer tenant filter remains the sole (still-correct) isolation in tests.
# --------------------------------------------------------------------------- #
def _is_postgres(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def set_tenant_scope(session: Session, organization_id: str) -> None:
    """Scope all RLS-protected queries in this transaction to one organization."""
    if _is_postgres(session):
        session.execute(
            text("SELECT set_config('app.current_org', :o, true)"), {"o": organization_id}
        )


def set_rls_bypass(session: Session) -> None:
    """Allow cross-org access for a trusted, audited operation (admin metrics, seed,
    migrations). Transaction-local — never leaks beyond the current request."""
    if _is_postgres(session):
        session.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
