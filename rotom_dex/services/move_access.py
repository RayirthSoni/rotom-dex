"""Move eligibility separated from access to the method that teaches it.

A learnset row establishes that a Pokemon *can* learn a move in this version group. It says nothing
about whether the player can reach the machine, the tutor or the breeding partner. Those are
different questions with different evidence, and in this snapshot they have different answers:
machine access can often be derived, tutor access never can, because the source carries no tutor
locations at all.
"""

from __future__ import annotations

from rotom_dex.repositories import pokemon as pokemon_repo
from rotom_dex.repositories.common import GameScope, rows
from rotom_dex.services.context import PlaythroughContext, TeamMember, classify, condition_context

ASSUMPTION = (
    "Eligibility and access are reported separately. A row marked eligible says this Pokemon can "
    "learn the move in this game; the access field says whether your progress puts the method within "
    "reach. Access unknown is not access denied."
)

TUTOR_REASON = (
    "Move tutors are not in this snapshot: the source carries no tutor locations or costs, so tutor "
    "access is unknown for every Pokemon in every game. Eligibility is established, access is not."
)


def _machine_access(db, scope: GameScope, context: dict, item_slug: str | None, kind: str | None) -> dict:
    if item_slug is None:
        return {"status": "unknown", "reason": "This machine's item is not recorded for this version group."}
    # `rows` decodes the JSON prerequisite trees for us.
    routes = rows(
        db,
        """SELECT a.id, a.method, a.prerequisites, l.slug AS location FROM acquisitions a
           LEFT JOIN locations l ON l.id=a.location_id JOIN items i ON i.id=a.item_id
           WHERE a.game_id=? AND i.slug=?""",
        (scope.id, item_slug),
    )
    shops = rows(
        db,
        """SELECT s.id, s.name, si.price, si.prerequisites FROM shop_items si JOIN shops s ON s.id=si.shop_id
           JOIN items i ON i.id=si.item_id WHERE s.game_id=? AND i.slug=?""",
        (scope.id, item_slug),
    )
    verdicts = []
    for route in routes:
        verdicts.append({"kind": "acquisition", "id": route["id"], "method": route["method"], "location": route["location"], **classify(route["prerequisites"], context)})
    for shop in shops:
        verdicts.append({"kind": "shop", "id": shop["id"], "name": shop["name"], "price": shop["price"], **classify(shop["prerequisites"], context)})

    if not verdicts:
        return {
            "status": "unknown",
            "item": item_slug,
            "routes": [],
            "reason": f"No recorded way to obtain {item_slug} in {scope.slug}; machine locations and prices are not in the source.",
        }
    best = "reachable" if any(v["status"] == "reachable" for v in verdicts) else ("unknown" if any(v["status"] == "unknown" for v in verdicts) else "locked")
    reusable = scope.mechanics.get("tm_reusable") if kind == "tm" else (1 if kind == "hm" else 0)
    note = ""
    if kind == "tm" and reusable == 0:
        note = "TMs are consumed when used in this game, so one copy teaches one Pokemon."
    elif kind == "tm" and reusable is None:
        note = "Whether TMs are reusable in this game is unverified."
    return {"status": best, "item": item_slug, "routes": verdicts, "reusable": reusable, "note": note}


def eligibility(db, scope: GameScope, ctx: PlaythroughContext, slug: str, member: TeamMember | None = None) -> dict:
    context, assumptions = condition_context(ctx, member)
    result = pokemon_repo.pokemon_learnset(db, scope.slug, slug, None, None)
    data = result["data"]
    if data is None:
        return {"pokemon": slug, "data": None, "assumptions": result["assumptions"]}

    level = member.level if member else None
    breeding = scope.mechanics.get("breeding")
    for row in data["moves"]:
        method = row["method"]
        if method == "level-up":
            if level is None:
                access = {"status": "unknown", "reason": "No level is recorded for this Pokemon, so it is unknown whether it has reached this move yet."}
            elif row["level"] <= level:
                access = {"status": "reachable", "reason": f"Learned at level {row['level']}; this Pokemon is level {level}."}
            else:
                access = {"status": "locked", "reason": f"Needs level {row['level']}; this Pokemon is level {level}."}
        elif method == "machine":
            access = _machine_access(db, scope, context, row.get("machine_item"), row.get("machine_kind"))
        elif method == "tutor":
            access = {"status": "unknown", "reason": TUTOR_REASON}
        elif method == "egg":
            if breeding == 0:
                access = {"status": "locked", "reason": f"{scope.slug} has no breeding, so egg moves cannot be obtained here."}
            elif breeding is None:
                access = {"status": "unknown", "reason": f"Whether {scope.slug} has breeding is unverified."}
            else:
                access = {"status": "unknown", "reason": "Breeding chains are not computed: which parents can pass this move is not derived in this snapshot."}
        else:
            access = {"status": "unknown", "reason": f"Access through '{method}' is not modelled in this snapshot."}
        row["eligible"] = True
        row["access"] = access

    counts: dict[str, int] = {}
    for row in data["moves"]:
        key = f"{row['method']}:{row['access']['status']}"
        counts[key] = counts.get(key, 0) + 1
    tutor_rows = sum(1 for r in data["moves"] if r["method"] == "tutor")
    tutors_recorded = db.execute("SELECT count(*) FROM tutors WHERE version_group_id=?", (scope.version_group_id,)).fetchone()[0]
    if tutor_rows:
        assumptions.append(f"{tutor_rows} moves are tutor-eligible for this Pokemon and {tutors_recorded} tutors are recorded for {scope.slug}.")
    return {
        "pokemon": slug,
        "member": member.pokemon if member else None,
        "moves": data["moves"],
        "method_counts": data["method_counts"],
        "access_counts": dict(sorted(counts.items())),
        "machine_rules": data["machine_rules"],
        "assumptions": assumptions,
    }
