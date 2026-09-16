"""Per-version-group Pokémon presence and learnsets."""

from __future__ import annotations

from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    version_to_group = {g.id: g.version_group_id for g in ctx.games}
    source_to_targets = defaultdict(list)
    for info in ctx.version_groups.values():
        source_to_targets[info.source_id].append(info.id)
    present: set[tuple[int, int]] = set()
    presence_reason: dict[tuple[int, int], set[str]] = defaultdict(set)
    # The source's per-version game indices are reliable through Generation VII; for later
    # versions they repeat earlier lists, so presence there relies on learnsets and encounters.
    index_groups = {g.id: g.version_group_id for g in ctx.games if g.generation_id <= 7}
    for r in c.rows("pokemon_game_indices"):
        vg = index_groups.get(int(r["version_id"]))
        if vg is not None:
            key = (int(r["pokemon_id"]), vg)
            present.add(key)
            presence_reason[key].add("pokemon_game_indices")
    for r in c.rows("encounters"):
        vg = version_to_group.get(int(r["version_id"]))
        if vg is not None:
            key = (int(r["pokemon_id"]), vg)
            present.add(key)
            presence_reason[key].add("encounters")
    methods = {int(r["id"]): r["identifier"] for r in c.rows("pokemon_move_methods")}
    learnset_rows: list[tuple[int, int, int, str, int, int | None]] = []
    ctx.skipped_learnset_rows = 0
    for r in c.rows("pokemon_moves"):
        targets = source_to_targets.get(int(r["version_group_id"]))
        if not targets:
            continue
        pid, mid = int(r["pokemon_id"]), int(r["move_id"])
        method, level = methods[int(r["pokemon_move_method_id"])], int(r["level"])
        order = int(r["order"]) if r["order"] else None
        for vg in targets:
            if (mid, vg) not in ctx.move_game_data:
                ctx.skipped_learnset_rows += 1
                continue
            key = (pid, vg)
            present.add(key)
            presence_reason[key].add("pokemon_moves")
            learnset_rows.append((pid, vg, mid, method, level, order))
    # Non-default variants (megas, battle forms) inherit their species' presence as 'unknown'.
    intro_group = {}
    for v in ctx.form_variants.values():
        pid = int(v["pokemon_id"])
        if v["introduced_in_version_group_id"]:
            order = ctx.group_order[int(v["introduced_in_version_group_id"])]
            intro_group[pid] = min(intro_group.get(pid, 10**6), order)
    default_of = ctx.default_form_of_species
    for info in ctx.version_groups.values():
        evidence_present = ev(
            ("pokemon_game_indices", f"version_id in version group {info.id}"),
            ("pokemon_moves", f"version_group_id={info.source_id}"),
            ("encounters", f"version_id in version group {info.id}"),
            ctx.normalizer_ref,
        )
        evidence_unknown = ev(
            ("pokemon_forms", "introduced_in_version_group_id <= target group; species present"),
            ctx.normalizer_ref,
        )
        for pid, p in ctx.pokemon.items():
            key = (pid, info.id)
            if key in present:
                w.add(m.PokemonVersionGroup(pid, info.id, "present", evidence_present))
                continue
            species_default = default_of[int(p["species_id"])]
            if p["is_default"] != "1" and (species_default, info.id) in present and intro_group.get(pid, 10**6) <= ctx.group_order[info.id]:
                w.add(m.PokemonVersionGroup(pid, info.id, "unknown", evidence_unknown))
    w.flush()
    ctx.present = present
    by_group: dict[int, str] = {
        info.id: ev(
            (
                "pokemon_moves",
                f"version_group_id={info.source_id}" + ("; inherited by expansion group" if info.data_source_id else ""),
            )
        )
        for info in ctx.version_groups.values()
    }
    for pid, vg, mid, method, level, order in learnset_rows:
        w.add(m.LearnsetEntry(pid, vg, mid, method, level, order, by_group[vg]))
    w.flush()
