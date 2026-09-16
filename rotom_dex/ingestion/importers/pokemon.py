"""Species, forms, variants, Pokédex numbers, egg groups and per-generation battle data."""

from __future__ import annotations

from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import STAT_SLUGS, Context
from rotom_dex.ingestion.historical import historical

GEN1_STATS = {1, 2, 3, 6, 9}
MODERN_STATS = {1, 2, 3, 4, 5, 6}
FIRST_ABILITY_GENERATION = 3
FIRST_HIDDEN_ABILITY_GENERATION = 5


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    species_names = ctx.english("pokemon_species_names", "pokemon_species_id")
    growth = {int(r["id"]): r["identifier"] for r in c.rows("growth_rates")}
    for sid, s in ctx.species.items():
        w.add(
            m.Species(
                sid,
                s["identifier"],
                species_names.get(sid, s["identifier"]),
                int(s["generation_id"]),
                int(s["evolves_from_species_id"]) if s["evolves_from_species_id"] else None,
                int(s["evolution_chain_id"]) if s["evolution_chain_id"] else None,
                int(s["gender_rate"]) if s["gender_rate"] else None,
                int(s["capture_rate"]) if s["capture_rate"] else None,
                int(s["base_happiness"]) if s["base_happiness"] else None,
                int(s["hatch_counter"]) if s["hatch_counter"] else None,
                growth.get(int(s["growth_rate_id"])) if s["growth_rate_id"] else None,
                s["is_baby"] == "1",
                s["is_legendary"] == "1",
                s["is_mythical"] == "1",
                ev(("pokemon_species", f"id={sid}")),
            )
        )
    variant_names = {}
    for r in c.rows("pokemon_form_names"):
        if r["local_language_id"] == "9":
            variant_names[int(r["pokemon_form_id"])] = (r["form_name"], r["pokemon_name"])
    default_variant = {}
    for vid, v in ctx.form_variants.items():
        if v["is_default"] == "1":
            default_variant[int(v["pokemon_id"])] = vid
    for pid, p in ctx.pokemon.items():
        sid = int(p["species_id"])
        species_name = species_names.get(sid, ctx.species[sid]["identifier"])
        variant = default_variant.get(pid)
        pokemon_name = variant_names.get(variant, ("", ""))[1] if variant else ""
        name = species_name if p["is_default"] == "1" else (pokemon_name or p["identifier"])
        w.add(
            m.PokemonForm(
                pid,
                sid,
                p["identifier"],
                name,
                p["is_default"] == "1",
                int(p["height"]) if p["height"] else None,
                int(p["weight"]) if p["weight"] else None,
                int(p["base_experience"]) if p["base_experience"] else None,
                int(p["order"]) if p["order"] else None,
                ev(("pokemon", f"id={pid}"), ("pokemon_species", f"id={sid}")),
            )
        )
    for vid, v in ctx.form_variants.items():
        w.add(
            m.FormVariant(
                vid,
                int(v["pokemon_id"]),
                v["identifier"],
                variant_names.get(vid, ("", ""))[0],
                v["is_default"] == "1",
                v["is_mega"] == "1",
                v["is_battle_only"] == "1",
                int(v["introduced_in_version_group_id"]) if v["introduced_in_version_group_id"] else None,
                ev(("pokemon_forms", f"id={vid}")),
            )
        )
    egg_groups = {int(r["id"]): r["identifier"] for r in c.rows("egg_groups")}
    for r in c.rows("pokemon_egg_groups"):
        sid = int(r["species_id"])
        w.add(
            m.PokemonEggGroup(
                sid,
                egg_groups[int(r["egg_group_id"])],
                ev(("pokemon_egg_groups", f"species_id={sid}")),
            )
        )
    for r in c.rows("pokemon_dex_numbers"):
        sid = int(r["species_id"])
        w.add(
            m.PokemonDexNumber(
                sid,
                int(r["pokedex_id"]),
                int(r["pokedex_number"]),
                ev(("pokemon_dex_numbers", f"species_id={sid}")),
            )
        )
    w.flush()

    ability_names = ctx.english("ability_names", "ability_id")
    for aid, a in ctx.abilities.items():
        w.add(
            m.Ability(
                aid,
                a["identifier"],
                ability_names.get(aid, a["identifier"]),
                int(a["generation_id"]),
                a["is_main_series"] == "1",
                ev(("abilities", f"id={aid}")),
            )
        )
    for r in c.rows("ability_prose"):
        if r["local_language_id"] == "9" and int(r["ability_id"]) in ctx.abilities:
            aid = int(r["ability_id"])
            w.add(
                m.AbilityEffect(
                    aid,
                    r["short_effect"],
                    r["effect"],
                    "current",
                    ev(("ability_prose", f"ability_id={aid}; local_language_id=9")),
                )
            )
    source_to_targets = defaultdict(list)
    for info in ctx.version_groups.values():
        source_to_targets[info.source_id].append(info.id)
    for r in c.rows("ability_flavor_text"):
        if r["language_id"] != "9":
            continue
        for vg in source_to_targets.get(int(r["version_group_id"]), ()):
            aid = int(r["ability_id"])
            w.add(
                m.AbilityFlavorText(
                    aid,
                    vg,
                    " ".join(r["flavor_text"].split()),
                    ev(
                        (
                            "ability_flavor_text",
                            f"ability_id={aid}; version_group_id={r['version_group_id']}; language_id=9",
                        )
                    ),
                )
            )
    changelog = {int(r["id"]): r for r in c.rows("ability_changelog")}
    for r in c.rows("ability_changelog_prose"):
        if r["local_language_id"] == "9":
            entry = changelog[int(r["ability_changelog_id"])]
            w.add(
                m.AbilityChange(
                    int(entry["ability_id"]),
                    int(entry["changed_in_version_group_id"]),
                    r["effect"],
                    ev(
                        ("ability_changelog", f"id={entry['id']}"),
                        ("ability_changelog_prose", f"id={entry['id']}; en"),
                    ),
                )
            )
    w.flush()

    now = {name: defaultdict(list) for name in ("pokemon_types", "pokemon_stats", "pokemon_abilities")}
    past = {name: defaultdict(list) for name in now}
    for name in now:
        for r in c.rows(name):
            now[name][int(r["pokemon_id"])].append(r)
        for r in c.rows(name + "_past"):
            past[name][int(r["pokemon_id"])].append(r)
    intro = ctx.form_intro_generation
    ctx.ability_gaps = []
    ctx.missing_abilities = []
    for gen in sorted(ctx.generations):
        for pid in sorted(ctx.pokemon):
            if intro[pid] > gen:
                continue
            evidence = {
                name: ev(
                    (name, f"pokemon_id={pid}"),
                    (name + "_past", f"pokemon_id={pid}; nearest generation_id >= {gen}"),
                    ctx.normalizer_ref,
                )
                for name in now
            }
            for r in historical(now["pokemon_types"][pid], past["pokemon_types"][pid], gen, ()):
                tid = int(r["type_id"])
                if tid in ctx.types:
                    w.add(m.PokemonType(pid, gen, int(r["slot"]), tid, evidence["pokemon_types"]))
            wanted = GEN1_STATS if gen == 1 else MODERN_STATS
            for r in historical(now["pokemon_stats"][pid], past["pokemon_stats"][pid], gen, ("stat_id",)):
                stat_id = int(r["stat_id"])
                if stat_id in wanted:
                    w.add(
                        m.PokemonStat(
                            pid,
                            gen,
                            STAT_SLUGS[stat_id],
                            int(r["base_stat"]),
                            int(r["effort"] or 0),
                            evidence["pokemon_stats"],
                        )
                    )
            if gen < FIRST_ABILITY_GENERATION:
                continue
            added = 0
            for r in historical(now["pokemon_abilities"][pid], past["pokemon_abilities"][pid], gen, ("slot",)):
                if not r["ability_id"]:
                    continue  # An empty historical ability removes the slot.
                aid = int(r["ability_id"])
                hidden = r["is_hidden"] == "1"
                if hidden and gen < FIRST_HIDDEN_ABILITY_GENERATION:
                    continue  # Hidden abilities did not exist; the source keeps the modern slot.
                if int(ctx.abilities[aid]["generation_id"]) > gen:
                    # The ability itself did not exist yet and the history table has no entry for
                    # this slot: the slot is dropped and the gap is reported as a data issue.
                    ctx.ability_gaps.append((pid, gen, int(r["slot"]), aid))
                    continue
                w.add(m.PokemonAbility(pid, gen, int(r["slot"]), aid, hidden, evidence["pokemon_abilities"]))
                added += 1
            if not added:
                ctx.missing_abilities.append((pid, gen))
        w.flush()
