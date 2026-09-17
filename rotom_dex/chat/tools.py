"""The typed tool allowlist.

Two structural rules make whole classes of wrong answer impossible rather than merely discouraged:

  1. No tool schema accepts a game. The dispatcher injects the one resolved from the validated
     context, so an answer about the wrong game cannot be produced even by a confused model.
  2. No tool schema accepts the playthrough. Progress, team and constraints come from the request
     body the player's own browser sent, so a model cannot invent a badge to justify a route.

Every handler returns the ordinary response envelope, which already carries `coverage_status`,
`assumptions` and `evidence`. Lookup, arithmetic and availability all happen in here; the model's
job is to choose a tool and explain what came back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rotom_dex.chat.protocols import ToolSpec
from rotom_dex.repositories import abilities as abilities_repo
from rotom_dex.repositories import coverage as coverage_repo
from rotom_dex.repositories import items as items_repo
from rotom_dex.repositories import locations as locations_repo
from rotom_dex.repositories import moves as moves_repo
from rotom_dex.repositories import natures as natures_repo
from rotom_dex.repositories import pokemon as pokemon_repo
from rotom_dex.repositories import progression as progression_repo
from rotom_dex.repositories import types as types_repo
from rotom_dex.repositories import vocabulary as vocabulary_repo
from rotom_dex.repositories.common import GameScope, envelope
from rotom_dex.services import boss, evolution, move_access, reachability, team
from rotom_dex.services.context import PlaythroughContext

SLUG = {"type": "string", "maxLength": 64}


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    handler: Callable


def _member(ctx: PlaythroughContext, index):
    if index is None:
        return None
    if not isinstance(index, int) or index >= len(ctx.team):
        return None
    return ctx.team[index]


def _registry() -> dict[str, Tool]:
    def tool(name, description, properties, required, features, handler):
        return Tool(ToolSpec(name, description, _schema(properties, required), tuple(features)), handler)

    entries = [
        tool(
            "dex_search",
            "Search Pokemon present in the current game by name fragment and optionally by type.",
            {"q": {"type": "string", "maxLength": 60}, "type": SLUG, "limit": {"type": "integer", "minimum": 1, "maximum": 25}},
            [],
            ("pokemon", "types"),
            lambda db, scope, ctx, a: pokemon_repo.search_pokemon(db, scope.slug, a.get("q"), a.get("type"), min(int(a.get("limit", 10)), 25), 0),
        ),
        tool(
            "dex_lookup",
            "Full details for one Pokemon in this game: typing, base stats, abilities, and optionally how to obtain it, how it evolves, and what it can learn.",
            {
                "pokemon": SLUG,
                "include": {"type": "array", "items": {"type": "string", "enum": ["acquisition", "evolution", "learnset"]}, "maxItems": 3},
                "max_level": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["pokemon"],
            ("pokemon", "types", "stats", "abilities"),
            lambda db, scope, ctx, a: pokemon_repo.pokemon_detail(db, scope.slug, a["pokemon"], a.get("max_level"), tuple(a.get("include") or ())),
        ),
        tool(
            "move_lookup",
            "This game's values for one move: type, damage class, power, accuracy, PP and effect.",
            {"move": SLUG},
            ["move"],
            ("moves", "move-effects"),
            lambda db, scope, ctx, a: moves_repo.move_detail(db, scope.slug, a["move"]),
        ),
        tool(
            "move_search",
            "Search moves that exist in this game, by name fragment, type or damage class.",
            {
                "q": {"type": "string", "maxLength": 60},
                "type": SLUG,
                "damage_class": {"type": "string", "enum": ["physical", "special", "status"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            [],
            ("moves",),
            lambda db, scope, ctx, a: moves_repo.search_moves(db, scope.slug, a.get("q"), a.get("type"), a.get("damage_class"), min(int(a.get("limit", 10)), 25), 0),
        ),
        tool(
            "item_lookup",
            "One item in this game: effect, category, price, where it can be obtained and which shops sell it.",
            {"item": SLUG},
            ["item"],
            ("items", "item-effects", "item-acquisition", "shops"),
            lambda db, scope, ctx, a: items_repo.item_detail(db, scope.slug, a["item"]),
        ),
        tool(
            "ability_lookup",
            "One ability in this game, or an explanation that this game has no Abilities at all.",
            {"ability": SLUG},
            ["ability"],
            ("abilities",),
            lambda db, scope, ctx, a: abilities_repo.ability_detail(db, scope.slug, a["ability"]),
        ),
        tool(
            "nature_lookup",
            "One Nature, or every Nature when none is named. Reports when this game has no Natures.",
            {"nature": SLUG},
            [],
            ("natures",),
            lambda db, scope, ctx, a: natures_repo.nature_detail(db, scope.slug, a["nature"]) if a.get("nature") else natures_repo.list_natures(db, scope.slug),
        ),
        tool(
            "type_matchup",
            "The exact damage multiplier for one attacking type against one or two defending types, using this game's "
            "generation chart. Always use this instead of reasoning about type effectiveness.",
            {"attack": SLUG, "defense": SLUG, "defense2": SLUG},
            ["attack", "defense"],
            ("type-effectiveness", "types"),
            lambda db, scope, ctx, a: types_repo.matchup(db, scope.slug, a["attack"], a["defense"], a.get("defense2")),
        ),
        tool(
            "game_facts",
            "Which mechanics this game has (Abilities, Natures, held items, breeding, the physical/special split) and "
            "the vocabulary of identifiers that are valid in it. Call this before assuming a mechanic exists.",
            {},
            [],
            ("mechanics",),
            lambda db, scope, ctx, a: vocabulary_repo.vocabulary(db, scope.slug),
        ),
        tool(
            "coverage_report",
            "What has and has not been reviewed for this game, feature by feature, plus the known data gaps. Use it to decide whether abstaining is the honest answer.",
            {},
            [],
            (),
            lambda db, scope, ctx, a: envelope(db, scope, coverage_repo.coverage_report(db, scope.slug)["games"][0], coverage=[], include_evidence=False),
        ),
        tool(
            "analyze_team",
            "The recorded team's defensive profile per member and its offensive coverage from the moves actually recorded. Preparation only; it never predicts a battle result.",
            {},
            [],
            team.FEATURES,
            lambda db, scope, ctx, a: envelope(db, scope, team.analyse(db, scope, ctx), features=team.FEATURES, include_evidence=False, assumptions=list(team.ASSUMPTIONS)),
        ),
        tool(
            "prepare_for_boss",
            "Preparation for one reviewed boss battle: the roster, how the types line up, level differences and supplies the recorded progress can already reach.",
            {"battle": {"type": "string", "maxLength": 96}},
            ["battle"],
            ("boss-teams", "progression", "shops"),
            lambda db, scope, ctx, a: _boss(db, scope, ctx, a["battle"]),
        ),
        tool(
            "check_reachability",
            "Whether the recorded progress settles obtaining these Pokemon or items. Returns reachable, locked or "
            "unknown per route, with the prerequisite that decided it. Always use this before recommending that the "
            "player go and get something.",
            {"pokemon": {"type": "array", "items": SLUG, "maxItems": 10}, "items": {"type": "array", "items": SLUG, "maxItems": 10}},
            [],
            ("encounters", "location-gates", "gifts-trades", "breeding", "evolution", "item-acquisition", "shops"),
            lambda db, scope, ctx, a: _reachability(db, scope, ctx, a),
        ),
        tool(
            "move_access",
            "Every move one Pokemon is eligible for in this game, with access to the teaching method reported separately. Eligibility is not access.",
            {"pokemon": SLUG, "member": {"type": "integer", "minimum": 0, "maximum": 5}},
            ["pokemon"],
            ("learnsets", "machines", "tutors", "breeding", "item-acquisition"),
            lambda db, scope, ctx, a: _wrap(
                db,
                scope,
                move_access.eligibility(db, scope, ctx, a["pokemon"], _member(ctx, a.get("member"))),
                ("learnsets", "machines", "tutors"),
                move_access.ASSUMPTION,
            ),
        ),
        tool(
            "evolution_requirements",
            "How one Pokemon evolves in this game, evaluated against the recorded progress, including rules that do not apply in this game.",
            {"pokemon": SLUG, "member": {"type": "integer", "minimum": 0, "maximum": 5}},
            ["pokemon"],
            ("evolution",),
            lambda db, scope, ctx, a: _wrap(db, scope, evolution.requirements(db, scope, ctx, a["pokemon"], _member(ctx, a.get("member"))), ("evolution",), evolution.ASSUMPTION),
        ),
        tool(
            "progression_lookup",
            "The reviewed main-story milestones for this game, or its reviewed boss battles. Filtered by the player's spoiler preference before you see it.",
            {"kind": {"type": "string", "enum": ["milestones", "battles"]}, "battle": {"type": "string", "maxLength": 96}},
            ["kind"],
            ("progression", "boss-teams"),
            lambda db, scope, ctx, a: _progression(db, scope, a),
        ),
        tool(
            "location_encounters",
            "Which Pokemon appear at one location in this game, by encounter method, with rates.",
            {"location": SLUG},
            ["location"],
            ("encounters", "location-gates"),
            lambda db, scope, ctx, a: locations_repo.location_encounters(db, scope.slug, a["location"]),
        ),
    ]
    return {t.spec.name: t for t in entries}


def _wrap(db, scope: GameScope, result: dict, features, assumption: str) -> dict:
    """Services return a bare dict; give it the same envelope every read endpoint uses."""
    if result.get("data", False) is None:
        return envelope(db, scope, None, features=features, assumptions=result.get("assumptions", []))
    return envelope(db, scope, result, features=features, include_evidence=False, assumptions=[assumption, *result.get("assumptions", [])])


def _boss(db, scope: GameScope, ctx: PlaythroughContext, battle: str) -> dict:
    result = boss.prepare(db, scope, ctx, battle)
    if result.get("data", False) is None:
        return envelope(db, scope, None, features=("boss-teams",), assumptions=result["assumptions"])
    return envelope(db, scope, result, features=("boss-teams", "progression", "shops"), include_evidence=False, assumptions=[*boss.ASSUMPTIONS, *result["assumptions"]])


def _reachability(db, scope: GameScope, ctx: PlaythroughContext, args: dict) -> dict:
    pokemon = [reachability.for_pokemon(db, scope, ctx, s.lower()) for s in (args.get("pokemon") or [])[:10]]
    items = [reachability.for_item(db, scope, ctx, s.lower()) for s in (args.get("items") or [])[:10]]
    shared = next((r["assumptions"] for r in [*pokemon, *items] if "assumptions" in r), [])
    data = {"pokemon": pokemon, "items": items, "closed_world": sorted(ctx.closed_world)}
    features = ("encounters", "location-gates", "gifts-trades", "breeding", "evolution", "item-acquisition", "shops")
    return envelope(db, scope, data, features=features, include_evidence=False, assumptions=[reachability.ASSUMPTION, *shared])


def _progression(db, scope: GameScope, args: dict) -> dict:
    if args["kind"] == "milestones":
        return progression_repo.list_milestones(db, scope.slug)
    if args.get("battle"):
        return progression_repo.battle_detail(db, scope.slug, args["battle"])
    return progression_repo.list_battles(db, scope.slug)


REGISTRY = _registry()


def specs(*, research_enabled: bool) -> list[ToolSpec]:
    """The tools a request may use. `web_research` is declared only when it is actually available."""
    out = [t.spec for t in REGISTRY.values()]
    if research_enabled:
        out.append(
            ToolSpec(
                name="web_research",
                description=(
                    "Search the public web when the player explicitly asks you to verify something, or when the reviewed "
                    "database has a gap you have already confirmed with coverage_report. Results are unreviewed and must be "
                    "labelled as externally researched; they never become facts with evidence ids."
                ),
                parameters=_schema(
                    {"query": {"type": "string", "maxLength": 200}, "why": {"type": "string", "maxLength": 200}},
                    ["query", "why"],
                ),
            )
        )
    return out
