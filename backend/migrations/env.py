"""Alembic environment.

The DB URL is taken from ``DATABASE_URL`` (12-factor; never committed). Target
metadata is the ORM ``Base`` — importing ``app.repositories.orm`` registers all models
so autogenerate and migrations see them.

Note: db/schema.sql remains the *canonical* schema; these migrations cover the ORM
subset used by the running application. A CI check (documented in the deployment
guide) diffs the migration head against schema.sql.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.repositories.orm  # noqa: F401  (registers models on Base.metadata)
from app.infra.db import Base

config = context.config

_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
