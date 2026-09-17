"""Filter vocabularies as they actually occur in one game.

Every list here is derived from the database rather than hardcoded, so a Generation III game never
offers `max-raid` as an encounter method and a Generation I game never offers `special-attack` as a
stat. The frontend's filter controls are built from this response.
"""

from __future__ import annotations

from rotom_dex.domain.conditions import SUPPORTED_OPS
from rotom_dex.repositories.common import envelope, resolve_game, rows, unsupported

AVAILABILITY_STATES = ("reachable", "locked", "unavailable", "unknown")
COVERAGE_STATUSES = ("complete", "partial", "missing", "disputed")
DAMAGE_CLASSES = ("physical", "special", "status")
ISSUE_KINDS = ("missing", "disputed", "unverified")
SPOILER_LEVELS = ("none", "hint", "full")
VERIFICATION_STATUSES = ("source-derived", "reference-reviewed")


def _column(db, sql: str, params=()) -> list[str]:
    return [r[0] for r in db.execute(sql, params) if r[0] is not None]


def vocabulary(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    gen, vg, gid = scope.generation_id, scope.version_group_id, scope.id
    data = {
        "types": rows(db, "SELECT slug, name FROM types WHERE generation_id<=? ORDER BY id", (gen,)),
        "stats": _column(db, "SELECT DISTINCT stat FROM pokemon_stats WHERE generation_id=? ORDER BY stat", (gen,)),
        "damage_classes": list(DAMAGE_CLASSES),
        "acquisition_methods": _column(db, "SELECT DISTINCT method FROM acquisitions WHERE game_id=? ORDER BY method", (gid,)),
        "learnset_methods": _column(db, "SELECT DISTINCT method FROM learnsets WHERE version_group_id=? ORDER BY method", (vg,)),
        "evolution_triggers": _column(
            db,
            """SELECT DISTINCT r.trigger FROM evolution_rules r
               JOIN evolution_applicability a ON a.rule_id=r.id AND a.version_group_id=?
               WHERE a.status='applies' ORDER BY r.trigger""",
            (vg,),
        ),
        "item_categories": _column(
            db,
            """SELECT DISTINCT i.category FROM item_game_data ig JOIN items i ON i.id=ig.item_id
               WHERE ig.version_group_id=? ORDER BY i.category""",
            (vg,),
        ),
        "item_pockets": _column(
            db,
            """SELECT DISTINCT i.pocket FROM item_game_data ig JOIN items i ON i.id=ig.item_id
               WHERE ig.version_group_id=? ORDER BY i.pocket""",
            (vg,),
        ),
        "egg_groups": _column(db, "SELECT DISTINCT egg_group FROM pokemon_egg_groups ORDER BY egg_group"),
        "machine_kinds": _column(db, "SELECT DISTINCT kind FROM machines WHERE version_group_id=? ORDER BY kind", (vg,)),
        "regions": _column(
            db,
            "SELECT r.slug FROM version_group_regions vr JOIN regions r ON r.id=vr.region_id WHERE vr.version_group_id=? ORDER BY r.id",
            (vg,),
        ),
        "condition_ops": sorted(SUPPORTED_OPS),
        "availability_states": list(AVAILABILITY_STATES),
        "coverage_statuses": list(COVERAGE_STATUSES),
        "issue_kinds": list(ISSUE_KINDS),
        "spoiler_levels": list(SPOILER_LEVELS),
        "verification_statuses": list(VERIFICATION_STATUSES),
        "mechanics": scope.mechanics,
    }
    return envelope(
        db,
        scope,
        data,
        coverage=[],
        include_evidence=False,
        assumptions=[
            "Lists are the values present in this game's own rows, so a filter offered here always has at least one match.",
            "A mechanics key that is absent is unverified for this game, which is not the same as the mechanic being absent.",
        ],
    )
