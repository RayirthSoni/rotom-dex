"""Acquisition reachability: what your recorded progress does and does not settle.

The stored `availability` column is echoed untouched. Everything this module adds lives under
`derived`, so a reading of the player's context is never mistaken for a fact from the source.
"""

from __future__ import annotations

from rotom_dex.repositories import items as items_repo
from rotom_dex.repositories import pokemon as pokemon_repo
from rotom_dex.repositories.common import GameScope
from rotom_dex.services.context import PlaythroughContext, classify, condition_context

ASSUMPTION = (
    "Reachability is derived from your recorded progress, not stored in the database. A route is "
    "reported as locked only when a prerequisite you vouched for is unmet; anything else stays "
    "unknown. No derivation ever reports a route as unavailable."
)


def _decorate(routes: list[dict], context: dict) -> list[dict]:
    for route in routes:
        prerequisites = route.get("prerequisites")
        route["derived"] = (
            classify(prerequisites, context)
            if prerequisites
            else {
                "status": "unknown",
                "evaluation": None,
                "blocked_by": [],
                "unknown_because": [{"op": "unknown", "reason": "This route records no prerequisites."}],
            }
        )
    return routes


def summarise(routes: list[dict]) -> dict[str, int]:
    counts = {"reachable": 0, "locked": 0, "unknown": 0}
    for route in routes:
        counts[route["derived"]["status"]] += 1
    return counts


def for_pokemon(db, scope: GameScope, ctx: PlaythroughContext, slug: str) -> dict:
    context, assumptions = condition_context(ctx)
    result = pokemon_repo.pokemon_acquisition(db, scope.slug, slug)
    data = result["data"]
    if data is None:
        return {"pokemon": slug, "data": None, "assumptions": result["assumptions"]}
    _decorate(data["routes"], context)
    return {"pokemon": slug, "routes": data["routes"], "counts": summarise(data["routes"]), "assumptions": assumptions}


def for_item(db, scope: GameScope, ctx: PlaythroughContext, slug: str) -> dict:
    context, assumptions = condition_context(ctx)
    result = items_repo.item_detail(db, scope.slug, slug)
    data = result["data"]
    if data is None:
        return {"item": slug, "data": None, "assumptions": result["assumptions"]}
    routes = _decorate(data["acquisition"], context)
    shops = _decorate([{**s, "prerequisites": s.get("prerequisites")} for s in data["shops"]], context)
    return {
        "item": slug,
        "routes": routes,
        "shops": shops,
        "counts": summarise(routes),
        "assumptions": assumptions,
    }
