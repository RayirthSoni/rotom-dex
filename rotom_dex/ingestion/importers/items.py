"""Items, per-generation presence, per-version-group data (flavor text, prices), machines."""

from __future__ import annotations

import re
from collections import defaultdict

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context

MACHINE = re.compile(r"^(tm|hm|tr)(\d+)$")


def run(ctx: Context) -> None:
    c, w, ev = ctx.cache, ctx.w, ctx.ev
    names = ctx.english("item_names", "item_id")
    categories = {int(r["id"]): r for r in c.rows("item_categories")}
    pockets = {int(r["id"]): r["identifier"] for r in c.rows("item_pockets")}
    seen: dict[str, int] = {}
    ctx.item_slug_collisions: list[tuple[int, str]] = []
    for iid, r in sorted(ctx.items.items()):
        category = categories[int(r["category_id"])]
        slug = r["identifier"]
        if slug in seen:  # The source has duplicate identifiers (e.g. two roseli-berry rows).
            ctx.item_slug_collisions.append((iid, slug))
            slug = f"{slug}-{iid}"
        seen[slug] = iid
        w.add(
            m.Item(
                iid,
                slug,
                names.get(iid, r["identifier"]),
                category["identifier"],
                pockets[int(category["pocket_id"])],
                int(r["cost"]) if r["cost"] else None,
                int(r["fling_power"]) if r["fling_power"] else None,
                ev(("items", f"id={iid}")),
            )
        )
    for r in c.rows("item_game_indices"):
        iid = int(r["item_id"])
        if iid not in ctx.items:
            continue
        w.add(
            m.ItemGeneration(
                iid,
                int(r["generation_id"]),
                int(r["game_index"]),
                ev(("item_game_indices", f"item_id={iid}")),
            )
        )
    for r in c.rows("item_prose"):
        if r["local_language_id"] == "9" and int(r["item_id"]) in ctx.items:
            iid = int(r["item_id"])
            w.add(
                m.ItemEffect(
                    iid,
                    r["short_effect"],
                    r["effect"],
                    "current",
                    ev(("item_prose", f"item_id={iid}; local_language_id=9")),
                )
            )
    flags = {int(r["id"]): r["identifier"] for r in c.rows("item_flags")}
    for r in c.rows("item_flag_map"):
        iid = int(r["item_id"])
        if iid not in ctx.items:
            continue
        w.add(m.ItemAttribute(iid, flags[int(r["item_flag_id"])], ev(("item_flag_map", f"item_id={iid}"))))
    w.flush()

    flavor = defaultdict(dict)
    for r in c.rows("item_flavor_text"):
        if r["language_id"] == "9":
            flavor[int(r["version_group_id"])][int(r["item_id"])] = " ".join(r["flavor_text"].split())
    prices = defaultdict(dict)
    for r in c.rows("item_prices"):
        if r["currency_id"] == "1":
            prices[int(r["version_group_id"])][int(r["item_id"])] = r
    ctx.item_game_data: set[tuple[int, int]] = set()
    for info in ctx.version_groups.values():
        src, gen = info.source_id, info.generation_id
        for iid, r in ctx.items.items():
            if gen not in ctx.item_generations[iid]:
                continue
            price = prices[src].get(iid)
            cost = int(r["cost"]) if r["cost"] else 0
            if price is not None:
                purchase = int(price["purchase_price"]) if price["purchase_price"] else None
                sell = int(price["sell_price"]) if price["sell_price"] else None
                provenance = "version-group"
            elif cost > 0:
                purchase, sell, provenance = cost, None, "default-cost"
            else:
                purchase, sell, provenance = None, None, "unknown"
            w.add(
                m.ItemGameData(
                    iid,
                    info.id,
                    flavor[src].get(iid),
                    purchase,
                    sell,
                    provenance,
                    ev(
                        ("item_game_indices", f"item_id={iid}; generation_id={gen}"),
                        (
                            "item_flavor_text",
                            f"item_id={iid}; version_group_id={src}; language_id=9",
                        ),
                        ("item_prices", f"item_id={iid}; version_group_id={src}"),
                        ("items", f"id={iid}; cost as default price"),
                        ctx.normalizer_ref,
                    ),
                )
            )
            ctx.item_game_data.add((iid, info.id))
    w.flush()

    ctx.machines: dict[int, dict[int, int]] = defaultdict(dict)  # vg -> item -> move
    for r in c.rows("machines"):
        src = int(r["version_group_id"])
        for info in ctx.version_groups.values():
            if info.source_id != src:
                continue
            iid, mid = int(r["item_id"]), int(r["move_id"])
            match = MACHINE.match(ctx.items[iid]["identifier"])
            if not match:
                raise ValueError(f"Machine item {iid} has an unexpected identifier")
            if (mid, info.id) not in ctx.move_game_data:
                continue
            w.add(
                m.Machine(
                    info.id,
                    int(match.group(2)),
                    match.group(1),
                    iid,
                    mid,
                    ev(("machines", f"version_group_id={src}; item_id={iid}")),
                )
            )
            ctx.machines[info.id][iid] = mid
    w.flush()
