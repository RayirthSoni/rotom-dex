"""Request bodies for the playthrough-aware services.

Shape is enforced here; meaning is enforced by `rotom_dex.services.context.validate`, which resolves
every identifier against the requested game. `extra="forbid"` throughout: a stray key from a
hand-edited save file should be reported, not silently ignored.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rotom_dex.services.context import PlaythroughContext, TeamMember

CLOSED_WORLD = Literal["milestones", "locations", "bag", "party", "trade"]


class TeamMemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pokemon: str = Field(min_length=1, max_length=64, description="Form slug, e.g. ralts")
    level: int | None = Field(None, ge=1, le=100)
    moves: list[str] = Field(default_factory=list, max_length=4)
    nature: str | None = Field(None, max_length=64)
    ability: str | None = Field(None, max_length=64)
    held_item: str | None = Field(None, max_length=64)
    nickname: str | None = Field(None, max_length=24)

    def to_domain(self) -> TeamMember:
        return TeamMember(
            pokemon=self.pokemon.lower(),
            level=self.level,
            moves=tuple(m.lower() for m in self.moves),
            nature=self.nature.lower() if self.nature else None,
            ability=self.ability.lower() if self.ability else None,
            held_item=self.held_item.lower() if self.held_item else None,
            nickname=self.nickname,
        )


class PlaythroughContextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game: str = Field(min_length=1, max_length=64, description="Exact game slug, e.g. emerald")
    current_location: str | None = Field(None, max_length=64)
    visited_locations: list[str] = Field(default_factory=list, max_length=1000)
    completed_milestones: list[str] = Field(default_factory=list, max_length=500)
    bag: list[str] = Field(default_factory=list, max_length=500)
    trade_access: Literal["none", "local", "any"] = "none"
    spoiler_level: Literal["none", "hint", "full"] = "hint"
    closed_world: list[CLOSED_WORLD] = Field(
        default_factory=list,
        description="Leaf families you vouch for as complete. Anything listed here may evaluate to locked; anything omitted stays unknown.",
    )
    team: list[TeamMemberIn] = Field(default_factory=list, max_length=6)

    def to_domain(self) -> PlaythroughContext:
        return PlaythroughContext(
            game=self.game.lower(),
            current_location=self.current_location.lower() if self.current_location else None,
            visited_locations=tuple(v.lower() for v in self.visited_locations),
            completed_milestones=tuple(m.lower() for m in self.completed_milestones),
            bag=tuple(b.lower() for b in self.bag),
            trade_access=self.trade_access,
            spoiler_level=self.spoiler_level,
            closed_world=frozenset(self.closed_world),
            team=tuple(m.to_domain() for m in self.team),
        )


class TeamAnalyzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: PlaythroughContextIn


class BossPrepareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: PlaythroughContextIn
    battle: str = Field(min_length=1, max_length=96)


class ReachabilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: PlaythroughContextIn
    pokemon: list[str] = Field(default_factory=list, max_length=25)
    items: list[str] = Field(default_factory=list, max_length=25)


class MoveAccessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: PlaythroughContextIn
    pokemon: str = Field(min_length=1, max_length=64)
    member: int | None = Field(None, ge=0, le=5, description="Index into context.team, so level and known moves are taken into account")


class EvolutionRequirementsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: PlaythroughContextIn
    pokemon: str = Field(min_length=1, max_length=64)
    member: int | None = Field(None, ge=0, le=5)


class ChatTurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=2000)


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: PlaythroughContextIn
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurnIn] = Field(default_factory=list, max_length=12)
