"""SQLite connections with foreign keys enabled. Read paths open the file read-only."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    target = Path(path)
    if readonly:
        if not target.exists():
            raise FileNotFoundError(f"Database not found: {target}")
        db = sqlite3.connect(f"{target.resolve().as_uri()}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(str(target))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db
