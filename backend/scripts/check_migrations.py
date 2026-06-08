"""Migration ↔ ORM drift check (CI gate).

Run AFTER ``alembic upgrade head`` against the same DATABASE_URL. Asserts that every
table the ORM declares exists in the migrated schema — catching the common, important
drift: someone added an ORM model but forgot the migration. (We deliberately don't use
``alembic check``: with hand-authored migrations it flags cosmetic index-name and
inferred-nullable differences that don't affect correctness.)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `app` importable when run directly (e.g. `python scripts/check_migrations.py`)
# without an editable install or PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

import app.repositories.orm  # noqa: F401,E402 — registers all models on Base.metadata
from app.infra.db import Base, make_engine  # noqa: E402


def main() -> int:
    url = os.environ.get("DATABASE_URL", "sqlite+pysqlite:///./_migcheck.db")
    engine = make_engine(url)
    existing = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables.keys())
    missing = expected - existing
    if missing:
        print(f"MIGRATION DRIFT: ORM tables missing from the migrated schema: {sorted(missing)}")
        print("→ add an Alembic migration for the new model(s).")
        return 1
    print(f"OK: all {len(expected)} ORM tables present in the migrated schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
