"""Moves, effects, meta, flags and per-version-group move data (rewound history)."""

from __future__ import annotations

from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context
from rotom_dex.ingestion.historical import damage_class, rewind_move

DAMAGE_CLASSES = {"1": "status", "2": "physical", "3": "special"}


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    names = ctx.english("move_names", "move_id")
    targets = {int(r["id"]): r["identifier"] for r in c.rows("move_targets")}
    ctx.move_ids = {mid for mid, r in ctx.moves.items() if int(r["type_id"]) in ctx.types}
    ctx.skipped_moves = sorted(set(ctx.moves) - ctx.move_ids)
    for mid in sorted(ctx.move_ids):
        r = ctx.moves[mid]
        w.add(
            m.Move(
                mid,
                r["identifier"],
                names.get(mid, r["identifier"]),
                int(r["generation_id"]),
                ev(("moves", f"id={mid}")),
            )
        )
    effect_ids = {int(r["id"]) for r in c.rows("move_effects")}
    for r in c.rows("move_effect_prose"):
        if r["local_language_id"] == "9" and int(r["move_effect_id"]) in effect_ids:
            eid = int(r["move_effect_id"])
            w.add(
                m.MoveEffect(
                    eid,
                    r["short_effect"],
                    r["effect"],
                    "current",
                    ev(("move_effect_prose", f"move_effect_id={eid}; local_language_id=9")),
                )
            )
    categories = {int(r["id"]): r["identifier"] for r in c.rows("move_meta_categories")}
    ailments = {int(r["id"]): r["identifier"] for r in c.rows("move_meta_ailments")}
    for r in c.rows("move_meta"):
        mid = int(r["move_id"])
        if mid not in ctx.move_ids:
            continue
        opt = {k: (int(r[k]) if r[k] else None) for k in ("min_hits", "max_hits", "min_turns", "max_turns")}
        w.add(
            m.MoveMeta(
                mid,
                categories[int(r["meta_category_id"])],
                ailments[int(r["meta_ailment_id"])],
                opt["min_hits"],
                opt["max_hits"],
                opt["min_turns"],
                opt["max_turns"],
                int(r["drain"]),
                int(r["healing"]),
                int(r["crit_rate"]),
                int(r["ailment_chance"]),
                int(r["flinch_chance"]),
                int(r["stat_chance"]),
                ev(("move_meta", f"move_id={mid}")),
            )
        )
    flags = {int(r["id"]): r["identifier"] for r in c.rows("move_flags")}
    for r in c.rows("move_flag_map"):
        mid = int(r["move_id"])
        if mid in ctx.move_ids:
            w.add(m.MoveFlag(mid, flags[int(r["move_flag_id"])], ev(("move_flag_map", f"move_id={mid}"))))
    w.flush()

    changes = defaultdict(list)
    for r in c.rows("move_changelog"):
        changes[int(r["move_id"])].append(r)
    prose_effects = {
        int(r["move_effect_id"]) for r in c.rows("move_effect_prose") if r["local_language_id"] == "9"
    } & effect_ids
    ctx.move_game_data: set[tuple[int, int]] = set()
    for info in ctx.version_groups.values():
        order = ctx.group_order[info.source_id]
        gen = info.generation_id
        for mid in sorted(ctx.move_ids):
            move = ctx.moves[mid]
            if int(move["generation_id"]) > gen:
                continue
            r = rewind_move(move, changes[mid], ctx.group_order, order)
            tid = int(r["type_id"])
            if tid not in ctx.types:
                continue
            cls = damage_class(
                gen,
                DAMAGE_CLASSES[r["damage_class_id"]],
                DAMAGE_CLASSES.get(ctx.types[tid]["damage_class_id"]),
            )
            effect = int(r["effect_id"]) if r["effect_id"] else None
            w.add(
                m.MoveGameData(
                    mid,
                    info.id,
                    tid,
                    cls,
                    int(r["power"] or 0) or None,  # 0/empty mean "no power"
                    int(r["accuracy"] or 0) or None,  # 0/empty mean "no accuracy check"
                    int(r["pp"]) if r["pp"] else None,
                    int(r["priority"] or 0),
                    targets[int(r["target_id"])],
                    effect if effect in prose_effects else None,
                    int(r["effect_chance"]) if r["effect_chance"] else None,
                    ev(
                        ("moves", f"id={mid}"),
                        (
                            "move_changelog",
                            f"move_id={mid}; entries after the target version group rewound",
                        ),
                        ("types", "damage class from type before Generation IV"),
                        ctx.normalizer_ref,
                    ),
                )
            )
            ctx.move_game_data.add((mid, info.id))
    w.flush()
    source_to_targets = defaultdict(list)
    for info in ctx.version_groups.values():
        source_to_targets[info.source_id].append(info.id)
    for r in c.rows("move_flavor_text"):
        if r["language_id"] != "9":
            continue
        mid = int(r["move_id"])
        for vg in source_to_targets.get(int(r["version_group_id"]), ()):
            if (mid, vg) in ctx.move_game_data:
                w.add(
                    m.MoveFlavorText(
                        mid,
                        vg,
                        " ".join(r["flavor_text"].split()),
                        ev(
                            (
                                "move_flavor_text",
                                f"move_id={mid}; version_group_id={r['version_group_id']}; language_id=9",
                            )
                        ),
                    )
                )
    w.flush()
