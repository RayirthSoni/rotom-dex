"""SQLite connections with foreign keys enabled. Read paths open the file read-only."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: str | Path, *, readonly: bool = False, same_thread: bool = True) -> sqlite3.Connection:
    """Open a connection.

    `same_thread=False` is needed by the API. FastAPI resolves a generator dependency by running its
    setup, the endpoint body and its teardown on *different* threadpool workers, so a connection
    created for one request legitimately moves between threads even though only one request ever
    uses it. sqlite3's default guard cannot tell that apart from genuine sharing, so the API opts
    out; nothing else does, and no connection is ever used by two requests at once.
    """
    target = Path(path)
    if readonly:
        if not target.exists():
            raise FileNotFoundError(f"Database not found: {target}")
        db = sqlite3.connect(f"{target.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=same_thread)
    else:
        db = sqlite3.connect(str(target), check_same_thread=same_thread)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db
