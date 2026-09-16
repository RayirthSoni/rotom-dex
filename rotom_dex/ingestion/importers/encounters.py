"""Exact-version acquisition: encounters, held items, derived evolution and breeding routes."""

from __future__ import annotations

from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.domain.conditions import all_of, unknown
from rotom_dex.ingestion.context import Context

PROGRESSION_UNKNOWN = unknown(
    "Progression gates, access requirements and one-time restrictions have not been reviewed."
)
BREEDING_UNKNOWN = unknown(
    "Day Care/Nursery access, a compatible partner and Ditto availability have not been reviewed."
)


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    slots = c.index("encounter_slots")
    methods = {int(r["id"]): r["identifier"] for r in c.rows("encounter_methods")}
    values = {int(r["id"]): r["identifier"] for r in c.rows("encounter_condition_values")}
    condition_map = defaultdict(list)
    for r in c.rows("encounter_condition_value_map"):
        condition_map[int(r["encounter_id"])].append(values[int(r["encounter_condition_value_id"])])
    games = {g.id: g for g in ctx.games}
    for r in c.rows("location_area_encounter_rates"):
        game = int(r["version_id"])
        if game in games:
            aid = int(r["location_area_id"])
            w.add(
                m.EncounterRate(
                    aid,
                    methods[int(r["encounter_method_id"])],
                    game,
                    int(r["rate"]),
                    ev(
                        (
                            "location_area_encounter_rates",
                            f"location_area_id={aid}; version_id={game}",
                        )
                    ),
                )
            )
    ctx.encounter_counts: dict[int, int] = defaultdict(int)
    ctx.special_method_counts: dict[int, int] = defaultdict(int)
    for r in c.rows("encounters"):
        game = int(r["version_id"])
        if game not in games:
            continue
        eid, pid, aid = int(r["id"]), int(r["pokemon_id"]), int(r["location_area_id"])
        slot = slots[int(r["encounter_slot_id"])]
        area = ctx.location_areas[aid]
        location = ctx.locations[int(area["location_id"])]
        method = methods[int(slot["encounter_method_id"])]
        conditions = condition_map.get(eid)
        encounter_conditions = (
            {
                "op": "and",
                "args": [{"op": "encounter_condition", "value": v} for v in sorted(conditions)],
            }
            if conditions
            else {"op": "always"}
        )
        w.add(
            m.Acquisition(
                f"encounter:{game}:{eid}",
                game,
                pid,
                None,
                int(location["id"]),
                aid,
                method,
                int(r["min_level"]),
                int(r["max_level"]),
                int(slot["rarity"]) if slot["rarity"] else None,
                "unknown",
                all_of({"op": "at_location", "value": location["identifier"]}, PROGRESSION_UNKNOWN),
                encounter_conditions,
                m.SOURCE_DERIVED,
                "",
                ev(
                    ("encounters", f"version_id={game}; location_area_id={aid}"),
                    ("encounter_slots", f"version_group_id={slot['version_group_id']}"),
                    ("encounter_condition_value_map", "condition values per encounter id"),
                    ctx.normalizer_ref,
                ),
            )
        )
        ctx.encounter_counts[game] += 1
        if method in ("gift", "gift-egg", "npc-trade", "static"):
            ctx.special_method_counts[game] += 1
    w.flush()
    ctx.held_item_counts: dict[int, int] = defaultdict(int)
    for r in c.rows("pokemon_items"):
        game = int(r["version_id"])
        if game in games:
            pid, iid = int(r["pokemon_id"]), int(r["item_id"])
            w.add(
                m.PokemonHeldItem(
                    pid,
                    game,
                    iid,
                    int(r["rarity"]),
                    ev(("pokemon_items", f"pokemon_id={pid}; version_id={game}")),
                )
            )
            ctx.held_item_counts[game] += 1
    w.flush()

    # Derived evolution routes: the evolved form is obtainable by evolving a pre-evolution.
    for game in ctx.games:
        vg = game.version_group_id
        for rid, rule in ctx.evolution_rules.items():
            if ctx.applicability.get((rid, vg)) != "applies":
                continue
            origin = ctx.pokemon[rule.from_form_id]["identifier"]
            w.add(
                m.Acquisition(
                    f"evolution:{game.id}:{rid}",
                    game.id,
                    rule.to_form_id,
                    None,
                    None,
                    None,
                    "evolution",
                    None,
                    None,
                    None,
                    "unknown",
                    all_of({"op": "has_pokemon", "value": origin}, rule.conditions),
                    {"op": "always"},
                    m.SOURCE_DERIVED,
                    "Derived from an evolution rule whose applicability is not reviewed.",
                    rule.evidence_id,
                )
            )
    w.flush()

    # Derived breeding routes where the game has breeding.
    egg_groups = defaultdict(set)
    for r in c.rows("pokemon_egg_groups"):
        egg_groups[int(r["species_id"])].add(int(r["egg_group_id"]))
    no_eggs = {int(r["id"]) for r in c.rows("egg_groups") if r["identifier"] == "no-eggs"}
    chains = defaultdict(list)
    for sid, s in ctx.species.items():
        chains[int(s["evolution_chain_id"])].append(sid)
    baby_item = {
        int(r["id"]): (int(r["baby_trigger_item_id"]) if r["baby_trigger_item_id"] else None)
        for r in c.rows("evolution_chains")
    }
    default_of = ctx.default_form_of_species
    ctx.breeding_counts: dict[int, int] = defaultdict(int)
    for game in ctx.games:
        vg = game.version_group_id
        if ctx.mechanic(vg, "breeding") != 1:
            continue
        evidence = ev(
            ("pokemon_egg_groups", "egg group membership"),
            ("pokemon_species", "evolves_from_species_id, evolution_chain_id, is_baby"),
            ("evolution_chains", "baby_trigger_item_id"),
            ("ref:mechanics:breeding", "breeding present in this version group"),
            ctx.normalizer_ref,
        )
        for sid, s in ctx.species.items():
            if s["evolves_from_species_id"] or egg_groups[sid] & no_eggs or not egg_groups[sid]:
                continue
            pid = default_of[sid]
            if (pid, vg) not in ctx.present:
                continue
            chain = int(s["evolution_chain_id"])
            family = [
                ctx.pokemon[default_of[x]]["identifier"]
                for x in sorted(chains[chain])
                if (default_of[x], vg) in ctx.present
            ]
            parents = (
                {"op": "or", "args": [{"op": "has_pokemon", "value": f} for f in family]}
                if len(family) > 1
                else {"op": "has_pokemon", "value": family[0]}
            )
            conds = [parents]
            incense = baby_item.get(chain)
            if s["is_baby"] == "1" and incense:
                conds.append({"op": "held_item", "value": ctx.items[incense]["identifier"]})
            conds.append(BREEDING_UNKNOWN)
            w.add(
                m.Acquisition(
                    f"breeding:{game.id}:{pid}",
                    game.id,
                    pid,
                    None,
                    None,
                    None,
                    "breeding",
                    1,
                    1,
                    None,
                    "unknown",
                    all_of(*conds),
                    {"op": "always"},
                    m.SOURCE_DERIVED,
                    "Derived from egg groups and evolution family; hatch level and facility not reviewed.",
                    evidence,
                )
            )
            ctx.breeding_counts[game.id] += 1
    w.flush()
