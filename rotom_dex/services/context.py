"""The playthrough context, and the one design decision that keeps reachability honest.

`evaluate_condition` is three-valued: an absent context key yields unknown, a present-but-unsatisfied
key yields false. So whether a prerequisite reads as *locked* or as *unknown* depends entirely on
which keys we populate, and that is a claim about the player's knowledge, not about the game.

`closed_world` makes the claim explicit, one leaf family at a time. Ticking "my milestone list is
complete" means a route needing an unticked milestone is genuinely locked. Leaving it off means the
same route is unknown. Nothing is inferred: a family the player has not vouched for is simply absent
from the context, and every such omission is reported as an assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rotom_dex.domain.conditions import explain_condition
from rotom_dex.errors import NotFound, SemanticError
from rotom_dex.repositories.common import GameScope, one

# Leaf families the player can vouch for, and the context keys each one populates.
CLOSED_WORLD_FAMILIES: dict[str, tuple[str, ...]] = {
    "milestones": ("milestone",),
    "locations": ("at_location", "in_region"),
    "bag": ("has_item", "use_item", "held_item"),
    "party": ("has_pokemon", "party_has_pokemon", "party_has_type"),
    "trade": ("trade", "trade_for_pokemon"),
}

CLOSED_WORLD_ASSUMED = {
    "milestones": "You marked your completed-milestone list as complete, so a route needing a milestone you have not ticked is reported as locked rather than unknown.",
    "locations": "You marked your visited-location list as complete, so a route in a location you have not visited is reported as locked rather than unknown.",
    "bag": "You marked your bag as complete, so a route needing an item you do not hold is reported as locked rather than unknown.",
    "party": "You marked your party as complete, so a route needing a Pokemon you do not have is reported as locked rather than unknown.",
    "trade": "You told Rotom what trading you can do, so a route needing a trade you cannot make is reported as locked rather than unknown.",
}

CLOSED_WORLD_OPEN = {
    "milestones": "Milestones you have not ticked are treated as unknown, not as incomplete.",
    "locations": "Locations you have not marked visited are treated as unknown, not as unreachable.",
    "bag": "Items you have not recorded are treated as unknown, not as missing.",
    "party": "Pokemon you have not recorded are treated as unknown, not as absent.",
    "trade": "Trade access is treated as unknown.",
}

# Leaf families this product does not track at all. They always evaluate to unknown, and saying so is
# more useful than pretending a route is unavailable because we never asked.
UNTRACKED_REASONS = {
    "time_of_day": "Time of day is not tracked, so time-gated routes stay unknown.",
    "encounter_condition": "Encounter conditions such as swarms, seasons and radar chains are not tracked.",
    "encounter_pokemon": "Which Pokemon you have already encountered is not tracked.",
    "happiness_at_least": "Friendship is not tracked.",
    "beauty_at_least": "Contest beauty is not tracked.",
    "affection_at_least": "Affection is not tracked.",
    "overworld_rain": "Overworld weather is not tracked.",
    "device_upside_down": "Console orientation is not tracked.",
    "stat_relation": "Individual stat values are not tracked, so Attack/Defense comparisons stay unknown.",
}

STATUS_BY_RESULT = {True: "reachable", False: "locked", None: "unknown"}


@dataclass(frozen=True)
class TeamMember:
    pokemon: str
    level: int | None = None
    moves: tuple[str, ...] = ()
    nature: str | None = None
    ability: str | None = None
    held_item: str | None = None
    nickname: str | None = None


@dataclass(frozen=True)
class PlaythroughContext:
    game: str
    current_location: str | None = None
    visited_locations: tuple[str, ...] = ()
    completed_milestones: tuple[str, ...] = ()
    bag: tuple[str, ...] = ()
    trade_access: str = "none"
    spoiler_level: str = "hint"
    closed_world: frozenset[str] = frozenset()
    team: tuple[TeamMember, ...] = ()

    @property
    def locations(self) -> set[str]:
        """Visited locations, including the current one."""
        return {*self.visited_locations, *([self.current_location] if self.current_location else [])}


def _exists(db, sql: str, params) -> bool:
    return db.execute(sql, params).fetchone() is not None


def validate(db, scope: GameScope, ctx: PlaythroughContext) -> list[str]:
    """Resolve every identifier the player supplied against this game. Returns warnings.

    Unknown identifiers raise: a typo in a saved file must not quietly become a weaker claim. Things
    that are merely inapplicable to this game -- a nature in a game without natures -- are semantic
    errors, matching how the read endpoints already gate those mechanics.
    """
    warnings: list[str] = []
    for slug in ctx.locations:
        if not _exists(db, "SELECT 1 FROM locations WHERE slug=?", (slug,)):
            raise NotFound(f"Unknown location '{slug}'")
    for slug in ctx.completed_milestones:
        if not _exists(db, "SELECT 1 FROM milestones WHERE game_id=? AND slug=?", (scope.id, slug)):
            raise NotFound(f"'{slug}' is not a recorded milestone for {scope.slug}")
    for slug in ctx.bag:
        if not _exists(db, "SELECT 1 FROM items WHERE slug=?", (slug,)):
            raise NotFound(f"Unknown item '{slug}'")
    if ctx.trade_access not in ("none", "local", "any"):
        raise SemanticError(f"Unknown trade access '{ctx.trade_access}'")
    extra = ctx.closed_world - set(CLOSED_WORLD_FAMILIES)
    if extra:
        raise SemanticError(f"Unknown closed-world families {sorted(extra)}; choose from {sorted(CLOSED_WORLD_FAMILIES)}")

    for member in ctx.team:
        form = one(db, "SELECT id, slug FROM pokemon_forms WHERE slug=?", (member.pokemon,))
        if form is None:
            raise NotFound(f"Unknown Pokemon '{member.pokemon}'")
        if not _exists(db, "SELECT 1 FROM pokemon_version_groups WHERE form_id=? AND version_group_id=?", (form["id"], scope.version_group_id)):
            warnings.append(f"'{member.pokemon}' has no data for {scope.slug}; it is kept on the team but cannot be analysed.")
        for move in member.moves:
            move_row = one(db, "SELECT id FROM moves WHERE slug=?", (move,))
            if move_row is None:
                raise NotFound(f"Unknown move '{move}'")
            if not _exists(db, "SELECT 1 FROM move_game_data WHERE move_id=? AND version_group_id=?", (move_row["id"], scope.version_group_id)):
                raise SemanticError(f"'{move}' has no values in {scope.slug}; it does not exist in this game")
        if member.nature is not None:
            if scope.mechanics.get("natures") == 0:
                raise SemanticError(f"{scope.slug} has no Natures, so '{member.nature}' cannot be set")
            if not _exists(db, "SELECT 1 FROM natures WHERE slug=?", (member.nature,)):
                raise NotFound(f"Unknown nature '{member.nature}'")
        if member.ability is not None:
            if scope.mechanics.get("abilities") == 0:
                raise SemanticError(f"{scope.slug} has no Abilities, so '{member.ability}' cannot be set")
            if not _exists(db, "SELECT 1 FROM abilities WHERE slug=? AND generation_id<=?", (member.ability, scope.generation_id)):
                raise NotFound(f"Unknown ability '{member.ability}' for generation {scope.generation_id}")
        if member.held_item is not None:
            if scope.mechanics.get("held_items") == 0:
                raise SemanticError(f"{scope.slug} has no held items, so '{member.held_item}' cannot be set")
            if not _exists(db, "SELECT 1 FROM items WHERE slug=?", (member.held_item,)):
                raise NotFound(f"Unknown item '{member.held_item}'")
        if member.level is not None and not 1 <= member.level <= 100:
            raise SemanticError(f"Level {member.level} is out of range")
    return warnings


def condition_context(ctx: PlaythroughContext, member: TeamMember | None = None) -> tuple[dict, list[str]]:
    """Build the evaluation context, and the assumptions that explain every key we did and did not set."""
    context: dict = {}
    assumptions: list[str] = []
    for family, ops in CLOSED_WORLD_FAMILIES.items():
        closed = family in ctx.closed_world
        assumptions.append((CLOSED_WORLD_ASSUMED if closed else CLOSED_WORLD_OPEN)[family])
        if not closed:
            continue
        if family == "milestones":
            context["milestone"] = set(ctx.completed_milestones)
        elif family == "locations":
            context["at_location"] = ctx.locations
            # `in_region` stays absent even here: the playthrough records locations, not regions, and
            # a complete location list is not a complete region list.
        elif family == "bag":
            for op in ops:
                context[op] = set(ctx.bag)
        elif family == "party":
            party = {m.pokemon for m in ctx.team}
            context["has_pokemon"] = party
            context["party_has_pokemon"] = party
        elif family == "trade":
            context["trade"] = ctx.trade_access != "none"

    if member is not None:
        if member.level is not None:
            context["level"] = member.level
        if member.moves:
            context["knows_move"] = set(member.moves)
        if member.held_item is not None:
            context["held_item"] = {member.held_item}
    else:
        assumptions.append("No team member is in scope, so level, known moves and held item stay unknown.")
    return context, assumptions


def classify(condition: dict, context: dict) -> dict:
    """Three-valued verdict for one prerequisite, with the leaves that produced it.

    `unavailable` is never produced. It is reserved for reviewed evidence that something cannot be
    obtained, which no derivation can establish.
    """
    explained = explain_condition(condition, context)
    unresolved = []
    for leaf in explained["unresolved"]:
        entry = dict(leaf)
        if leaf["op"] != "unknown" and leaf["op"] in UNTRACKED_REASONS:
            entry["reason"] = UNTRACKED_REASONS[leaf["op"]]
        elif leaf["op"] != "unknown":
            entry.setdefault("reason", f"Your playthrough does not record {leaf['op'].replace('_', ' ')}.")
        unresolved.append(entry)
    return {
        "status": STATUS_BY_RESULT[explained["result"]],
        "evaluation": explained["result"],
        "blocked_by": explained["blocking"],
        "unknown_because": unresolved,
    }


@dataclass
class Resolved:
    """A validated context together with its scope and reusable assumptions."""

    scope: GameScope
    ctx: PlaythroughContext
    assumptions: list[str] = field(default_factory=list)
