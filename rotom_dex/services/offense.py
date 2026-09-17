"""Offensive coverage computed from the moves a team actually has.

Only damaging moves count. A status move is listed and excluded, because it contributes no type
multiplier, and a move whose power is null has no fixed power in this generation. Coverage is a
preparation signal: it ignores STAB, stats, accuracy, PP, items and abilities, so it says what a
team *can hit*, never what it will win.
"""

from __future__ import annotations

from rotom_dex.calculators import type_effectiveness as calc
from rotom_dex.repositories.common import GameScope, one, rows

ASSUMPTION = (
    "Coverage is type multipliers from this generation's chart only: no same-type bonus, stats, "
    "accuracy, PP, held items or abilities are applied. It is a preparation signal, not a prediction "
    "of a battle result."
)


def move_values(db, scope: GameScope, slug: str) -> dict | None:
    return one(
        db,
        """SELECT m.slug, m.name, t.slug AS type, g.damage_class, g.power, g.accuracy, g.pp, g.priority, g.evidence_id
           FROM move_game_data g JOIN moves m ON m.id=g.move_id JOIN types t ON t.id=g.type_id
           WHERE m.slug=? AND g.version_group_id=?""",
        (slug, scope.version_group_id),
    )


def coverage(db, scope: GameScope, team: list[dict]) -> dict:
    """Best multiplier per defending type across every damaging move on the team.

    `team` is a list of `{"pokemon": slug, "moves": [slug, ...]}`.
    """
    gen = scope.generation_id
    defenders = [r["slug"] for r in rows(db, "SELECT slug FROM types WHERE generation_id<=? ORDER BY id", (gen,))]
    attacking: list[dict] = []
    excluded: list[dict] = []
    for member in team:
        for slug in member.get("moves", ()):
            values = move_values(db, scope, slug)
            if values is None:
                excluded.append({"pokemon": member["pokemon"], "move": slug, "reason": f"'{slug}' has no values in {scope.slug}."})
                continue
            entry = {"pokemon": member["pokemon"], "move": values["slug"], **values}
            if values["damage_class"] == "status":
                excluded.append({**entry, "reason": "Status moves deal no damage, so they add no type coverage."})
            elif values["power"] is None:
                excluded.append({**entry, "reason": "This move has no fixed power in this generation, so its damage cannot be compared by type."})
            else:
                attacking.append(entry)

    by_type = []
    for defender in defenders:
        best = {"defense": defender, "multiplier": 0.0, "moves": []}
        for move in attacking:
            factor = calc.factor(db, gen, calc.type_id(db, move["type"], gen), [calc.type_id(db, defender, gen)])
            multiplier = factor["multiplier"]
            if multiplier > best["multiplier"]:
                best = {"defense": defender, "multiplier": multiplier, "moves": []}
            if multiplier == best["multiplier"]:
                best["moves"].append({"pokemon": move["pokemon"], "move": move["slug"], "type": move["type"]})
        by_type.append(best)

    return {
        "generation": gen,
        "attacking_moves": attacking,
        "excluded_moves": excluded,
        "by_type": by_type,
        "super_effective_against": [b["defense"] for b in by_type if b["multiplier"] > 1],
        "neutral_at_best_against": [b["defense"] for b in by_type if b["multiplier"] == 1],
        "resisted_against": [b["defense"] for b in by_type if 0 < b["multiplier"] < 1],
        "no_effect_against": [b["defense"] for b in by_type if b["multiplier"] == 0],
    }
