"""Abilities for an exact game (generation-scoped slots, version-group flavor text)."""

from __future__ import annotations

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


def _mechanic_absent(db, scope):
    return envelope(
        db,
        scope,
        None,
        features=("abilities",),
        assumptions=[f"Abilities are absent as a mechanic in {scope.slug}; no ability data applies."],
    )


def search_abilities(db, game: str, q: str | None, limit: int, offset: int) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    if scope.mechanics.get("abilities") == 0:
        return _mechanic_absent(db, scope)
    where = ["a.generation_id<=?", "a.is_main_series=1"]
    params: list = [scope.generation_id]
    if q:
        where.append("(a.slug LIKE ? OR lower(a.name) LIKE ?)")
        params += [like(q), like(q)]
    base = f"FROM abilities a WHERE {' AND '.join(where)}"
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    found = rows(
        db,
        f"SELECT a.id, a.slug, a.name, a.generation_id, a.evidence_id {base} ORDER BY a.id LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return envelope(
        db,
        scope,
        found,
        features=("abilities",),
        pagination=paging(limit, offset, total),
        include_evidence=False,
    )


def ability_detail(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    if scope.mechanics.get("abilities") == 0:
        return _mechanic_absent(db, scope)
    ability = one(db, "SELECT * FROM abilities WHERE slug=? OR CAST(id AS TEXT)=?", (key.lower(), key))
    if ability is None:
        raise NotFound(f"Unknown ability '{key}'")
    if ability["generation_id"] > scope.generation_id:
        return envelope(
            db,
            scope,
            None,
            features=("abilities",),
            assumptions=[f"'{ability['slug']}' was introduced in generation {ability['generation_id']}."],
        )
    data = {
        **ability,
        "effect": one(
            db,
            "SELECT short_effect, effect, wording, evidence_id FROM ability_effects WHERE ability_id=?",
            (ability["id"],),
        ),
        "flavor_text": one(
            db,
            "SELECT text, evidence_id FROM ability_flavor_text WHERE ability_id=? AND version_group_id=?",
            (ability["id"], scope.version_group_id),
        ),
        "changes": rows(
            db,
            """SELECT v.slug AS changed_in, c.effect, c.evidence_id FROM ability_changes c
                                   JOIN version_groups v ON v.id=c.changed_in_version_group_id
                                   WHERE c.ability_id=? ORDER BY v.ord""",
            (ability["id"],),
        ),
        "pokemon": rows(
            db,
            """SELECT f.id, f.slug, f.name, pa.slot, pa.is_hidden, pa.evidence_id
                                   FROM pokemon_abilities pa JOIN pokemon_forms f ON f.id=pa.form_id
                                   JOIN pokemon_version_groups p ON p.form_id=f.id AND p.version_group_id=?
                                   WHERE pa.ability_id=? AND pa.generation_id=? ORDER BY f.species_id, f.id""",
            (scope.version_group_id, ability["id"], scope.generation_id),
        ),
    }
    return envelope(
        db,
        scope,
        data,
        features=("abilities",),
        assumptions=["Effect text uses the source's current wording; version-group changes are listed separately."],
    )
