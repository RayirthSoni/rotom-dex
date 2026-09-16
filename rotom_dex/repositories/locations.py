"""Locations and per-location encounters for an exact game."""

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


def search_locations(db, game: str, q: str | None, limit: int, offset: int) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    where = ["EXISTS (SELECT 1 FROM acquisitions a WHERE a.location_id=l.id AND a.game_id=?)"]
    params: list = [scope.id]
    if q:
        where.append("(l.slug LIKE ? OR lower(l.name) LIKE ?)")
        params += [like(q), like(q)]
    base = f"FROM locations l WHERE {' AND '.join(where)}"
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    joined = base.replace("FROM locations l", "FROM locations l LEFT JOIN regions r ON r.id=l.region_id")
    found = rows(
        db,
        f"SELECT l.id, l.slug, l.name, r.slug AS region, l.evidence_id {joined} ORDER BY l.id LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return envelope(
        db,
        scope,
        found,
        features=("encounters",),
        pagination=paging(limit, offset, total),
        include_evidence=False,
        assumptions=["Only locations with at least one recorded route in this game are listed."],
    )


def location_encounters(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    location = one(
        db,
        "SELECT l.*, r.slug AS region FROM locations l LEFT JOIN regions r ON r.id=l.region_id WHERE l.slug=? OR CAST(l.id AS TEXT)=?",
        (key.lower(), key),
    )
    if location is None:
        raise NotFound(f"Unknown location '{key}'")
    routes = rows(
        db,
        """SELECT a.id, a.method, f.slug AS pokemon, f.name AS pokemon_name, i.slug AS item,
                         a.min_level, a.max_level, a.chance_percent, a.availability, a.prerequisites,
                         a.encounter_conditions, a.verification_status, la.slug AS location_area, la.name AS area_name,
                         a.evidence_id FROM acquisitions a LEFT JOIN pokemon_forms f ON f.id=a.form_id
                         LEFT JOIN items i ON i.id=a.item_id LEFT JOIN location_areas la ON la.id=a.location_area_id
                         WHERE a.game_id=? AND a.location_id=? ORDER BY la.id, a.method, a.chance_percent DESC, a.id""",
        (scope.id, location["id"]),
    )
    rates = rows(
        db,
        """SELECT la.slug AS location_area, er.method, er.rate, er.evidence_id FROM encounter_rates er
                        JOIN location_areas la ON la.id=er.location_area_id WHERE er.game_id=? AND la.location_id=?
                        ORDER BY la.id, er.method""",
        (scope.id, location["id"]),
    )
    data = {"location": location, "routes": routes, "encounter_rates": rates}
    return envelope(
        db,
        scope,
        data,
        features=("encounters", "gifts-trades"),
        assumptions=["Slot percentages are per method and area; do not sum across methods."],
    )
