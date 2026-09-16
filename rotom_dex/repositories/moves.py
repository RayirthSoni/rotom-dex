"""Move search and detail for an exact game (version-group scoped values)."""

from __future__ import annotations

import sqlite3

from rotom_dex.repositories.common import (
    NotFound,
    envelope,
    like,
    one,
    paging,
    resolve_game,
    rows,
    unsupported,
)


def resolve_move(db: sqlite3.Connection, key: str) -> dict:
    move = one(db, "SELECT * FROM moves WHERE slug=? OR CAST(id AS TEXT)=?", (key.lower(), key))
    if move is None:
        raise NotFound(f"Unknown move '{key}'")
    return move


def search_moves(
    db,
    game: str,
    q: str | None,
    type_slug: str | None,
    damage_class: str | None,
    limit: int,
    offset: int,
) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    where = ["mg.version_group_id=?"]
    params: list = [scope.version_group_id]
    if q:
        where.append("(m.slug LIKE ? OR lower(m.name) LIKE ?)")
        params += [like(q), like(q)]
    if type_slug:
        where.append("t.slug=?")
        params.append(type_slug.lower())
    if damage_class:
        where.append("mg.damage_class=?")
        params.append(damage_class)
    base = f"""FROM move_game_data mg JOIN moves m ON m.id=mg.move_id JOIN types t ON t.id=mg.type_id
               WHERE {" AND ".join(where)}"""
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    found = rows(
        db,
        f"""SELECT m.id, m.slug, m.name, t.slug AS type, mg.damage_class, mg.power, mg.accuracy,
                         mg.pp, mg.priority, mg.evidence_id {base} ORDER BY m.id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return envelope(
        db,
        scope,
        found,
        features=("moves",),
        pagination=paging(limit, offset, total),
        include_evidence=False,
    )


def move_detail(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    move = resolve_move(db, key)
    data = one(
        db,
        """SELECT m.id, m.slug, m.name, m.generation_id, t.slug AS type, mg.damage_class, mg.power,
                      mg.accuracy, mg.pp, mg.priority, mg.target, mg.effect_chance, mg.evidence_id,
                      e.short_effect, e.effect, e.wording AS effect_wording, e.evidence_id AS effect_evidence_id
                      FROM move_game_data mg JOIN moves m ON m.id=mg.move_id JOIN types t ON t.id=mg.type_id
                      LEFT JOIN move_effects e ON e.id=mg.effect_id
                      WHERE mg.move_id=? AND mg.version_group_id=?""",
        (move["id"], scope.version_group_id),
    )
    if data is None:
        return envelope(
            db,
            scope,
            None,
            features=("moves",),
            assumptions=[
                f"'{move['slug']}' was introduced in generation {move['generation_id']} and has no values for "
                f"{scope.slug}."
            ],
        )
    for key_ in ("short_effect", "effect"):
        if data[key_] and data["effect_chance"] is not None:
            data[key_] = data[key_].replace("$effect_chance", str(data["effect_chance"]))
    data["flavor_text"] = one(
        db,
        "SELECT text, evidence_id FROM move_flavor_text WHERE move_id=? AND version_group_id=?",
        (move["id"], scope.version_group_id),
    )
    data["meta"] = one(db, "SELECT * FROM move_meta WHERE move_id=?", (move["id"],))
    data["flags"] = [
        r["flag"] for r in rows(db, "SELECT flag FROM move_flags WHERE move_id=? ORDER BY flag", (move["id"],))
    ]
    data["machine"] = one(
        db,
        "SELECT mc.kind, mc.machine_number, i.slug AS item, mc.evidence_id FROM machines mc "
        "JOIN items i ON i.id=mc.item_id WHERE mc.move_id=? AND mc.version_group_id=?",
        (move["id"], scope.version_group_id),
    )
    data["learner_count"] = db.execute(
        "SELECT count(DISTINCT form_id) FROM learnsets WHERE move_id=? AND version_group_id=?",
        (move["id"], scope.version_group_id),
    ).fetchone()[0]
    return envelope(
        db,
        scope,
        data,
        features=("moves", "move-effects", "move-flavor-text", "machines"),
        assumptions=[
            "Effect text uses the source's current wording; numbers (power, accuracy, PP, "
            "type, damage class) are version-group specific."
        ],
    )


def move_learners(db, game: str, key: str, limit: int, offset: int) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    move = resolve_move(db, key)
    base = "FROM learnsets l JOIN pokemon_forms f ON f.id=l.form_id WHERE l.move_id=? AND l.version_group_id=?"
    params = [move["id"], scope.version_group_id]
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    found = rows(
        db,
        f"SELECT f.id, f.slug, f.name, l.method, l.level, l.evidence_id {base} "
        f"ORDER BY f.species_id, f.id, l.method, l.level LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return envelope(
        db,
        scope,
        {"move": {"id": move["id"], "slug": move["slug"]}, "learners": found},
        features=("learnsets",),
        pagination=paging(limit, offset, total),
        include_evidence=False,
    )
