"""Games, mechanics, coverage and issues."""

from __future__ import annotations

import sqlite3

from rotom_dex.repositories.common import (
    GameScope,
    coverage_rows,
    envelope,
    overall_status,
    resolve_game,
    rows,
)


def list_games(db: sqlite3.Connection) -> dict:
    games = rows(
        db,
        """SELECT g.id, g.slug, g.name, g.support_tier, g.is_main_series, g.note,
                        v.slug AS version_group, v.generation_id AS generation
                        FROM game_versions g JOIN version_groups v ON v.id=g.version_group_id
                        ORDER BY v.ord, g.id""",
    )
    for game in games:
        game["is_main_series"] = bool(game["is_main_series"])
        coverage = coverage_rows(db, game["id"])
        game["coverage_status"] = overall_status(coverage) if coverage else "missing"
        game["coverage_counts"] = {
            status: sum(1 for c in coverage if c["status"] == status)
            for status in ("complete", "partial", "missing", "disputed")
        }
    return envelope(
        db,
        None,
        games,
        coverage=[],
        include_evidence=False,
        assumptions=[
            "Catalog and excluded games have no imported facts; their coverage "
            "is reported as missing rather than borrowed from a similar game."
        ],
    )


def game_detail(db: sqlite3.Connection, slug: str) -> dict:
    scope = resolve_game(db, slug)
    mechanics = rows(
        db,
        """SELECT key, value, note, verification_status, evidence_id FROM game_mechanics
                            WHERE version_group_id=? ORDER BY key""",
        (scope.version_group_id,),
    )
    issues = rows(
        db,
        "SELECT id, feature, subject, kind, description, evidence_id FROM data_issues "
        "WHERE game_id=? OR game_id IS NULL ORDER BY id",
        (scope.id,),
    )
    data = {
        **scope.summary(),
        "is_main_series": scope.is_main_series,
        "note": scope.note,
        "mechanics": mechanics,
        "issues": issues,
        "regions": [
            r["slug"]
            for r in rows(
                db,
                "SELECT r.slug FROM version_group_regions vr JOIN regions r ON r.id=vr.region_id "
                "WHERE vr.version_group_id=? ORDER BY r.id",
                (scope.version_group_id,),
            )
        ],
    }
    return envelope(db, scope, data)


def issues(db: sqlite3.Connection, scope: GameScope | None) -> dict:
    if scope is None:
        found = rows(db, "SELECT * FROM data_issues ORDER BY id")
    else:
        found = rows(
            db,
            "SELECT * FROM data_issues WHERE game_id=? OR game_id IS NULL ORDER BY id",
            (scope.id,),
        )
    return envelope(db, scope, found, coverage=[], include_evidence=False)
