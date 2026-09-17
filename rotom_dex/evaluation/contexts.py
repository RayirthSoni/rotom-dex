"""Named playthrough fixtures the question set refers to.

A case says "mid-emerald" rather than repeating a context, so a question's expectation is anchored
to a described point in a playthrough rather than to a wall of fields.
"""

from __future__ import annotations

from rotom_dex.services.context import PlaythroughContext, TeamMember

EMERALD_EARLY = ("littleroot-arrival", "starter-chosen", "pokedex-received", "rival-route-103", "petalburg-wally", "hm01-cut", "stone-badge")
EMERALD_MID = EMERALD_EARLY + (
    "devon-goods",
    "briney-ferry",
    "knuckle-badge",
    "hm05-flash",
    "steven-letter",
    "slateport-arrival",
    "oceanic-museum",
    "mauville-arrival",
    "hm06-rock-smash",
    "wally-mauville",
    "dynamo-badge",
    "hm04-strength",
    "meteor-falls-theft",
    "mt-chimney-showdown",
    "heat-badge",
    "go-goggles",
    "balance-badge",
    "hm03-surf",
)
RED_EARLY = ("pallet-departure", "oaks-parcel", "pokedex-received", "viridian-forest", "boulder-badge")
RED_MID = RED_EARLY + (
    "mt-moon-crossed",
    "cerulean-arrival",
    "cascade-badge",
    "bill-ss-ticket",
    "ss-anne",
    "thunder-badge",
    "rock-tunnel-crossed",
    "lavender-arrival",
    "rainbow-badge",
    "rocket-hideout",
    "pokemon-tower",
    "snorlax-cleared",
    "soul-badge",
    "hm03-surf",
)

MILESTONES = frozenset({"milestones"})


def _all(db, game_id: int) -> tuple[str, ...]:
    return tuple(r[0] for r in db.execute("SELECT slug FROM milestones WHERE game_id=? ORDER BY ord", (game_id,)))


def build(name: str, game: str, db, game_id: int) -> PlaythroughContext:
    if name == "none":
        return PlaythroughContext(game=game)
    if name == "early-emerald":
        return PlaythroughContext(game=game, completed_milestones=EMERALD_EARLY, closed_world=MILESTONES)
    if name == "mid-emerald":
        return PlaythroughContext(game=game, completed_milestones=EMERALD_MID, closed_world=MILESTONES)
    if name == "open-emerald":
        return PlaythroughContext(game=game, completed_milestones=EMERALD_EARLY)
    if name == "early-red":
        return PlaythroughContext(game=game, completed_milestones=RED_EARLY, closed_world=MILESTONES)
    if name == "mid-red":
        return PlaythroughContext(game=game, completed_milestones=RED_MID, closed_world=MILESTONES)
    if name == "open-red":
        return PlaythroughContext(game=game, completed_milestones=RED_EARLY)
    if name == "early-emerald-hint":
        return PlaythroughContext(game=game, completed_milestones=EMERALD_EARLY, closed_world=MILESTONES, spoiler_level="hint")
    if name == "early-emerald-none":
        return PlaythroughContext(game=game, completed_milestones=EMERALD_EARLY, closed_world=MILESTONES, spoiler_level="none")
    if name == "early-red-hint":
        return PlaythroughContext(game=game, completed_milestones=RED_EARLY, closed_world=MILESTONES, spoiler_level="hint")
    if name == "early-red-none":
        return PlaythroughContext(game=game, completed_milestones=RED_EARLY, closed_world=MILESTONES, spoiler_level="none")
    if name in ("late-emerald-full", "late-red-full"):
        return PlaythroughContext(game=game, completed_milestones=_all(db, game_id), closed_world=MILESTONES, spoiler_level="full")
    if name == "team-emerald":
        return PlaythroughContext(
            game=game,
            completed_milestones=EMERALD_EARLY,
            closed_world=MILESTONES,
            team=(
                TeamMember(pokemon="grovyle", level=18, moves=("absorb", "pursuit", "quick-attack")),
                TeamMember(pokemon="marshtomp", level=17, moves=("water-gun", "mud-shot")),
            ),
        )
    raise ValueError(f"Unknown evaluation context '{name}'")
