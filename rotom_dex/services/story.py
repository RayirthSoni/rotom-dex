"""Small explainable story-team shortlist from exact-game records, not usage rankings."""

from __future__ import annotations

from collections import Counter

from rotom_dex.repositories import pokemon
from rotom_dex.repositories.common import rows
from rotom_dex.services import defense, reachability, team


def recommend(db, scope, ctx, favorites=(), level=20):
    existing = {m.pokemon for m in ctx.team}
    weak = Counter()
    existing_types = set()
    for member in ctx.team:
        typing = team.types_of(db, scope, member.pokemon)
        existing_types.update(typing)
        if typing:
            weak.update(defense.profile(db, scope, typing, member.ability)["basic"]["weaknesses"])
    # Only local recorded acquisition candidates. Unknown access stays unknown.
    candidates = rows(
        db,
        """SELECT DISTINCT f.slug,f.name FROM acquisitions a JOIN pokemon_forms f ON f.id=a.form_id
                         WHERE a.game_id=? AND a.location_id IS NOT NULL AND a.availability!='unavailable'
                         AND (a.min_level IS NULL OR a.min_level<=?) ORDER BY f.id LIMIT 100""",
        (scope.id, level),
    )
    result = []
    for candidate in candidates:
        slug = candidate["slug"]
        if slug in existing:
            continue
        typing = team.types_of(db, scope, slug)
        if not typing:
            continue
        acquisition = reachability.for_pokemon(db, scope, ctx, slug)
        routes = [r for r in acquisition.get("routes", []) if r.get("location") and (r.get("min_level") or 0) <= level]
        if ctx.trade_access == "none":
            routes = [r for r in routes if "trade" not in r["method"]]
        if not routes:
            continue
        accessible = [r for r in routes if r["derived"]["status"] == "reachable"]
        unknown = [r for r in routes if r["derived"]["status"] == "unknown"]
        if not accessible and not unknown:
            continue
        profile = defense.profile(db, scope, typing)["basic"]
        helps = sorted(t for t in profile["resistances"] + profile["immunities"] if weak[t])
        novel = sorted(set(typing) - existing_types)
        score = 4 * bool(accessible) + 2 * len(helps) + len(novel) + 3 * (slug in favorites)
        learnset = pokemon.pokemon_learnset(db, scope.slug, slug, "level-up", level)["data"] or {}
        moves = list(reversed(learnset.get("moves", [])))[:4]
        result.append(
            {
                "pokemon": slug,
                "name": candidate["name"],
                "rank_score": score,
                "status": "reachable" if accessible else "unknown",
                "role": "Adds defensive options" if helps else "Adds type variety",
                "resists_team_weaknesses": helps,
                "new_types": novel,
                "routes": (accessible or unknown)[:2],
                "moves": moves,
                "tradeoff": "Ranked by typing and access, not a full battle simulation. Check move timing and training effort before replacing a teammate.",
            }
        )
    return {
        "recommendations": sorted(result, key=lambda r: (-r["rank_score"], r["pokemon"]))[:3],
        "assumptions": [
            f"Candidate catch levels and level-up moves are limited to level {level}.",
            "The shortlist searches up to 100 locally recorded catchable candidates. Missing records can exclude useful choices.",
            "Items, abilities, evolution effort, upcoming bosses and strategy require additional checks.",
        ],
    }
