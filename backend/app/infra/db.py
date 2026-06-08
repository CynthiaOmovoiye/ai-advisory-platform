"""Database engine/session plumbing (infra layer).

Kept deliberately thin and engine-creation lazy so importing this module never
requires a live database (tests construct their own SQLite engine). The declarative
``Base`` is the metadata target for both the ORM models and Alembic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import JSON, create_engine
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
