"""Mechanics flags and curated game-pack content (progression, bosses, shops, tutors, issues)."""

from __future__ import annotations

from rotom_dex.domain import models as m
from rotom_dex.domain.conditions import leaves
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
                    raise ValueError(f"Pack {game.slug} contradicts mechanics pack on {key}; resolve in the mechanics pack instead")
                values[key] = entry["value"]
                notes[key] = (_status(entry), entry.get("note", ""))
                evidence[key] = _pack_ev(ctx, game.slug, entry["references"], f"mechanics.{key}")
        for key, value in values.items():
            status, note = notes[key]
            w.add(m.GameMechanic(info.id, key, value, note, status, evidence[key]))
    w.flush()

    ctx.pack_counts: dict[int, dict[str, int]] = {}
    ctx.progression_completeness: dict[int, dict[str, str]] = {}
    ctx.boss_completeness: dict[int, dict[str, str]] = {}
    for game in ctx.games:
        pack = ctx.packs.get(game.slug)
        counts = {
            "milestones": 0,
            "battles": 0,
            "location_gates": 0,
            "acquisitions": 0,
            "shops": 0,
            "tutors": 0,
            "issues": 0,
        }
        ctx.pack_counts[game.id] = counts
        if not pack:
            continue
        counts["location_gates"] = len(pack.location_gates)
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
                if ability is not None:
                    # A curated roster is transcribed by hand from a reference page, so the ability
                    # is checked against the species' own slots rather than merely existing.
                    ability_id = _slug(ctx.slug_to_ability, ability, "ability")
                    if (form, ability_id, game.version_group_id) not in ctx.form_abilities:
                        raise ValueError(f"Battle {bid}: {member['pokemon']} cannot have ability {ability}")
                w.add(
                    m.TrainerPartyMember(
                        bid,
                        slot,
                        form,
                        member["level"],
                        member.get("gender"),
                        ability_id if ability else None,
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
            evidence = _pack_ev(ctx, slug, refs, f"issues.{issue['id']}") if refs else ev((f"pack:{slug}", f"issues.{issue['id']}"))
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
        progression = _progression_status(pack)
        ctx.progression_completeness[game.id] = progression
        ctx.boss_completeness[game.id] = _boss_status(pack, progression["status"])
    w.flush()


MAIN_STORY_KINDS = ("badge", "elite-four", "champion")


def _progression_status(pack) -> dict[str, str]:
    """`complete` is earned by a connected chain to a declared end, not by the pack claiming it."""
    if not pack.milestones:
        return {"status": "missing", "note": "No curated milestones."}
    total = len(pack.milestones)
    # The pack validator already guarantees every milestone leaf resolves, so these edges cannot dangle.
    edges = {ms["slug"]: [leaf["value"] for leaf in leaves(ms["prerequisites"]) if leaf["op"] == "milestone"] for ms in pack.milestones}
    if pack.main_story_end is None:
        return {"status": "partial", "note": f"{total} curated milestones; no main_story_end is declared, so the reviewed story is open-ended."}

    # Every milestone must be grounded: reachable by walking prerequisites down to a root. A cycle
    # never grounds, so this catches cycles without a separate pass.
    grounded: set[str] = set()
    for _ in range(total):
        progressed = False
        for slug, needs in edges.items():
            if slug not in grounded and all(n in grounded for n in needs):
                grounded.add(slug)
                progressed = True
        if not progressed:
            break
    ungrounded = sorted(set(edges) - grounded)
    if ungrounded:
        return {"status": "partial", "note": f"{total} curated milestones; {len(ungrounded)} are unreachable from a starting milestone ({', '.join(ungrounded[:3])})."}
    return {
        "status": "complete",
        "note": f"{total} curated milestones forming a connected chain from the start of the game to '{pack.main_story_end}'. "
        "Complete means the reviewed main story, not post-game content.",
    }


def _boss_status(pack, progression_status: str) -> dict[str, str]:
    """`complete` means every badge, Elite Four and Champion milestone has a reviewed roster.

    Gated on the progression being complete as well. "Every curated badge has a roster" is a hollow
    claim when only the first badge is curated, so an incomplete story caps this at `partial`.
    """
    if not pack.battles:
        return {"status": "missing", "note": "No curated trainer battles."}
    total = len(pack.battles)
    attached = {b.get("milestone") for b in pack.battles}
    required = [ms["slug"] for ms in pack.milestones if ms["kind"] in MAIN_STORY_KINDS]
    if not required:
        return {"status": "partial", "note": f"{total} curated trainer battles; no badge or Champion milestones are curated to check them against."}
    if progression_status != "complete":
        note = f"{total} curated trainer battles covering {len(required)} curated main-story milestones, but the progression itself is incomplete."
        return {"status": "partial", "note": note}
    missing = [slug for slug in required if slug not in attached]
    if missing:
        note = f"{total} curated trainer battles; {len(missing)} of {len(required)} main-story milestones still have no roster ({', '.join(missing[:3])})."
        return {"status": "partial", "note": note}
    return {"status": "complete", "note": f"{total} curated trainer battles; every one of the {len(required)} badge, Elite Four and Champion milestones has a reviewed roster."}


def _pack_ev(ctx: Context, slug: str, refs: list[str], selector: str) -> str:
    return ctx.pack_ev(slug, refs, selector)


def _slug(index: dict[str, int], value: str, kind: str) -> int:
    if value not in index:
        raise ValueError(f"Unknown {kind} slug in pack: {value}")
    return index[value]


def _location(ctx: Context, value: str | None) -> int | None:
    if value is None:
        return None
    return _slug(ctx.slug_to_location, value, "location")
