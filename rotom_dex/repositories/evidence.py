"""Evidence lookup."""

from __future__ import annotations

import sqlite3

from rotom_dex.repositories.common import NotFound, evidence_details, snapshot_id


def evidence_detail(db: sqlite3.Connection, evidence_id: str) -> dict:
    if db.execute("SELECT 1 FROM evidence WHERE id=?", (evidence_id,)).fetchone() is None:
        raise NotFound(f"Unknown evidence id {evidence_id}")
    return {"snapshot_id": snapshot_id(db), "data": evidence_details(db, {evidence_id})[0]}
