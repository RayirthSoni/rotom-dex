"""Numbered SQL migrations. Files are applied in order exactly once and recorded.

Legacy databases created by the v1 Emerald sample (`schema_version` table) are
refused: they must be rebuilt with `rotom import` into a new file.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from pathlib import Path

from rotom_dex.errors import StaleDatabase

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
PATTERN = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


def available() -> list[tuple[int, str, Path]]:
    found = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = PATTERN.match(path.name)
        if not match:
            raise ValueError(f"Bad migration file name: {path.name}")
        found.append((int(match.group(1)), match.group(2), path))
    versions = [v for v, _, _ in found]
    if versions != list(range(1, len(found) + 1)):
        raise ValueError(f"Migrations must be numbered consecutively from 0001: {versions}")
    return found


def applied(db: sqlite3.Connection) -> list[int]:
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "schema_version" in tables and "schema_migrations" not in tables:
        raise StaleDatabase("Legacy v1 sample database; rebuild it with `rotom import` into a new file")
    if "schema_migrations" not in tables:
        return []
    return [r[0] for r in db.execute("SELECT version FROM schema_migrations ORDER BY version")]


def migrate(db: sqlite3.Connection) -> list[int]:
    """Apply pending migrations. Returns the versions applied in this call."""
    done = applied(db)
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    newly = []
    for version, name, path in available():
        if version in done:
            continue
        with db:
            db.executescript(path.read_text())
            db.execute(
                "INSERT INTO schema_migrations VALUES (?,?,?)",
                (version, name, dt.datetime.now(dt.UTC).isoformat()),
            )
        newly.append(version)
    return newly


def check_current(db: sqlite3.Connection) -> None:
    """Raise if the database is behind the code's migrations (read-only callers)."""
    done = applied(db)
    expected = [v for v, _, _ in available()]
    if done != expected:
        raise StaleDatabase(f"Database schema is at {done}, code expects {expected}; run `rotom import`")
