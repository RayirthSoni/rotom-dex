"""Reviewed ability type effects: the arithmetic half of what an ability does defensively.

Rows are written per generation, like `type_effectiveness`, because a modifier's starting generation
is not always the ability's introduction. Abilities the vocabulary cannot express are recorded as
data issues so the omission is explicit rather than silent.
"""

from __future__ import annotations

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context

FEATURE = "ability-type-effects"


def run(ctx: Context) -> None:
    pack = ctx.ability_effects
    if pack is None:
        return
    w, db = ctx.w, ctx.w.db
    w.flush()  # abilities, types and generations must exist before we resolve slugs
    abilities = {r[0]: r[1] for r in db.execute("SELECT slug, id FROM abilities")}
    types = {r[0]: r[1] for r in db.execute("SELECT slug, id FROM types")}
    type_generation = {r[0]: r[1] for r in db.execute("SELECT slug, generation_id FROM types")}
    ability_generation = {r[0]: r[1] for r in db.execute("SELECT slug, generation_id FROM abilities")}

    pack_ref = ("ability-type-effects", "data/mechanics/ability_type_effects.json; reviewed modifiers")
    for slug, entry in pack.abilities.items():
        ability_id = abilities.get(slug)
        if ability_id is None:
            raise ValueError(f"Ability type effects name unknown ability '{slug}'")
        refs = [pack_ref, *((f"ref:ability-type-effects:{r}", f"ability={slug}") for r in entry["references"])]
        evidence = ctx.ev(*refs)
        for generation in sorted(ctx.generations):
            if generation < entry["since_generation"] or generation < ability_generation[slug]:
                continue
            for effect in entry["effects"]:
                type_slug = effect.get("type")
                type_id = None
                if type_slug is not None:
                    type_id = types.get(type_slug)
                    if type_id is None:
                        raise ValueError(f"Ability type effects name unknown type '{type_slug}'")
                    if type_generation[type_slug] > generation:
                        continue  # the attacking type does not exist yet in this generation
                w.add(
                    m.AbilityTypeEffect(
                        f"{slug}:{generation}:{effect['applies_to']}:{type_slug or '*'}",
                        ability_id,
                        generation,
                        effect["applies_to"],
                        type_id,
                        effect["damage_factor"],
                        effect.get("note", ""),
                        pack.review_status,
                        evidence,
                    )
                )

    for item in pack.excluded:
        w.add(
            m.DataIssue(
                f"ability-type-effects:{item['ability']}",
                None,
                FEATURE,
                f"ability:{item['ability']}",
                "missing",
                f"{item['ability']} is not modelled as a type modifier: {item['reason']}",
                ctx.ev(pack_ref),
            )
        )

    w.flush()  # coverage counts these rows straight from the table
