"""Per-game coverage rows and source-level data issues, computed from what was imported."""

from __future__ import annotations

from rotom_dex.domain import models as m
from rotom_dex.ingestion.context import Context
from rotom_dex.ingestion.importers.catalog import expected_type_count

FEATURES = (
    "pokemon",
    "types",
    "stats",
    "abilities",
    "ability-type-effects",
    "moves",
    "move-effects",
    "move-flavor-text",
    "learnsets",
    "machines",
    "tutors",
    "evolution",
    "encounters",
    "location-gates",
    "gifts-trades",
    "breeding",
    "held-items",
    "items",
    "item-prices",
    "item-effects",
    "item-flavor-text",
    "item-acquisition",
    "shops",
    "natures",
    "type-effectiveness",
    "mechanics",
    "progression",
    "boss-teams",
)


def run(ctx: Context) -> None:
    db, w, ev = ctx.w.db, ctx.w, ctx.ev
    policy = ev(ctx.registry_ref, ctx.normalizer_ref)

    def one(sql: str, *params) -> int:
        return db.execute(sql, params).fetchone()[0]

    for game in ctx.games:
        gid, vg = game.id, game.version_group_id
        info = ctx.version_groups[vg]
        gen = info.generation_id
        rows: list[tuple[str, str, str]] = []
        pack = ctx.pack_counts.get(gid, {})
        inherited = " Version-group data inherited from the base game's group." if info.data_source_id else ""

        def mech(key: str, vg: int = vg) -> int | None:
            return ctx.mechanic(vg, key)

        present = one(
            "SELECT count(*) FROM pokemon_version_groups WHERE version_group_id=? AND presence='present'",
            vg,
        )
        unknown_forms = one(
            "SELECT count(*) FROM pokemon_version_groups WHERE version_group_id=? AND presence='unknown'",
            vg,
        )
        rows.append(
            (
                "pokemon",
                "complete" if present else "missing",
                f"{present} forms present in source data for this version group; {unknown_forms} additional variant forms with unknown presence.",
            )
        )
        for feature, table in (("types", "pokemon_types"), ("stats", "pokemon_stats")):
            covered = one(
                f"SELECT count(DISTINCT p.form_id) FROM pokemon_version_groups p JOIN {table} t "
                "ON t.form_id=p.form_id AND t.generation_id=? WHERE p.version_group_id=? "
                "AND p.presence='present'",
                gen,
                vg,
            )
            rows.append(
                (
                    feature,
                    _ratio(covered, present),
                    f"{covered}/{present} present forms have generation {gen} {feature}.",
                )
            )
        rows.append(
            _mechanic_feature(
                "abilities",
                mech("abilities"),
                one(
                    "SELECT count(DISTINCT p.form_id) FROM pokemon_version_groups p JOIN "
                    "pokemon_abilities a ON a.form_id=p.form_id AND a.generation_id=? WHERE "
                    "p.version_group_id=? AND p.presence='present'",
                    gen,
                    vg,
                ),
                present,
                "ability slots",
            )
        )
        # Reviewed type modifiers are a curated addition, never complete: the note says how many of
        # the game's own ability slots are covered, so "partial" is read as scope, not as a gap.
        modelled = one(
            """SELECT count(DISTINCT a.ability_id) FROM ability_type_effects e
               JOIN pokemon_abilities a ON a.ability_id=e.ability_id AND a.generation_id=e.generation_id
               JOIN pokemon_version_groups p ON p.form_id=a.form_id AND p.version_group_id=? AND p.presence='present'
               WHERE e.generation_id=?""",
            vg,
            gen,
        )
        in_game = one(
            """SELECT count(DISTINCT a.ability_id) FROM pokemon_abilities a
               JOIN pokemon_version_groups p ON p.form_id=a.form_id AND p.version_group_id=? AND p.presence='present'
               WHERE a.generation_id=?""",
            vg,
            gen,
        )
        if mech("abilities") == 0:
            rows.append(("ability-type-effects", "complete", "Not applicable: this mechanic is absent in this game."))
        elif mech("abilities") is None:
            rows.append(("ability-type-effects", "missing", "Whether this game has abilities is unverified."))
        else:
            rows.append(
                (
                    "ability-type-effects",
                    "partial" if modelled else "missing",
                    f"{modelled} of {in_game} abilities reachable in this game have a reviewed type modifier. "
                    "Only type-based defensive modifiers are curated; abilities whose effect depends on a move "
                    "flag, the weather, the field or the holder's HP are listed as data issues.",
                )
            )
        moves = one("SELECT count(*) FROM move_game_data WHERE version_group_id=?", vg)
        rows.append(
            (
                "moves",
                "complete" if moves else "missing",
                f"{moves} moves with version-group values (history rewound; damage class per generation rules).{inherited}",
            )
        )
        rows.append(
            (
                "move-effects",
                "partial" if moves else "missing",
                "Effect text uses the source's current wording, not historical wording; effect ids are linked per move.",
            )
        )
        flavor = one("SELECT count(*) FROM move_flavor_text WHERE version_group_id=?", vg)
        rows.append(
            (
                "move-flavor-text",
                "complete" if flavor else "missing",
                f"{flavor} in-game move descriptions for this version group.{inherited}",
            )
        )
        learn = one("SELECT count(DISTINCT form_id) FROM learnsets WHERE version_group_id=?", vg)
        rows.append(
            (
                "learnsets",
                _ratio(learn, present),
                f"{learn}/{present} present forms have learnset rows. Eligibility only; TM, tutor, breeding access is separate.{inherited}",
            )
        )
        rows.append(
            _mechanic_feature(
                "machines",
                mech("tm_present"),
                one("SELECT count(*) FROM machines WHERE version_group_id=?", vg),
                None,
                "machine items linked to moves; locations and prices are not in the source",
            )
        )
        tutors = one("SELECT count(*) FROM tutors WHERE version_group_id=?", vg)
        rows.append(
            (
                "tutors",
                "partial" if tutors else "missing",
                f"{tutors} curated tutor entries; the source has tutor learnsets but no tutor locations or costs.",
            )
        )
        applies = one(
            "SELECT count(*) FROM evolution_applicability WHERE version_group_id=? AND status='applies'",
            vg,
        )
        reviewed = one(
            "SELECT count(*) FROM evolution_applicability WHERE version_group_id=? AND verification_status=?",
            vg,
            m.REFERENCE_REVIEWED,
        )
        rows.append(
            (
                "evolution",
                "partial" if applies else "missing",
                f"{applies} rules derived as applicable ({reviewed} reviewed). Conditions are typed; unsupported mechanics carry unknown leaves.",
            )
        )
        enc = ctx.encounter_counts.get(gid, 0)
        rows.append(
            (
                "encounters",
                "partial" if enc else "missing",
                f"{enc} exact-version encounter slots. Progression prerequisites unreviewed; absent rows do not mean unobtainable.",
            )
        )
        special = ctx.special_method_counts.get(gid, 0) + pack.get("acquisitions", 0)
        rows.append(
            (
                "gifts-trades",
                "partial" if special else "missing",
                f"{special} gift/trade/static routes from source encounters and packs.",
            )
        )
        rows.append(
            _mechanic_feature(
                "breeding",
                mech("breeding"),
                ctx.breeding_counts.get(gid, 0),
                None,
                "derived breeding routes",
                derived=True,
            )
        )
        rows.append(
            _mechanic_feature(
                "held-items",
                mech("held_items"),
                ctx.held_item_counts.get(gid, 0),
                None,
                "wild held-item records",
                derived=True,
            )
        )
        items = one("SELECT count(*) FROM item_game_data WHERE version_group_id=?", vg)
        rows.append(
            (
                "items",
                "complete" if items else "missing",
                f"{items} items indexed for generation {gen} with version-group data.{inherited}",
            )
        )
        priced = one(
            "SELECT count(*) FROM item_game_data WHERE version_group_id=? AND price_provenance='version-group'",
            vg,
        )
        rows.append(
            (
                "item-prices",
                "partial" if items else "missing",
                f"{priced} version-group prices; remaining items use the source's default cost (provenance recorded per item).",
            )
        )
        rows.append(
            (
                "item-effects",
                "partial" if items else "missing",
                "Effect text uses the source's current wording, not historical wording.",
            )
        )
        iflavor = one(
            "SELECT count(*) FROM item_game_data WHERE version_group_id=? AND flavor_text IS NOT NULL",
            vg,
        )
        rows.append(
            (
                "item-flavor-text",
                _ratio(iflavor, items),
                f"{iflavor}/{items} items have in-game descriptions for this version group.",
            )
        )
        item_acq = one("SELECT count(*) FROM acquisitions WHERE game_id=? AND item_id IS NOT NULL", gid)
        rows.append(
            (
                "item-acquisition",
                "partial" if item_acq or ctx.held_item_counts.get(gid) else "missing",
                f"{item_acq} curated item routes; wild held items recorded separately. Field items, gifts and machine locations are not in the source.",
            )
        )
        shops = pack.get("shops", 0)
        rows.append(
            (
                "shops",
                "partial" if shops else "missing",
                f"{shops} curated shops. The source has no shop inventories.",
            )
        )
        rows.append(_mechanic_feature("natures", mech("natures"), one("SELECT count(*) FROM natures"), None, "natures"))
        chart = one("SELECT count(*) FROM type_effectiveness WHERE generation_id=?", gen)
        rows.append(
            (
                "type-effectiveness",
                "complete" if chart == expected_type_count(gen) ** 2 else "missing",
                f"{chart} generation {gen} attack/defense pairs including immunities.",
            )
        )
        mechanics = one("SELECT count(*) FROM game_mechanics WHERE version_group_id=?", vg)
        rows.append(
            (
                "mechanics",
                _ratio(mechanics, 12),
                f"{mechanics}/12 mechanics flags recorded for this version group.",
            )
        )
        gated, encounter_locations = pack.get("location_gates", 0), ctx.encounter_location_counts.get(gid, 0)
        rows.append(
            (
                "location-gates",
                _ratio(gated, encounter_locations),
                f"{gated}/{encounter_locations} locations with encounters have a reviewed access condition; "
                "the rest keep an explicit unknown, which is not a claim that they are unreachable.",
            )
        )
        # `complete` is earned by an invariant the importer checked, never by the pack asserting it:
        # a connected milestone chain ending at the declared `main_story_end`, and a battle attached
        # to every badge, Elite Four and Champion milestone.
        progression = ctx.progression_completeness.get(gid, {})
        rows.append(
            (
                "progression",
                progression.get("status", "missing"),
                progression.get("note", f"{pack.get('milestones', 0)} curated milestones."),
            )
        )
        bosses = ctx.boss_completeness.get(gid, {})
        rows.append(
            (
                "boss-teams",
                bosses.get("status", "missing"),
                bosses.get("note", f"{pack.get('battles', 0)} curated trainer battles."),
            )
        )
        unknown_features = {f for f, _, _ in rows} - set(FEATURES)
        if unknown_features:
            raise ValueError(f"Coverage rows for unknown features {sorted(unknown_features)}")
        for feature, status, note in rows:
            w.add(m.Coverage(gid, feature, "*", status, note, policy))
        if not enc:
            w.add(
                m.DataIssue(
                    f"source:{game.slug}:encounters",
                    gid,
                    "encounters",
                    "*",
                    "missing",
                    "The pinned source has no encounter rows for this version.",
                    policy,
                )
            )
        if not learn:
            w.add(
                m.DataIssue(
                    f"source:{game.slug}:learnsets",
                    gid,
                    "learnsets",
                    "*",
                    "missing",
                    "The pinned source has no learnset rows for this version group.",
                    policy,
                )
            )
        if info.data_source_id:
            w.add(
                m.DataIssue(
                    f"source:{game.slug}:inherited",
                    gid,
                    "learnsets",
                    "*",
                    "unverified",
                    "Expansion content is stored under the base version group in the source; learnsets, moves, machines and item data are inherited from it.",
                    policy,
                )
            )
        for key in ("abilities", "natures", "held_items", "breeding", "tm_present", "tm_reusable"):
            if mech(key) is None:
                w.add(
                    m.DataIssue(
                        f"mechanics:{game.slug}:{key}",
                        gid,
                        "mechanics",
                        key,
                        "unverified",
                        f"Mechanic '{key}' could not be confirmed for this version group.",
                        policy,
                    )
                )
    for pid, gen, slot, aid in ctx.ability_gaps:
        w.add(
            m.DataIssue(
                f"source:abilities:{pid}:{gen}:{slot}",
                None,
                "abilities",
                f"pokemon:{pid}",
                "unverified",
                f"Slot {slot} holds ability {aid}, introduced after generation {gen}, and the source has no historical entry; the slot is omitted for generation {gen}.",
                policy,
            )
        )
    for pid, gen in ctx.missing_abilities:
        w.add(
            m.DataIssue(
                f"source:abilities:none:{pid}:{gen}",
                None,
                "abilities",
                f"pokemon:{pid}",
                "missing",
                f"The source records no ability slots for this form in generation {gen}.",
                policy,
            )
        )
    for iid, slug in ctx.item_slug_collisions:
        w.add(
            m.DataIssue(
                f"source:items:duplicate-slug:{iid}",
                None,
                "items",
                f"item:{iid}",
                "disputed",
                f"The source lists item {iid} with the same identifier as an earlier item ('{slug}'); it is stored as '{slug}-{iid}'.",
                policy,
            )
        )
    if any(g.generation_id >= 8 for g in ctx.games):
        w.add(
            m.DataIssue(
                "source:presence:generation-8-plus",
                None,
                "pokemon",
                "*",
                "unverified",
                "For Generation VIII+ versions the source's game indices repeat earlier lists, so Pokémon "
                "presence is derived from learnsets and encounters only; forms without either are absent.",
                policy,
            )
        )
    if ctx.skipped_moves:
        w.add(
            m.DataIssue(
                "source:moves:non-battle-types",
                None,
                "moves",
                "*",
                "missing",
                f"{len(ctx.skipped_moves)} moves with Shadow/unknown types are not imported.",
                policy,
            )
        )
    w.flush()


def _ratio(covered: int, total: int) -> str:
    if total == 0 or covered == 0:
        return "missing"
    return "complete" if covered >= total else "partial"


def _mechanic_feature(feature: str, flag: int | None, n: int, total: int | None, noun: str, derived: bool = False) -> tuple[str, str, str]:
    if flag is None:
        return (
            feature,
            "missing",
            f"Whether this game has {feature.replace('-', ' ')} is unverified.",
        )
    if flag == 0:
        return (feature, "complete", "Not applicable: this mechanic is absent in this game.")
    if total is not None:
        return (feature, _ratio(n, total), f"{n}/{total} present forms have {noun}.")
    status = ("partial" if derived else "complete") if n else "missing"
    return (feature, status, f"{n} {noun}.")
