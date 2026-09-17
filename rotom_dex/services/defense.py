"""Defensive type profiles, with the ability layer kept strictly separate from the type layer.

Two blocks are always returned. `basic` is the generation's type chart and nothing else. `ability`
is the same profile with reviewed ability modifiers applied, and exists only when the game has the
ability mechanic and the holder's ability has a reviewed entry. They are never merged, because one
is a fact from the source and the other is a curated, deliberately incomplete overlay.
"""

from __future__ import annotations

from rotom_dex.calculators import type_effectiveness as calc
from rotom_dex.repositories.common import GameScope, rows

BASIC_ASSUMPTION = "Multipliers are the generation's type chart only: abilities, items, weather and move-specific interactions are not applied."
ABILITY_ASSUMPTION = (
    "The ability-adjusted figures apply reviewed type modifiers only. Abilities whose effect depends on a "
    "move flag, the weather, the field or remaining HP are not applied, and are listed as data issues under "
    "the ability-type-effects coverage feature."
)


def ability_modifiers(db, generation: int, ability: str | None) -> list[dict]:
    if not ability:
        return []
    return rows(
        db,
        """SELECT e.applies_to, t.slug AS type, e.damage_factor, e.note, e.verification_status, e.evidence_id
           FROM ability_type_effects e JOIN abilities a ON a.id=e.ability_id
           LEFT JOIN types t ON t.id=e.type_id
           WHERE a.slug=? AND e.generation_id=? ORDER BY e.applies_to, t.id""",
        (ability, generation),
    )


def _apply(basic: float, modifiers: list[dict], attack: str) -> tuple[float, list[dict]]:
    """Apply reviewed modifiers to one attacking type. Effectiveness classes read the basic value."""
    value, applied = basic, []
    for mod in modifiers:
        if mod["applies_to"] == "type" and mod["type"] == attack:
            value = value * mod["damage_factor"] / 100
        elif mod["applies_to"] == "super-effective" and basic > 1:
            value = value * mod["damage_factor"] / 100
        elif mod["applies_to"] == "non-super-effective" and basic <= 1:
            value = value * mod["damage_factor"] / 100
        else:
            continue
        applied.append(mod)
    return value, applied


def _buckets(by_type: list[dict], key: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"immunities": [], "resistances": [], "weaknesses": []}
    for row in by_type:
        value = row[key]
        if value == 0:
            out["immunities"].append(row["attack"])
        elif value < 1:
            out["resistances"].append(row["attack"])
        elif value > 1:
            out["weaknesses"].append(row["attack"])
    return out


def profile(db, scope: GameScope, defending: list[str], ability: str | None = None) -> dict:
    """Per attacking type, how much damage this typing takes in this game's generation."""
    gen = scope.generation_id
    defense_ids = [calc.type_id(db, slug, gen) for slug in defending]
    attackers = rows(db, "SELECT slug FROM types WHERE generation_id<=? ORDER BY id", (gen,))
    ability_supported = scope.mechanics.get("abilities") == 1
    modifiers = ability_modifiers(db, gen, ability) if ability_supported else []

    by_type = []
    for attacker in attackers:
        slug = attacker["slug"]
        result = calc.factor(db, gen, calc.type_id(db, slug, gen), defense_ids)
        row = {"attack": slug, "multiplier": result["multiplier"], "parts": result["parts"]}
        if modifiers:
            adjusted, applied = _apply(result["multiplier"], modifiers, slug)
            row["ability_multiplier"] = adjusted
            row["ability_applied"] = applied
        by_type.append(row)

    data = {
        "generation": gen,
        "types": defending,
        "basic": {"by_type": by_type, **_buckets(by_type, "multiplier")},
    }
    if modifiers:
        data["ability"] = {
            "ability": ability,
            "modifiers": modifiers,
            **_buckets(by_type, "ability_multiplier"),
        }
    elif ability and ability_supported:
        data["ability"] = {
            "ability": ability,
            "modifiers": [],
            "note": f"'{ability}' has no reviewed type modifier, so the basic profile stands unchanged. That is not a claim that the ability does nothing.",
        }
    elif ability:
        data["ability"] = {"ability": ability, "modifiers": [], "note": f"{scope.slug} has no Abilities as a mechanic."}
    return data
