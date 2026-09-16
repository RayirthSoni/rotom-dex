"""Natures (global table), exposed only for games that have the mechanic."""

from __future__ import annotations

from rotom_dex.repositories.common import NotFound, envelope, one, resolve_game, rows, unsupported


def _gate(db, scope):
    flag = scope.mechanics.get("natures")
    if flag == 0:
        return envelope(
            db,
            scope,
            None,
            features=("natures",),
            assumptions=[f"Natures are absent as a mechanic in {scope.slug}."],
        )
    if flag is None:
        return envelope(
            db,
            scope,
            None,
            features=("natures",),
            assumptions=[f"Whether {scope.slug} has Natures is unverified; no data is returned."],
        )
    return None


def list_natures(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    gated = _gate(db, scope)
    if gated:
        return gated
    natures = rows(db, "SELECT * FROM natures ORDER BY id")
    for n in natures:
        n["neutral"] = n["increased_stat"] == n["decreased_stat"]
    return envelope(
        db,
        scope,
        natures,
        features=("natures",),
        assumptions=["A nature whose increased and decreased stats match is neutral."],
    )


def nature_detail(db, game: str, key: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    gated = _gate(db, scope)
    if gated:
        return gated
    nature = one(db, "SELECT * FROM natures WHERE slug=? OR CAST(id AS TEXT)=?", (key.lower(), key))
    if nature is None:
        raise NotFound(f"Unknown nature '{key}'")
    nature["neutral"] = nature["increased_stat"] == nature["decreased_stat"]
    nature["modifiers"] = {} if nature["neutral"] else {nature["increased_stat"]: 1.1, nature["decreased_stat"]: 0.9}
    return envelope(db, scope, nature, features=("natures",))
