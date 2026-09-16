"""Types and type effectiveness for an exact game."""

from __future__ import annotations

from rotom_dex.calculators import type_effectiveness as calc
from rotom_dex.repositories.common import envelope, resolve_game, rows, unsupported


def list_types(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    types = rows(
        db,
        "SELECT id, slug, name, generation_id, evidence_id FROM types WHERE generation_id<=? ORDER BY id",
        (scope.generation_id,),
    )
    return envelope(db, scope, types, features=("type-effectiveness",))


def chart(db, game: str) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    return envelope(
        db,
        scope,
        {"generation": scope.generation_id, "pairs": calc.chart(db, scope.generation_id)},
        features=("type-effectiveness",),
        include_evidence=False,
    )


def matchup(db, game: str, attack: str, defense: str, defense2: str | None) -> dict:
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    gen = scope.generation_id
    attack_id = calc.type_id(db, attack, gen)
    defense_ids = [calc.type_id(db, defense, gen)]
    if defense2:
        defense_ids.append(calc.type_id(db, defense2, gen))
    result = calc.factor(db, gen, attack_id, defense_ids)
    data = {
        "generation": gen,
        "attack": attack.lower(),
        "defenses": [defense.lower()] + ([defense2.lower()] if defense2 else []),
        **result,
    }
    return envelope(
        db,
        scope,
        data,
        features=("type-effectiveness",),
        assumptions=["Type matchups only; abilities, items and move-specific interactions are not applied."],
    )
