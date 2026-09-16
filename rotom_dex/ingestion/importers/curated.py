"""Mechanics flags and curated game-pack content (progression, bosses, shops, tutors, issues)."""

from __future__ import annotations

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context


def _status(entry: dict) -> str:
    status = entry.get("verification_status", m.REFERENCE_REVIEWED)
    if status not in m.VERIFICATION_STATUSES:
        raise ValueError(f"Bad verification_status {status}")
    return status


def run(ctx: Context) -> None:
    w, ev = ctx.w, ctx.ev
    # Mechanics per version group, with game-pack overrides.
    for info in ctx.version_groups.values():
        values = ctx.mechanics.values(info.slug)
        notes = {key: ctx.mechanics.status(info.slug, key) for key in values}
        evidence = {
            key: ev(
                (f"ref:mechanics:{key}", f"{info.slug}: {key}"),
                ("mechanics", f"version_groups.{info.slug}"),
            )
            for key in values
        }
        for game in info.games:
            pack = ctx.packs.get(game.slug)
            if not pack:
                continue
            for key, entry in pack.mechanics.items():
                if key in values and values[key] != entry["value"]:
                    raise ValueError(
                        f"Pack {game.slug} contradicts mechanics pack on {key}; resolve in the mechanics pack instead"
                    )
                values[key] = entry["value"]
                notes[key] = (_status(entry), entry.get("note", ""))
                evidence[key] = _pack_ev(ctx, game.slug, entry["references"], f"mechanics.{key}")
        for key, value in values.items():
            status, note = notes[key]
            w.add(m.GameMechanic(info.id, key, value, note, status, evidence[key]))
    w.flush()

    ctx.pack_counts: dict[int, dict[str, int]] = {}
    for game in ctx.games:
        pack = ctx.packs.get(game.slug)
        counts = {
            "milestones": 0,
            "battles": 0,
            "acquisitions": 0,
            "shops": 0,
            "tutors": 0,
            "issues": 0,
        }
        ctx.pack_counts[game.id] = counts
        if not pack:
            continue
        slug = game.slug
        milestone_ids = {}
        for ord_, ms in enumerate(pack.milestones, start=1):
            mid = f"{slug}:{ms['slug']}"
            milestone_ids[ms["slug"]] = mid
            w.add(
                m.Milestone(
                    mid,
                    game.id,
                    ms["slug"],
                    ms["name"],
                    ord_,
                    ms["kind"],
                    _location(ctx, ms.get("location")),
                    ms["prerequisites"],
                    ms.get("spoiler_level", "none"),
                    _status(ms),
                    _pack_ev(ctx, slug, ms["references"], f"milestones.{ms['slug']}"),
                )
            )
            counts["milestones"] += 1
        for b in pack.battles:
            bid = f"{slug}:{b['id']}"
            milestone = b.get("milestone")
            if milestone is not None and milestone not in milestone_ids:
                raise ValueError(f"Battle {bid} references unknown milestone {milestone}")
            evidence = _pack_ev(ctx, slug, b["references"], f"battles.{b['id']}")
            w.add(
                m.TrainerBattle(
                    bid,
                    game.id,
                    milestone_ids.get(milestone),
                    b["name"],
                    b["trainer_class"],
                    _location(ctx, b.get("location")),
                    b.get("prize_money"),
                    _status(b),
                    evidence,
                )
            )
            for slot, member in enumerate(b["party"], start=1):
                form = _slug(ctx.slug_to_pokemon, member["pokemon"], "pokemon")
                if (form, game.version_group_id) not in ctx.present:
                    raise ValueError(f"Battle {bid}: {member['pokemon']} is not present in this game")
                moves = member.get("moves")
                if moves:
                    for mv in moves:
                        if (
                            _slug(ctx.slug_to_move, mv, "move"),
                            game.version_group_id,
                        ) not in ctx.move_game_data:
                            raise ValueError(f"Battle {bid}: move {mv} unknown in this game")
                ability = member.get("ability")
                w.add(
                    m.TrainerPartyMember(
                        bid,
                        slot,
                        form,
                        member["level"],
                        member.get("gender"),
                        _slug(ctx.slug_to_ability, ability, "ability") if ability else None,
                        _slug(ctx.slug_to_item, member["held_item"], "item") if member.get("held_item") else None,
                        moves,
                        _status(b),
                        evidence,
                    )
                )
            counts["battles"] += 1
        for a in pack.acquisitions:
            form = _slug(ctx.slug_to_pokemon, a["pokemon"], "pokemon") if "pokemon" in a else None
            item = _slug(ctx.slug_to_item, a["item"], "item") if "item" in a else None
            location = _location(ctx, a.get("location"))
            area = a.get("location_area")
            area_id = None
            if area is not None:
                area_id = int(area)
                if area_id not in ctx.location_areas:
                    raise ValueError(f"Acquisition {a['id']}: unknown location area {area}")
            w.add(
                m.Acquisition(
                    f"pack:{game.id}:{a['id']}",
                    game.id,
                    form,
                    item,
                    location,
                    area_id,
                    a["method"],
                    a.get("min_level"),
                    a.get("max_level"),
                    a.get("chance_percent"),
                    a.get("availability", "unknown"),
                    a["prerequisites"],
                    a.get("encounter_conditions", {"op": "always"}),
                    _status(a),
                    a.get("note", ""),
                    _pack_ev(ctx, slug, a["references"], f"acquisitions.{a['id']}"),
                )
            )
            counts["acquisitions"] += 1
        for s in pack.shops:
            sid = f"{slug}:{s['id']}"
            evidence = _pack_ev(ctx, slug, s["references"], f"shops.{s['id']}")
            w.add(
                m.Shop(
                    sid,
                    game.id,
                    _location(ctx, s.get("location")),
                    s["name"],
                    s.get("prerequisites", {"op": "always"}),
                    _status(s),
                    evidence,
                )
            )
            for entry in s["items"]:
                w.add(
                    m.ShopItem(
                        sid,
                        _slug(ctx.slug_to_item, entry["item"], "item"),
                        entry.get("price"),
                        entry.get("prerequisites", {"op": "always"}),
                        evidence,
                    )
                )
            counts["shops"] += 1
        for t in pack.tutors:
            move = _slug(ctx.slug_to_move, t["move"], "move")
            if (move, game.version_group_id) not in ctx.move_game_data:
                raise ValueError(f"Tutor {t['id']}: move {t['move']} unknown in this game")
            w.add(
                m.Tutor(
                    f"{slug}:{t['id']}",
                    game.version_group_id,
                    move,
                    _location(ctx, t.get("location")),
                    _slug(ctx.slug_to_item, t["cost_item"], "item") if t.get("cost_item") else None,
                    t.get("cost_amount"),
                    t.get("prerequisites", {"op": "always"}),
                    _status(t),
                    _pack_ev(ctx, slug, t["references"], f"tutors.{t['id']}"),
                )
            )
            counts["tutors"] += 1
        for issue in pack.issues:
            refs = issue.get("references") or []
            evidence = (
                _pack_ev(ctx, slug, refs, f"issues.{issue['id']}")
                if refs
                else ev((f"pack:{slug}", f"issues.{issue['id']}"))
            )
            w.add(
                m.DataIssue(
                    f"{slug}:{issue['id']}",
                    game.id,
                    issue["feature"],
                    issue["subject"],
                    issue["kind"],
                    issue["description"],
                    evidence,
                )
            )
            counts["issues"] += 1
    w.flush()


def _pack_ev(ctx: Context, slug: str, refs: list[str], selector: str) -> str:
    return ctx.ev(
        *[(f"ref:{slug}:{ref}", f"read for verification: {selector}") for ref in refs],
        (f"pack:{slug}", selector),
    )


def _slug(index: dict[str, int], value: str, kind: str) -> int:
    if value not in index:
        raise ValueError(f"Unknown {kind} slug in pack: {value}")
    return index[value]


def _location(ctx: Context, value: str | None) -> int | None:
    if value is None:
        return None
    return _slug(ctx.slug_to_location, value, "location")
