"""Team analysis: the defensive profile of each member and the offensive coverage of the whole.

This lived inside the API router until chat needed it too. It is here so the router, the chat tool
and any future caller compute the same answer from the same code rather than agreeing by accident.
"""

from __future__ import annotations

from rotom_dex.repositories.common import GameScope, rows
from rotom_dex.services import defense, offense
from rotom_dex.services.context import PlaythroughContext

ASSUMPTIONS = [defense.BASIC_ASSUMPTION, defense.ABILITY_ASSUMPTION, offense.ASSUMPTION]

FEATURES = ("types", "stats", "abilities", "ability-type-effects", "moves", "type-effectiveness")


def types_of(db, scope: GameScope, slug: str) -> list[str]:
    return [
        r["slug"]
        for r in rows(
            db,
            """SELECT t.slug FROM pokemon_types pt JOIN types t ON t.id=pt.type_id
               JOIN pokemon_forms f ON f.id=pt.form_id
               WHERE f.slug=? AND pt.generation_id=? ORDER BY pt.slot""",
            (slug, scope.generation_id),
        )
    ]


def analyse(db, scope: GameScope, ctx: PlaythroughContext, warnings: list[str] | None = None) -> dict:
    warnings = list(warnings or [])
    members = []
    for member in ctx.team:
        types = types_of(db, scope, member.pokemon)
        if not types:
            members.append(
                {
                    "pokemon": member.pokemon,
                    "level": member.level,
                    "types": [],
                    "defence": None,
                    "note": f"'{member.pokemon}' has no typing recorded for {scope.slug}, so it cannot be analysed. That is not a claim it is unobtainable.",
                }
            )
            continue
        members.append(
            {
                "pokemon": member.pokemon,
                "nickname": member.nickname,
                "level": member.level,
                "types": types,
                "ability": member.ability,
                "nature": member.nature,
                "held_item": member.held_item,
                "defence": defense.profile(db, scope, types, member.ability),
            }
        )
    team_moves = [{"pokemon": m.pokemon, "moves": list(m.moves)} for m in ctx.team]
    return {
        "team": members,
        "coverage": offense.coverage(db, scope, team_moves) if team_moves else None,
        "mechanics": scope.mechanics,
        "warnings": warnings,
    }
