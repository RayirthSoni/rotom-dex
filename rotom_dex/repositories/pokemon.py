"""Pokémon search, detail, acquisition, evolution and learnsets for an exact game."""

from __future__ import annotations

import sqlite3

from rotom_dex.repositories.common import (
    GameScope,
    NotFound,
    envelope,
    like,
    one,
    paging,
    resolve_game,
    rows,
    unsupported,
)

LEARNSET_ASSUMPTIONS = [
    "Learnsets describe eligibility. Machine, tutor and breeding access are not established by a row.",
    "Level filtering applies only to level-up moves; other methods remain listed.",
]
ACQUISITION_ASSUMPTIONS = [
    "Availability is 'unknown' until progression gates are reviewed; absent routes do not mean unobtainable.",
    "Encounter percentages describe individual slots and must not be summed across methods.",
]


def resolve_form(db: sqlite3.Connection, key: str) -> dict:
    form = one(
        db,
        """SELECT f.*, s.slug AS species_slug, s.name AS species_name, s.generation_id
                      FROM pokemon_forms f JOIN species s ON s.id=f.species_id
                      WHERE f.slug=? OR (f.is_default=1 AND CAST(f.species_id AS TEXT)=?)
                      OR CAST(f.id AS TEXT)=? ORDER BY f.is_default DESC LIMIT 1""",
        (key.lower(), key, key),
    )
    if form is None:
        raise NotFound(f"Unknown Pokémon '{key}' (not in the catalog)")
    return form


def presence(db: sqlite3.Connection, scope: GameScope, form_id: int) -> dict | None:
    return one(
        db,
        "SELECT presence, evidence_id FROM pokemon_version_groups WHERE form_id=? AND version_group_id=?",
        (form_id, scope.version_group_id),
    )


def search_pokemon(
    db: sqlite3.Connection, game: str, q: str | None, type_slug: str | None, limit: int, offset: int
) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    where = ["p.version_group_id=?"]
    params: list = [scope.version_group_id]
    if q:
        where.append("(f.slug LIKE ? OR lower(f.name) LIKE ? OR CAST(f.species_id AS TEXT)=?)")
        params += [like(q), like(q), q.strip()]
    if type_slug:
        where.append(
            "EXISTS (SELECT 1 FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE "
            "pt.form_id=f.id AND pt.generation_id=? AND t.slug=?)"
        )
        params += [scope.generation_id, type_slug.lower()]
    base = f"""FROM pokemon_version_groups p JOIN pokemon_forms f ON f.id=p.form_id
               WHERE {" AND ".join(where)}"""
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    found = rows(
        db,
        f"""SELECT f.id, f.slug, f.name, f.species_id, f.is_default, p.presence,
                         p.evidence_id {base} ORDER BY f.species_id, f.id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    for r in found:
        r["types"] = [
            t["slug"]
            for t in rows(
                db,
                "SELECT t.slug FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE pt.form_id=? "
                "AND pt.generation_id=? ORDER BY pt.slot",
                (r["id"], scope.generation_id),
            )
        ]
    return envelope(
        db,
        scope,
        found,
        features=("pokemon", "types"),
        pagination=paging(limit, offset, total),
        include_evidence=False,
    )


def pokemon_detail(db: sqlite3.Connection, game: str, key: str, level: int | None = None) -> dict:
    """Full card: species/form facts, generation battle data, and the three sub-resources."""
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    form = resolve_form(db, key)
    core = _core(db, scope, form)
    if core is None:
        return _absent(db, scope, form)
    core["acquisition"] = pokemon_acquisition(db, game, key)["data"]
    core["evolution"] = pokemon_evolution(db, game, key)["data"]
    core["learnset"] = pokemon_learnset(db, game, key, None, level)["data"]
    return envelope(db, scope, core, assumptions=LEARNSET_ASSUMPTIONS + ACQUISITION_ASSUMPTIONS)


def pokemon_core(db: sqlite3.Connection, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    form = resolve_form(db, key)
    core = _core(db, scope, form)
    if core is None:
        return _absent(db, scope, form)
    return envelope(db, scope, core, features=("pokemon", "types", "stats", "abilities", "held-items"))


def _absent(db, scope, form):
    return envelope(
        db,
        scope,
        None,
        features=("pokemon",),
        assumptions=[
            f"'{form['slug']}' exists in the catalog but has no data for {scope.slug} (introduced in "
            f"generation {form['generation_id']}, or absent from this game's data). This does not by itself "
            "prove the Pokémon is unobtainable."
        ],
    )


def _core(db, scope, form) -> dict | None:
    pres = presence(db, scope, form["id"])
    if pres is None:
        return None
    gen, fid = scope.generation_id, form["id"]
    data = {
        "form": {
            k: form[k]
            for k in (
                "id",
                "slug",
                "name",
                "species_id",
                "species_slug",
                "species_name",
                "is_default",
                "height_dm",
                "weight_hg",
                "base_experience",
                "evidence_id",
            )
        },
        "presence": pres,
        "species": one(
            db,
            """SELECT generation_id, evolves_from_species_id, evolution_chain_id, gender_rate,
                              capture_rate, base_happiness, hatch_counter, growth_rate, is_baby, is_legendary,
                              is_mythical, evidence_id FROM species WHERE id=?""",
            (form["species_id"],),
        ),
        "types": rows(
            db,
            "SELECT pt.slot, t.slug AS type, pt.evidence_id FROM pokemon_types pt JOIN types t "
            "ON t.id=pt.type_id WHERE pt.form_id=? AND pt.generation_id=? ORDER BY pt.slot",
            (fid, gen),
        ),
        "stats": rows(
            db,
            "SELECT stat, base_stat, effort, evidence_id FROM pokemon_stats WHERE form_id=? AND "
            "generation_id=? ORDER BY CASE stat WHEN 'hp' THEN 1 WHEN 'attack' THEN 2 WHEN "
            "'defense' THEN 3 WHEN 'special-attack' THEN 4 WHEN 'special-defense' THEN 5 WHEN "
            "'special' THEN 6 ELSE 7 END",
            (fid, gen),
        ),
        "abilities": rows(
            db,
            "SELECT pa.slot, a.slug AS ability, a.name, pa.is_hidden, pa.evidence_id FROM "
            "pokemon_abilities pa JOIN abilities a ON a.id=pa.ability_id WHERE pa.form_id=? "
            "AND pa.generation_id=? ORDER BY pa.slot",
            (fid, gen),
        ),
        "egg_groups": [
            r["egg_group"]
            for r in rows(
                db,
                "SELECT egg_group FROM pokemon_egg_groups WHERE species_id=? ORDER BY egg_group",
                (form["species_id"],),
            )
        ],
        "held_items": rows(
            db,
            "SELECT i.slug AS item, i.name, h.rarity, h.evidence_id FROM pokemon_held_items h "
            "JOIN items i ON i.id=h.item_id WHERE h.form_id=? AND h.game_id=? ORDER BY "
            "h.rarity DESC",
            (fid, scope.id),
        ),
        "dex_numbers": rows(
            db,
            """SELECT d.slug AS pokedex, n.number, n.evidence_id FROM pokemon_dex_numbers n
                                   JOIN pokedexes d ON d.id=n.pokedex_id WHERE n.species_id=? AND (d.slug='national'
                                   OR EXISTS (SELECT 1 FROM pokedex_version_groups pv WHERE pv.pokedex_id=d.id
                                   AND pv.version_group_id=?)) ORDER BY d.id""",
            (form["species_id"], scope.version_group_id),
        ),
        "variants": rows(
            db,
            "SELECT id, slug, form_name, is_default, is_mega, is_battle_only, "
            "introduced_in_version_group_id FROM form_variants WHERE form_id=? ORDER BY id",
            (fid,),
        ),
        "other_forms": rows(
            db,
            "SELECT f.id, f.slug, f.name, p.presence FROM pokemon_forms f LEFT JOIN "
            "pokemon_version_groups p ON p.form_id=f.id AND p.version_group_id=? "
            "WHERE f.species_id=? AND f.id!=? ORDER BY f.id",
            (scope.version_group_id, form["species_id"], fid),
        ),
    }
    if scope.mechanics.get("abilities") == 0:
        data["abilities"] = []
        data["abilities_note"] = "Abilities are absent as a mechanic in this game."
    return data


def pokemon_acquisition(db: sqlite3.Connection, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    form = resolve_form(db, key)
    if presence(db, scope, form["id"]) is None:
        return _absent(db, scope, form)
    routes = rows(
        db,
        """SELECT a.id, a.method, a.min_level, a.max_level, a.chance_percent, a.availability,
                         a.prerequisites, a.encounter_conditions, a.verification_status, a.note,
                         l.slug AS location, l.name AS location_name, la.slug AS location_area,
                         la.name AS location_area_name, a.location_area_id, a.evidence_id
                         FROM acquisitions a LEFT JOIN locations l ON l.id=a.location_id
                         LEFT JOIN location_areas la ON la.id=a.location_area_id
                         WHERE a.game_id=? AND a.form_id=? ORDER BY a.method, a.id""",
        (scope.id, form["id"]),
    )
    for r in routes:
        if r["location_area_id"] is not None:
            r["encounter_rate"] = one(
                db,
                "SELECT rate FROM encounter_rates WHERE location_area_id=? AND method=? AND game_id=?",
                (r["location_area_id"], r["method"], scope.id),
            )
    data = {
        "form": {"id": form["id"], "slug": form["slug"], "name": form["name"]},
        "routes": routes,
        "route_counts": _counts(routes, "method"),
    }
    return envelope(
        db,
        scope,
        data,
        features=("encounters", "gifts-trades", "breeding", "evolution"),
        assumptions=ACQUISITION_ASSUMPTIONS,
    )


def pokemon_evolution(db: sqlite3.Connection, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    form = resolve_form(db, key)
    if presence(db, scope, form["id"]) is None:
        return _absent(db, scope, form)
    rules = rows(
        db,
        """SELECT r.id, r.trigger, r.conditions, r.raw, r.introduced_version_group_id,
                        f.slug AS from_pokemon, f.name AS from_name, t.slug AS to_pokemon, t.name AS to_name,
                        a.status AS applicability, a.reason, a.verification_status, r.evidence_id,
                        a.evidence_id AS applicability_evidence_id
                        FROM evolution_rules r JOIN pokemon_forms f ON f.id=r.from_form_id
                        JOIN pokemon_forms t ON t.id=r.to_form_id
                        LEFT JOIN evolution_applicability a ON a.rule_id=r.id AND a.version_group_id=?
                        WHERE r.from_form_id=? OR r.to_form_id=? ORDER BY r.id""",
        (scope.version_group_id, form["id"], form["id"]),
    )
    data = {
        "form": {"id": form["id"], "slug": form["slug"], "name": form["name"]},
        "outgoing": [r for r in rules if r["from_pokemon"] == form["slug"]],
        "incoming": [r for r in rules if r["to_pokemon"] == form["slug"]],
    }
    return envelope(
        db,
        scope,
        data,
        features=("evolution",),
        assumptions=[
            "Rules include immediate incoming and outgoing evolutions only, with their applicability to this "
            "game (derived unless reference-reviewed)."
        ],
    )


def pokemon_learnset(db: sqlite3.Connection, game: str, key: str, method: str | None, max_level: int | None) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    form = resolve_form(db, key)
    if presence(db, scope, form["id"]) is None:
        return _absent(db, scope, form)
    where = ["l.form_id=?", "l.version_group_id=?"]
    params: list = [form["id"], scope.version_group_id]
    if method:
        where.append("l.method=?")
        params.append(method)
    if max_level is not None:
        where.append("(l.method!='level-up' OR l.level<=?)")
        params.append(max_level)
    moves = rows(
        db,
        f"""SELECT l.method, l.level, l.ord, m.id AS move_id, m.slug AS move, m.name AS move_name,
                         t.slug AS type, mg.damage_class, mg.power, mg.accuracy, mg.pp, mg.priority,
                         l.evidence_id, mg.evidence_id AS move_evidence_id,
                         mc.kind AS machine_kind, mc.machine_number, i.slug AS machine_item
                         FROM learnsets l JOIN moves m ON m.id=l.move_id
                         JOIN move_game_data mg ON mg.move_id=l.move_id AND mg.version_group_id=l.version_group_id
                         JOIN types t ON t.id=mg.type_id
                         LEFT JOIN machines mc ON mc.move_id=l.move_id AND mc.version_group_id=l.version_group_id
                         AND l.method='machine' LEFT JOIN items i ON i.id=mc.item_id
                         WHERE {" AND ".join(where)}
                         ORDER BY CASE l.method WHEN 'level-up' THEN 0 ELSE 1 END, l.method, l.level, l.ord, m.slug""",
        params,
    )
    data = {
        "form": {"id": form["id"], "slug": form["slug"], "name": form["name"]},
        "moves": moves,
        "method_counts": _counts(moves, "method"),
        "machine_rules": {k: scope.mechanics.get(k) for k in ("tm_present", "tm_reusable", "hm_present", "tr_present")},
    }
    return envelope(
        db,
        scope,
        data,
        features=("learnsets", "machines", "tutors"),
        assumptions=LEARNSET_ASSUMPTIONS,
    )


def _counts(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item[key]] = counts.get(item[key], 0) + 1
    return dict(sorted(counts.items()))
