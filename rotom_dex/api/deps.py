"""Request-scoped read-only database connections and common query parameters."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Query

from rotom_dex.db.connection import connect
from rotom_dex.db.migrations import check_current
from rotom_dex.settings import DEFAULT_DB


def get_db() -> Iterator[sqlite3.Connection]:
    # One connection per request, and never shared between them. See `connect` for why the
    # same-thread guard has to be off here.
    db = connect(DEFAULT_DB, readonly=True, same_thread=False)
    try:
        check_current(db)
        yield db
    finally:
        db.close()


GameParam = Query(..., min_length=1, max_length=64, description="Exact game slug, e.g. emerald or red")
LimitParam = Query(50, ge=1, le=200)
OffsetParam = Query(0, ge=0)
QParam = Query(None, max_length=100, description="Case-insensitive substring of slug or name")
