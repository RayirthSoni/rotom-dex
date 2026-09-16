"""Item search and detail for an exact game."""

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


def resolve_item(db: sqlite3.Connection, key: str) -> dict:
    item = one(db, "SELECT * FROM items WHERE slug=? OR CAST(id AS TEXT)=?", (key.lower(), key))
    if item is None:
        raise NotFound(f"Unknown item '{key}'")
    return item


def search_items(db, game: str, q: str | None, category: str | None, limit: int, offset: int) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    where = ["ig.version_group_id=?"]
    params: list = [scope.version_group_id]
    if q:
        where.append("(i.slug LIKE ? OR lower(i.name) LIKE ?)")
        params += [like(q), like(q)]
    if category:
        where.append("(i.category=? OR i.pocket=?)")
        params += [category, category]
    base = f"FROM item_game_data ig JOIN items i ON i.id=ig.item_id WHERE {' AND '.join(where)}"
    total = db.execute(f"SELECT count(*) {base}", params).fetchone()[0]
    found = rows(
        db,
        f"""SELECT i.id, i.slug, i.name, i.category, i.pocket, ig.purchase_price, ig.sell_price,
                         ig.price_provenance, ig.evidence_id {base} ORDER BY i.id LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return envelope(
        db,
        scope,
        found,
        features=("items", "item-prices"),
        pagination=paging(limit, offset, total),
        include_evidence=False,
    )


def item_detail(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    item = resolve_item(db, key)
    data = one(
        db,
        """SELECT i.id, i.slug, i.name, i.category, i.pocket, i.fling_power, ig.flavor_text,
                      ig.purchase_price, ig.sell_price, ig.price_provenance, ig.evidence_id
                      FROM item_game_data ig JOIN items i ON i.id=ig.item_id
                      WHERE ig.item_id=? AND ig.version_group_id=?""",
        (item["id"], scope.version_group_id),
    )
    if data is None:
        return envelope(
            db,
            scope,
            None,
            features=("items",),
            assumptions=[f"'{item['slug']}' has no game index for generation {scope.generation_id} in the source; this does not prove it is absent from the game."],
        )
    data["effect"] = one(
        db,
        "SELECT short_effect, effect, wording, evidence_id FROM item_effects WHERE item_id=?",
        (item["id"],),
    )
    data["attributes"] = [r["flag"] for r in rows(db, "SELECT flag FROM item_attributes WHERE item_id=? ORDER BY flag", (item["id"],))]
    data["holdable"] = ("holdable" in data["attributes"]) if scope.mechanics.get("held_items") != 0 else False
    data["machine"] = one(
        db,
        """SELECT mc.kind, mc.machine_number, m.slug AS move, m.name AS move_name, mc.evidence_id
                                 FROM machines mc JOIN moves m ON m.id=mc.move_id
                                 WHERE mc.item_id=? AND mc.version_group_id=?""",
        (item["id"], scope.version_group_id),
    )
    if data["machine"]:
        data["machine"]["reusable"] = scope.mechanics.get("tm_reusable") if data["machine"]["kind"] == "tm" else (1 if data["machine"]["kind"] == "hm" else 0)
    data["acquisition"] = rows(
        db,
        """SELECT a.id, a.method, a.availability, a.prerequisites, a.verification_status,
                                      a.note, l.slug AS location, l.name AS location_name, a.evidence_id
                                      FROM acquisitions a LEFT JOIN locations l ON l.id=a.location_id
                                      WHERE a.game_id=? AND a.item_id=? ORDER BY a.id""",
        (scope.id, item["id"]),
    )
    data["shops"] = rows(
        db,
        """SELECT s.id, s.name, l.slug AS location, si.price, si.prerequisites,
                                s.verification_status, si.evidence_id
                                FROM shop_items si JOIN shops s ON s.id=si.shop_id
                                LEFT JOIN locations l ON l.id=s.location_id
                                WHERE s.game_id=? AND si.item_id=? ORDER BY s.id""",
        (scope.id, item["id"]),
    )
    data["held_by"] = rows(
        db,
        """SELECT f.slug AS pokemon, f.name, h.rarity, h.evidence_id FROM pokemon_held_items h
                                  JOIN pokemon_forms f ON f.id=h.form_id WHERE h.game_id=? AND h.item_id=?
                                  ORDER BY h.rarity DESC, f.id""",
        (scope.id, item["id"]),
    )
    return envelope(
        db,
        scope,
        data,
        features=(
            "items",
            "item-prices",
            "item-effects",
            "item-flavor-text",
            "item-acquisition",
            "shops",
            "held-items",
        ),
        assumptions=[
            "Effect text uses the source's current wording; the in-game description is version-group specific.",
            "Price provenance 'default-cost' means the source's generic cost, not a value verified for this game.",
        ],
    )
