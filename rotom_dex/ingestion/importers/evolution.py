"""Evolution rules as typed conditions, plus derived per-version-group applicability."""

from __future__ import annotations

from rotom_dex.domain import models as m
from rotom_dex.domain.conditions import all_of, unknown
from rotom_dex.ingestion.context import Context

RELATIVE = {"1": "attack>defense", "-1": "attack<defense", "0": "attack=defense"}
GENDERS = {"1": "female", "2": "male"}
MODELLED_TRIGGERS = {"level-up", "use-item", "trade"}


def translate(ctx: Context, r: dict, trigger: str) -> dict:
    conds: list[dict] = []
    if r["minimum_level"]:
        conds.append({"op": "level_at_least", "value": int(r["minimum_level"])})
    if r["trigger_item_id"]:
        conds.append({"op": "use_item", "value": ctx.items[int(r["trigger_item_id"])]["identifier"]})
    if r["held_item_id"]:
        conds.append({"op": "held_item", "value": ctx.items[int(r["held_item_id"])]["identifier"]})
    if r["gender_id"]:
        if r["gender_id"] in GENDERS:
            conds.append({"op": "gender", "value": GENDERS[r["gender_id"]]})
        else:
            conds.append(unknown("Gender requirement is not male/female"))
    if r["time_of_day"]:
        conds.append({"op": "time_of_day", "value": r["time_of_day"]})
    if r["known_move_id"]:
        conds.append({"op": "knows_move", "value": ctx.moves[int(r["known_move_id"])]["identifier"]})
    if r["known_move_type_id"]:
        conds.append({"op": "knows_move_type", "value": ctx.type_slugs[int(r["known_move_type_id"])]})
    for field, op in (
        ("minimum_happiness", "happiness_at_least"),
        ("minimum_beauty", "beauty_at_least"),
        ("minimum_affection", "affection_at_least"),
    ):
        if r[field]:
            conds.append({"op": op, "value": int(r[field])})
    if r["relative_physical_stats"]:
        conds.append({"op": "stat_relation", "value": RELATIVE[r["relative_physical_stats"]]})
    if r["party_species_id"]:
        conds.append(
            {
                "op": "party_has_pokemon",
                "value": ctx.species[int(r["party_species_id"])]["identifier"],
            }
        )
    if r["party_type_id"]:
        conds.append({"op": "party_has_type", "value": ctx.type_slugs[int(r["party_type_id"])]})
    if r["trade_species_id"]:
        conds.append(
            {
                "op": "trade_for_pokemon",
                "value": ctx.species[int(r["trade_species_id"])]["identifier"],
            }
        )
    elif trigger == "trade":
        conds.append({"op": "trade"})
    if r["needs_overworld_rain"] == "1":
        conds.append({"op": "overworld_rain"})
    if r["turn_upside_down"] == "1":
        conds.append({"op": "device_upside_down"})
    if r["location_id"]:
        conds.append({"op": "at_location", "value": ctx.locations[int(r["location_id"])]["identifier"]})
    if r["region_id"]:
        conds.append(
            {
                "op": "in_region",
                "value": ctx.cache.index("regions")[int(r["region_id"])]["identifier"],
            }
        )
    if r["near_special_rock"] == "1":
        conds.append(unknown("Must level up near a special rock (magnetic field, mossy or icy rock); the location differs between games."))
    if r["needs_multiplayer"] == "1":
        conds.append(unknown("Requires a multiplayer (Union Circle) session."))
    if r["used_move_id"] or r["minimum_move_count"]:
        conds.append(unknown("Requires using a specific move a number of times; not modelled."))
    if r["minimum_steps"]:
        conds.append(unknown("Requires walking a number of steps under a condition; not modelled."))
    if r["minimum_damage_taken"]:
        conds.append(unknown("Requires taking a minimum amount of damage; not modelled."))
    if r["nature_bitmask"]:
        conds.append(unknown("Depends on the Pokémon's Nature; not modelled."))
    if r["condition_expression"]:
        conds.append(unknown("Depends on the Pokémon's personality value; not modelled."))
    if r["percentage_chance"]:
        conds.append(unknown(f"Random outcome ({r['percentage_chance']}% chance)."))
    if trigger not in MODELLED_TRIGGERS:
        conds.append(unknown(f"Evolution trigger '{trigger}' requires reviewed handling."))
    return all_of(*conds)


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    triggers = {int(r["id"]): r["identifier"] for r in c.rows("evolution_triggers")}
    default_of = ctx.default_form_of_species
    rules: dict[int, dict] = {}
    for r in c.rows("pokemon_evolution"):
        rid, target = int(r["id"]), int(r["evolved_species_id"])
        origin_species = ctx.species[target]["evolves_from_species_id"]
        if not origin_species:
            raise ValueError(f"Evolution {rid}: target species {target} has no pre-evolution")
        to_form = int(ctx.form_variants[int(r["evolved_pokemon_form_id"])]["pokemon_id"]) if r["evolved_pokemon_form_id"] else default_of[target]
        from_form = int(ctx.form_variants[int(r["required_pokemon_form_id"])]["pokemon_id"]) if r["required_pokemon_form_id"] else default_of[int(origin_species)]
        trigger = triggers[int(r["evolution_trigger_id"])]
        conditions = translate(ctx, r, trigger)
        raw = {k: v for k, v in r.items() if v not in ("", "0")}
        vg = int(r["version_group_id"]) if r["version_group_id"] else None
        rule = m.EvolutionRule(
            rid,
            from_form,
            to_form,
            trigger,
            vg,
            conditions,
            raw,
            ev(
                ("pokemon_evolution", f"id={rid}"),
                ("pokemon_species", f"id={target}; evolves_from_species_id"),
                ctx.normalizer_ref,
            ),
        )
        w.add(rule)
        rules[rid] = {"rule": rule, "row": r}
    w.flush()
    ctx.evolution_rules = {rid: entry["rule"] for rid, entry in rules.items()}

    overrides: dict[tuple[int, int], tuple[dict, str]] = {}
    for game in ctx.games:
        pack = ctx.packs.get(game.slug)
        if not pack:
            continue
        for o in pack.evolution_overrides:
            key = (int(o["rule_id"]), game.version_group_id)
            if key in overrides and overrides[key][0]["status"] != o["status"]:
                raise ValueError(f"Conflicting evolution overrides for rule {key}")
            overrides[key] = (o, game.slug)
    ctx.applicability: dict[tuple[int, int], str] = {}
    derived = ev(
        ("pokemon_evolution", "version_group_id, location_id, region_id, trigger_item_id"),
        ("pokemon_game_indices", "presence of both forms"),
        ("item_game_indices", "trigger item generation"),
        ctx.normalizer_ref,
    )
    for info in ctx.version_groups.values():
        for rid, entry in rules.items():
            rule, row = entry["rule"], entry["row"]
            status, reason = derive(ctx, info, rule, row)
            verification = m.UNVERIFIED
            override = overrides.get((rid, info.id))
            if override:
                o, slug = override
                status, reason, verification = o["status"], o["reason"], m.REFERENCE_REVIEWED
                evidence = ev(
                    *[(f"ref:{slug}:{ref}", f"evolution rule {rid}") for ref in o["references"]],
                    (f"pack:{slug}", f"evolution_overrides rule_id={rid}"),
                )
            else:
                evidence = derived
            w.add(m.EvolutionApplicability(rid, info.id, status, reason, verification, evidence))
            ctx.applicability[(rid, info.id)] = status
    w.flush()


def derive(ctx: Context, info, rule: m.EvolutionRule, row: dict) -> tuple[str, str]:
    present = ctx.present
    if (rule.from_form_id, info.id) not in present or (rule.to_form_id, info.id) not in present:
        return "not-applicable", "One of the forms is absent from this version group's data."
    if rule.introduced_version_group_id is not None:
        if ctx.group_order[rule.introduced_version_group_id] > info.order:
            return "not-applicable", "Rule introduced in a later version group."
    if row["location_id"]:
        region = ctx.locations[int(row["location_id"])]["region_id"]
        if not region or int(region) not in info.region_ids:
            return "not-applicable", "Required location lies in a region this version group lacks."
    if row["region_id"] and int(row["region_id"]) not in info.region_ids:
        return "not-applicable", "Rule bound to a region this version group lacks."
    for field in ("trigger_item_id", "held_item_id"):
        if row[field] and info.generation_id not in ctx.item_generations[int(row[field])]:
            return "unknown", "Required item has no game index in this generation."
    return "applies", ("Derived: both forms present, rule not introduced later, location/region and item checks passed. Not reviewed against the game.")
