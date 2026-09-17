"""Evolution requirements, evaluated against one team member's situation.

Rules that cannot fire in this game are kept and labelled rather than dropped, so a player looking at
Kirlia in Emerald sees that Gallade exists and why it is out of reach here.
"""

from __future__ import annotations

from rotom_dex.repositories import pokemon as pokemon_repo
from rotom_dex.repositories.common import GameScope
from rotom_dex.services.context import PlaythroughContext, TeamMember, classify, condition_context

ASSUMPTION = (
    "A rule marked not-applicable cannot fire in this game; that is a fact about the game, not about "
    "your progress. For applicable rules, met/unmet is derived from what your playthrough records."
)


def requirements(db, scope: GameScope, ctx: PlaythroughContext, slug: str, member: TeamMember | None = None) -> dict:
    context, assumptions = condition_context(ctx, member)
    result = pokemon_repo.pokemon_evolution(db, scope.slug, slug)
    data = result["data"]
    if data is None:
        return {"pokemon": slug, "data": None, "assumptions": result["assumptions"]}
    for rule in data["outgoing"]:
        if rule.get("applicability") == "not-applicable":
            rule["derived"] = {
                "status": "not-applicable",
                "evaluation": False,
                "blocked_by": [],
                "unknown_because": [],
                "reason": rule.get("reason") or "This rule does not apply in this game.",
            }
        else:
            rule["derived"] = classify(rule["conditions"], context)
    return {
        "pokemon": slug,
        "member": member.pokemon if member else None,
        "outgoing": data["outgoing"],
        "incoming": data["incoming"],
        "assumptions": assumptions,
    }
