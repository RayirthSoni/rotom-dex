"""Shared read-side helpers: game scope resolution, row decoding, envelopes, evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from rotom_dex.errors import NotFound

JSON_FIELDS = ("conditions", "prerequisites", "encounter_conditions", "raw", "moves")
ASSUMPTION_SOURCE = "Facts are derived from the pinned source snapshot and reviewed packs; 'complete' coverage is relative to that source, not independent game testing."


@dataclass
class GameScope:
    id: int
    slug: str
    name: str
    version_group_id: int
    version_group: str
    generation_id: int
    support_tier: str
    is_main_series: bool
    note: str
    mechanics: dict[str, int] = field(default_factory=dict)
    in_database: bool = False

    @property
    def importable(self) -> bool:
        return self.support_tier in ("validated", "imported")

    @property
    def imported(self) -> bool:
        """Facts for this game exist in the open database."""
        return self.importable and self.in_database

    def summary(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "version_group": self.version_group,
            "generation": self.generation_id,
            "support_tier": self.support_tier,
        }


def rows(db: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    result = [dict(r) for r in db.execute(sql, params)]
    for row in result:
        for key in JSON_FIELDS:
            if key in row and isinstance(row[key], str):
                row[key] = json.loads(row[key])
    return result


def one(db: sqlite3.Connection, sql: str, params=()) -> dict | None:
    found = rows(db, sql, params)
    return found[0] if found else None


def snapshot_id(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT id FROM snapshots").fetchone()
    if row is None:
        raise NotFound("Database has no published snapshot; run `rotom import` first")
    return row[0]


def known_games(db: sqlite3.Connection) -> list[str]:
    return [r[0] for r in db.execute("SELECT slug FROM game_versions ORDER BY id")]


def resolve_game(db: sqlite3.Connection, slug: str) -> GameScope:
    row = one(
        db,
        """SELECT g.id, g.slug, g.name, g.version_group_id, v.slug AS version_group,
                     v.generation_id, g.support_tier, g.is_main_series, g.note
                     FROM game_versions g JOIN version_groups v ON v.id=g.version_group_id
                     WHERE g.slug=?""",
        (slug.lower(),),
    )
    if row is None:
        raise NotFound(f"Unknown game '{slug}'. Known games: {', '.join(known_games(db))}")
    scope = GameScope(**{**row, "is_main_series": bool(row["is_main_series"])})
    scope.mechanics = {
        r["key"]: r["value"]
        for r in rows(
            db,
            "SELECT key, value FROM game_mechanics WHERE version_group_id=?",
            (scope.version_group_id,),
        )
    }
    scope.in_database = db.execute("SELECT 1 FROM coverage WHERE game_id=? LIMIT 1", (scope.id,)).fetchone() is not None
    return scope


def coverage_rows(db: sqlite3.Connection, game_id: int, features: tuple[str, ...] | None = None) -> list[dict]:
    sql = "SELECT feature, subject, status, note, evidence_id FROM coverage WHERE game_id=?"
    params: list = [game_id]
    if features:
        sql += f" AND feature IN ({','.join('?' for _ in features)})"
        params.extend(features)
    return rows(db, sql + " ORDER BY feature, subject", params)


def overall_status(coverage: list[dict]) -> str:
    statuses = {c["status"] for c in coverage}
    if not statuses:
        return "missing"
    if "disputed" in statuses:
        return "disputed"
    if statuses == {"complete"}:
        return "complete"
    if statuses == {"missing"}:
        return "missing"
    return "partial"


def collect_evidence_ids(value) -> set[str]:
    ids: set[str] = set()

    def walk(v):
        if isinstance(v, dict):
            for k, item in v.items():
                if k.endswith("evidence_id") and isinstance(item, str):
                    ids.add(item)
                else:
                    walk(item)
        elif isinstance(v, list):
            for item in v:
                walk(item)

    walk(value)
    return ids


def evidence_details(db: sqlite3.Connection, ids: set[str]) -> list[dict]:
    out = []
    for eid in sorted(ids):
        out.append(
            {
                "id": eid,
                "sources": rows(
                    db,
                    """SELECT s.id AS source_id, s.kind, s.url, s.retrieved_at, s.sha256, s.license,
                   s.review_status, em.selector FROM evidence_members em JOIN sources s ON s.id=em.source_id
                   WHERE em.evidence_id=? ORDER BY s.id, em.selector""",
                    (eid,),
                ),
            }
        )
    return out


def envelope(
    db: sqlite3.Connection,
    scope: GameScope | None,
    data,
    *,
    features=None,
    assumptions: list[str] | None = None,
    pagination: dict | None = None,
    coverage: list[dict] | None = None,
    include_evidence: bool = True,
) -> dict:
    coverage = coverage if coverage is not None else (coverage_rows(db, scope.id, features) if scope else [])
    result = {
        "game": scope.summary() if scope else None,
        "snapshot_id": snapshot_id(db),
        "coverage_status": overall_status(coverage) if data is not None else "missing",
        "coverage": coverage,
        "data": data,
        "assumptions": list(assumptions or []) + [ASSUMPTION_SOURCE],
        "evidence": [],
    }
    if pagination is not None:
        result["pagination"] = pagination
    if include_evidence and data is not None:
        result["evidence"] = evidence_details(db, collect_evidence_ids(data))
    return result


def unsupported(db: sqlite3.Connection, scope: GameScope) -> dict:
    """Envelope for games whose facts are not in this database (by policy or by selection)."""
    if scope.importable:
        reason = f"'{scope.slug}' is importable but was not imported into this database; run `rotom import --games {scope.slug}`."
    else:
        reason = f"'{scope.slug}' is {scope.support_tier}: {scope.note or 'no facts imported.'}"
    return envelope(db, scope, None, assumptions=[reason + " No facts from another game are substituted."])


def paging(limit: int, offset: int, total: int) -> dict:
    return {"limit": limit, "offset": offset, "total": total}


def like(q: str | None) -> str:
    return f"%{(q or '').strip().lower()}%"
