"""Curated progression: milestones and trainer battles."""

from __future__ import annotations

from rotom_dex.repositories.common import NotFound, envelope, one, resolve_game, rows, unsupported


def list_milestones(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    milestones = rows(
        db,
        """SELECT m.id, m.slug, m.name, m.ord, m.kind, l.slug AS location, m.prerequisites,
                             m.spoiler_level, m.verification_status, m.evidence_id FROM milestones m
                             LEFT JOIN locations l ON l.id=m.location_id WHERE m.game_id=? ORDER BY m.ord""",
        (scope.id,),
    )
    return envelope(
        db,
        scope,
        milestones,
        features=("progression",),
        assumptions=["Milestones are curated and reference-reviewed; coverage 'partial' means the list is incomplete."],
    )


def list_battles(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    battles = rows(
        db,
        """SELECT b.id, b.name, b.trainer_class, b.milestone_id, l.slug AS location, b.prize_money,
                          b.verification_status, b.evidence_id FROM trainer_battles b
                          LEFT JOIN locations l ON l.id=b.location_id WHERE b.game_id=? ORDER BY b.id""",
        (scope.id,),
    )
    return envelope(db, scope, battles, features=("boss-teams",), include_evidence=False)


def battle_detail(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    battle = one(
        db,
        """SELECT b.id, b.name, b.trainer_class, b.milestone_id, l.slug AS location, b.prize_money,
                        b.verification_status, b.evidence_id FROM trainer_battles b
                        LEFT JOIN locations l ON l.id=b.location_id WHERE b.game_id=? AND (b.id=? OR b.id=?)""",
        (scope.id, key, f"{scope.slug}:{key}"),
    )
    if battle is None:
        raise NotFound(f"Unknown battle '{key}' for {scope.slug}")
    battle["party"] = rows(
        db,
        """SELECT tp.slot, f.slug AS pokemon, f.name, tp.level, tp.gender, a.slug AS ability,
                                  i.slug AS held_item, tp.moves, tp.verification_status, tp.evidence_id
                                  FROM trainer_party tp JOIN pokemon_forms f ON f.id=tp.form_id
                                  LEFT JOIN abilities a ON a.id=tp.ability_id LEFT JOIN items i ON i.id=tp.held_item_id
                                  WHERE tp.battle_id=? ORDER BY tp.slot""",
        (battle["id"],),
    )
    for member in battle["party"]:
        member["types"] = [
            t["slug"]
            for t in rows(
                db,
                """SELECT t.slug FROM pokemon_types pt JOIN types t ON t.id=pt.type_id
                   JOIN pokemon_forms f ON f.id=pt.form_id
                   WHERE f.slug=? AND pt.generation_id=? ORDER BY pt.slot""",
                (member["pokemon"], scope.generation_id),
            )
        ]
    return envelope(db, scope, battle, features=("boss-teams",))
