"""Buffered writer with bulk conflict detection and content-addressed evidence.

Rows are staged per table and inserted with INSERT OR IGNORE. After each flush,
`stage EXCEPT table` lists staged rows that are not present verbatim in the
table: those are either conflicting facts (a different row already holds the
primary key) or constraint violations. Re-inserting one offending row without
OR IGNORE surfaces the exact SQLite error. Repeated identical rows are no-ops,
which is what makes imports idempotent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict

from rotom_dex.domain.conditions import validate_condition

JSON_FIELDS = {"conditions", "prerequisites", "encounter_conditions", "raw", "moves"}
CONDITION_FIELDS = {"conditions", "prerequisites", "encounter_conditions"}
FLUSH_THRESHOLD = 50_000


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _param(key, value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return canonical(value)
    if key in JSON_FIELDS and value is not None and not isinstance(value, str):
        return canonical(value)
    return value


class Writer:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._buffers: dict[str, list[dict]] = defaultdict(list)
        self._evidence_seen: set[str] = set()
        self.inserted: dict[str, int] = defaultdict(int)

    # -- rows -----------------------------------------------------------------
    def add(self, record) -> None:
        values = asdict(record)
        for key in CONDITION_FIELDS & set(values):
            if values[key] is not None:
                validate_condition(values[key])
        self.row(record.table, values)

    def row(self, table: str, values: dict) -> None:
        buffer = self._buffers[table]
        buffer.append({k: _param(k, v) for k, v in values.items()})
        if len(buffer) >= FLUSH_THRESHOLD:
            # Flush every buffer in insertion order so parents (evidence, catalogs) land first.
            self.flush()

    def flush(self, table: str | None = None) -> None:
        tables = [table] if table else list(self._buffers)
        for name in tables:
            rows = self._buffers.pop(name, [])
            if rows:
                self._flush_rows(name, rows)

    def _flush_rows(self, table: str, rows: list[dict]) -> None:
        columns = list(rows[0])
        if any(list(r) != columns for r in rows):
            raise ValueError(f"Inconsistent columns buffered for {table}")
        stage = f"_stage_{table}"
        collist = ",".join(columns)
        db = self.db
        db.execute(f"DROP TABLE IF EXISTS temp.{stage}")
        db.execute(f"CREATE TEMP TABLE {stage} AS SELECT {collist} FROM {table} WHERE 0")
        db.executemany(
            f"INSERT INTO temp.{stage} ({collist}) VALUES ({','.join('?' for _ in columns)})",
            [tuple(r[c] for c in columns) for r in rows],
        )
        before = db.total_changes
        db.execute(f"INSERT OR IGNORE INTO {table} ({collist}) SELECT {collist} FROM temp.{stage}")
        self.inserted[table] += db.total_changes - before
        offending = db.execute(f"SELECT {collist} FROM (SELECT {collist} FROM temp.{stage} EXCEPT SELECT {collist} FROM {table}) LIMIT 1").fetchone()
        if offending is not None:
            values = dict(zip(columns, tuple(offending), strict=True))
            try:
                db.execute(
                    f"INSERT INTO {table} ({collist}) VALUES ({','.join('?' for _ in columns)})",
                    tuple(offending),
                )
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc) or "PRIMARY" in str(exc):
                    raise ValueError(f"Conflicting fact in {table}: {values} ({exc})") from exc
                raise ValueError(f"Invalid row for {table}: {values} ({exc})") from exc
            raise ValueError(f"Conflicting fact in {table}: {values}")
        db.execute(f"DROP TABLE temp.{stage}")

    # -- evidence -------------------------------------------------------------
    def evidence(self, *refs: tuple[str, str]) -> str:
        """Content-addressed evidence id for a set of (source_id, selector) pairs."""
        items = sorted(set(refs))
        if not items:
            raise ValueError("Evidence needs at least one source reference")
        eid = hashlib.sha256(canonical(items).encode()).hexdigest()[:24]
        if eid not in self._evidence_seen:
            self._evidence_seen.add(eid)
            self.row("evidence", {"id": eid})
            for source, selector in items:
                self.row(
                    "evidence_members",
                    {"evidence_id": eid, "source_id": source, "selector": selector},
                )
        return eid
