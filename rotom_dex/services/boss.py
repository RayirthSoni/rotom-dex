"""Boss preparation from a reviewed roster.

This is preparation, not prediction. There is no battle simulator here: the output is the roster,
how each side's types line up, where your levels sit, and which resources your recorded progress can
already reach. It never states who would win.

Only one battle in this snapshot has a reviewed roster, so abstention is the normal path: a game
whose `boss-teams` coverage is missing returns no plan and says why.
"""

from __future__ import annotations

from rotom_dex.repositories import progression as progression_repo
from rotom_dex.repositories.common import GameScope, coverage_rows, rows
from rotom_dex.services import defense, offense
from rotom_dex.services.context import PlaythroughContext, classify, condition_context
from rotom_dex.services.reachability import summarise

ASSUMPTIONS = [
    "This is preparation, not a prediction. No battle is simulated, so nothing here states or implies an outcome.",
    "Type matchups use this generation's chart. Stats, held items, move order, accuracy and AI behaviour are not modelled.",
    "Level differences are shown as they are; they are context for your own judgement, not a recommendation to grind.",
]


def _member_types(db, scope: GameScope, slug: str) -> list[str]:
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


def prepare(db, scope: GameScope, ctx: PlaythroughContext, battle_key: str) -> dict:
    context, assumptions = condition_context(ctx)
    # Abstain before looking the battle up. In a game with no reviewed rosters at all, "we have no
    # boss data for this game" is the true answer; "unknown battle" would blame the question.
    roster_coverage = coverage_rows(db, scope.id, ("boss-teams",))
    if not roster_coverage or all(c["status"] == "missing" for c in roster_coverage):
        return {
            "battle": battle_key,
            "data": None,
            "assumptions": [
                f"No boss rosters have been reviewed for {scope.slug}, so no preparation can be offered. "
                "That is a gap in the reviewed data, not a claim that this game has no bosses.",
                *assumptions,
            ],
        }
    battle = progression_repo.battle_detail(db, scope.slug, battle_key)["data"]
    if battle is None:
        return {"battle": battle_key, "data": None, "assumptions": assumptions}

    team = [{"pokemon": m.pokemon, "moves": list(m.moves)} for m in ctx.team]
    our_coverage = offense.coverage(db, scope, team) if team else None

    # How our moves line up against each of theirs.
    threats = []
    for enemy in battle["party"]:
        enemy_defence = defense.profile(db, scope, enemy["types"], enemy.get("ability"))
        best = None
        if our_coverage:
            multipliers = {}
            for move in our_coverage["attacking_moves"]:
                row = next(r for r in enemy_defence["basic"]["by_type"] if r["attack"] == move["type"])
                multipliers[(move["pokemon"], move["slug"])] = row["multiplier"]
            if multipliers:
                (pokemon, move), multiplier = max(multipliers.items(), key=lambda kv: kv[1])
                best = {"pokemon": pokemon, "move": move, "multiplier": multiplier}
        threats.append(
            {
                "slot": enemy["slot"],
                "pokemon": enemy["pokemon"],
                "name": enemy["name"],
                "level": enemy["level"],
                "types": enemy["types"],
                "ability": enemy.get("ability"),
                "held_item": enemy.get("held_item"),
                "moves": enemy.get("moves") or [],
                "their_move_types": _their_move_types(db, scope, enemy.get("moves") or []),
                "our_best_move": best,
                "defence": enemy_defence,
                "verification_status": enemy.get("verification_status"),
            }
        )

    # What each of our members faces from their known moves.
    our_members = []
    for member in ctx.team:
        types = _member_types(db, scope, member.pokemon)
        if not types:
            our_members.append({"pokemon": member.pokemon, "level": member.level, "types": [], "note": f"'{member.pokemon}' has no typing recorded for {scope.slug}."})
            continue
        profile = defense.profile(db, scope, types, member.ability)
        # One entry per distinct move, listing which of their Pokemon carry it: two Geodudes with the
        # same moveset are one threat to plan around, not two.
        incoming: dict[str, dict] = {}
        for threat in threats:
            for move_type in threat["their_move_types"]:
                row = next((r for r in profile["basic"]["by_type"] if r["attack"] == move_type["type"]), None)
                if not row or row["multiplier"] <= 1:
                    continue
                entry = incoming.setdefault(
                    move_type["move"],
                    {"move": move_type["move"], "type": move_type["type"], "multiplier": row["multiplier"], "from": []},
                )
                if threat["pokemon"] not in entry["from"]:
                    entry["from"].append(threat["pokemon"])
        our_members.append(
            {
                "pokemon": member.pokemon,
                "level": member.level,
                "types": types,
                "ability": member.ability,
                "defence": profile,
                "takes_super_effective": sorted(incoming.values(), key=lambda e: (-e["multiplier"], e["move"])),
            }
        )

    levels = [m.level for m in ctx.team if m.level is not None]
    enemy_levels = [e["level"] for e in battle["party"]]
    resources = _reachable_resources(db, scope, context)
    return {
        "battle": battle,
        "threats": threats,
        "team": our_members,
        "coverage": our_coverage,
        "levels": {
            "yours": sorted(levels),
            "theirs": sorted(enemy_levels),
            "their_highest": max(enemy_levels) if enemy_levels else None,
            "your_lowest": min(levels) if levels else None,
            "note": "No level is recorded for some team members." if len(levels) != len(ctx.team) else "",
        },
        "resources": resources,
        "assumptions": assumptions,
    }


def _their_move_types(db, scope: GameScope, moves: list[str]) -> list[dict]:
    out = []
    for slug in moves:
        values = offense.move_values(db, scope, slug)
        if values and values["damage_class"] != "status" and values["power"] is not None:
            out.append({"move": slug, "type": values["type"], "power": values["power"], "damage_class": values["damage_class"]})
        elif values:
            out.append({"move": slug, "type": values["type"], "power": values["power"], "damage_class": values["damage_class"], "note": "deals no direct damage"})
    return out


def _reachable_resources(db, scope: GameScope, context: dict) -> dict:
    """Shops and item routes your recorded progress already settles, for stocking up beforehand."""
    shop_rows = rows(
        db,
        """SELECT s.id AS shop_id, s.name, l.slug AS location, s.prerequisites AS shop_prerequisites,
                  i.slug AS item, i.name AS item_name, si.price, si.prerequisites
           FROM shop_items si JOIN shops s ON s.id=si.shop_id JOIN items i ON i.id=si.item_id
           LEFT JOIN locations l ON l.id=s.location_id WHERE s.game_id=? ORDER BY s.id, i.id""",
        (scope.id,),
    )
    for row in shop_rows:
        row["derived"] = classify(row["prerequisites"], context)
    return {"shop_items": shop_rows, "counts": summarise(shop_rows)}
