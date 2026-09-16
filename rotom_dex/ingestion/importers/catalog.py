"""Global catalogs: generations, version groups, games, regions, types, type charts,
natures, locations and Pokédexes."""

from __future__ import annotations

from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import STAT_SLUGS, Context
from rotom_dex.ingestion.historical import historical

EXPECTED_CHART = {1: 15 * 15}  # other generations: 17x17 (2-5) and 18x18 (6+)


def expected_type_count(generation: int) -> int:
    return 15 if generation == 1 else 17 if generation <= 5 else 18


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    gen_names = ctx.english("generation_names", "generation_id")
    for gid, r in c.index("generations").items():
        w.add(
            m.Generation(
                gid,
                r["identifier"],
                gen_names.get(gid, r["identifier"]),
                ev(("generations", f"id={gid}")),
            )
        )
    region_names = ctx.english("region_names", "region_id")
    for rid, r in c.index("regions").items():
        w.add(
            m.Region(
                rid,
                r["identifier"],
                region_names.get(rid, r["identifier"]),
                ev(("regions", f"id={rid}")),
            )
        )
    for gid, g in ctx.all_groups.items():
        w.add(
            m.VersionGroup(
                gid,
                g["identifier"],
                g["identifier"],
                int(g["generation_id"]),
                int(g["order"]),
                ev(("version_groups", f"id={gid}")),
            )
        )
    for r in c.rows("version_group_regions"):
        w.add(m.VersionGroupRegion(int(r["version_group_id"]), int(r["region_id"])))
    version_names = ctx.english("version_names", "version_id")
    for game in ctx.registry.games.values():
        w.add(
            m.GameVersion(
                game.id,
                game.slug,
                version_names.get(game.id, game.slug),
                game.version_group_id,
                game.is_main_series,
                game.tier,
                game.note,
                ev(("versions", f"id={game.id}"), ctx.registry_ref),
            )
        )
    type_names = ctx.english("type_names", "type_id")
    for tid, r in ctx.types.items():
        w.add(
            m.Type(
                tid,
                r["identifier"],
                type_names.get(tid, r["identifier"]),
                int(r["generation_id"]),
                ev(("types", f"id={tid}")),
            )
        )
    past = defaultdict(list)
    for r in c.rows("type_efficacy_past"):
        past[(int(r["damage_type_id"]), int(r["target_type_id"]))].append(r)
    for gen in sorted(ctx.generations):
        evidence = ev(
            ("type_efficacy", "all damage/target pairs"),
            ("type_efficacy_past", f"nearest generation_id >= {gen}"),
            ctx.normalizer_ref,
        )
        present = {tid for tid, r in ctx.types.items() if int(r["generation_id"]) <= gen}
        count = 0
        for r in c.rows("type_efficacy"):
            a, d = int(r["damage_type_id"]), int(r["target_type_id"])
            if a not in present or d not in present:
                continue
            applicable = [p for p in past[(a, d)] if int(p["generation_id"]) >= gen]
            value = min(applicable, key=lambda p: int(p["generation_id"])) if applicable else r
            w.add(m.TypeEffectiveness(gen, a, d, int(value["damage_factor"]), evidence))
            count += 1
        if count != expected_type_count(gen) ** 2:
            raise ValueError(f"Type chart for generation {gen} has {count} pairs")
    nature_names = ctx.english("nature_names", "nature_id")
    for nid, r in c.index("natures").items():
        w.add(
            m.Nature(
                nid,
                r["identifier"],
                nature_names.get(nid, r["identifier"]),
                STAT_SLUGS[int(r["increased_stat_id"])],
                STAT_SLUGS[int(r["decreased_stat_id"])],
                None,
                None,
                ev(("natures", f"id={nid}")),
            )
        )
    location_names = ctx.english("location_names", "location_id")
    for lid, r in ctx.locations.items():
        w.add(
            m.Location(
                lid,
                int(r["region_id"]) if r["region_id"] else None,
                r["identifier"],
                location_names.get(lid, r["identifier"]),
                ev(("locations", f"id={lid}")),
            )
        )
    area_names = ctx.english("location_area_prose", "location_area_id")
    for aid, r in ctx.location_areas.items():
        location = ctx.locations[int(r["location_id"])]
        slug = r["identifier"] or "default"
        w.add(
            m.LocationArea(
                aid,
                int(r["location_id"]),
                slug,
                area_names.get(aid) or location_names.get(int(r["location_id"]), slug),
                ev(("location_areas", f"id={aid}"), ("locations", f"id={location['id']}")),
            )
        )
    dex_names = ctx.english("pokedex_prose", "pokedex_id")
    for did, r in c.index("pokedexes").items():
        w.add(
            m.Pokedex(
                did,
                r["identifier"],
                dex_names.get(did, r["identifier"]),
                int(r["region_id"]) if r["region_id"] else None,
                r["is_main_series"] == "1",
                ev(("pokedexes", f"id={did}")),
            )
        )
    for r in c.rows("pokedex_version_groups"):
        w.add(m.PokedexVersionGroup(int(r["pokedex_id"]), int(r["version_group_id"])))
    w.flush()


__all__ = ["run", "historical", "expected_type_count", "EXPECTED_CHART"]
