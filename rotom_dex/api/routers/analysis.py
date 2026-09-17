"""Playthrough-aware analysis: team, boss preparation, reachability, move access, evolution.

POST because the body is a playthrough context held in the player's browser, not a resource
identifier. The context is validated against the requested game before anything is derived, and the
response is the same envelope the read endpoints use, so coverage, assumptions and evidence travel
with every answer.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from rotom_dex.api.deps import get_db
from rotom_dex.api.requests import (
    BossPrepareIn,
    EvolutionRequirementsIn,
    MoveAccessIn,
    PlaythroughContextIn,
    ReachabilityIn,
    TeamAnalyzeIn,
)
from rotom_dex.api.schemas import Envelope
from rotom_dex.errors import SemanticError
from rotom_dex.repositories.common import GameScope, envelope, resolve_game, unsupported
from rotom_dex.services import boss, evolution, move_access, reachability, team
from rotom_dex.services.context import PlaythroughContext, TeamMember, validate

router = APIRouter()


def _resolve(db: sqlite3.Connection, body: PlaythroughContextIn) -> tuple[GameScope, PlaythroughContext, list[str]]:
    scope = resolve_game(db, body.game)
    ctx = body.to_domain()
    warnings = validate(db, scope, ctx) if scope.imported else []
    return scope, ctx, warnings


def _member(ctx: PlaythroughContext, index: int | None) -> TeamMember | None:
    if index is None:
        return None
    if index >= len(ctx.team):
        raise SemanticError(f"No team member at index {index}; the team has {len(ctx.team)}")
    return ctx.team[index]


@router.post("/team/analyze", response_model=Envelope)
def team_analyze(body: TeamAnalyzeIn, db: sqlite3.Connection = Depends(get_db)):
    """Defensive profile per member and offensive coverage from the team's actual moves."""
    scope, ctx, warnings = _resolve(db, body.context)
    if not scope.imported:
        return unsupported(db, scope)
    data = team.analyse(db, scope, ctx, warnings)
    return envelope(
        db,
        scope,
        data,
        features=team.FEATURES,
        include_evidence=False,
        assumptions=[*team.ASSUMPTIONS, *warnings],
    )


@router.post("/boss/prepare", response_model=Envelope)
def boss_prepare(body: BossPrepareIn, db: sqlite3.Connection = Depends(get_db)):
    """Preparation for a reviewed boss battle. Never a prediction of the result."""
    scope, ctx, warnings = _resolve(db, body.context)
    if not scope.imported:
        return unsupported(db, scope)
    result = boss.prepare(db, scope, ctx, body.battle)
    if result.get("data", False) is None:
        return envelope(db, scope, None, features=("boss-teams",), assumptions=[*result["assumptions"], *warnings])
    assumptions = [*boss.ASSUMPTIONS, *result["assumptions"], *warnings]
    return envelope(db, scope, result, features=("boss-teams", "progression", "shops"), include_evidence=False, assumptions=assumptions)


@router.post("/acquisition/reachability", response_model=Envelope)
def acquisition_reachability(body: ReachabilityIn, db: sqlite3.Connection = Depends(get_db)):
    """What your recorded progress settles about obtaining these Pokemon and items."""
    scope, ctx, warnings = _resolve(db, body.context)
    if not scope.imported:
        return unsupported(db, scope)
    if not body.pokemon and not body.items:
        raise SemanticError("Name at least one Pokemon or item to check")
    pokemon = [reachability.for_pokemon(db, scope, ctx, slug.lower()) for slug in body.pokemon]
    items = [reachability.for_item(db, scope, ctx, slug.lower()) for slug in body.items]
    shared = next((r["assumptions"] for r in [*pokemon, *items] if "assumptions" in r), [])
    data = {"pokemon": pokemon, "items": items, "closed_world": sorted(ctx.closed_world)}
    return envelope(
        db,
        scope,
        data,
        features=("encounters", "gifts-trades", "breeding", "evolution", "item-acquisition", "shops"),
        include_evidence=False,
        assumptions=[reachability.ASSUMPTION, *shared, *warnings],
    )


@router.post("/pokemon/{pokemon}/move-access", response_model=Envelope)
def pokemon_move_access(pokemon: str, body: MoveAccessIn, db: sqlite3.Connection = Depends(get_db)):
    """Every move this Pokemon is eligible for, with access to the teaching method reported separately."""
    scope, ctx, warnings = _resolve(db, body.context)
    if not scope.imported:
        return unsupported(db, scope)
    result = move_access.eligibility(db, scope, ctx, pokemon.lower(), _member(ctx, body.member))
    if result.get("data", False) is None:
        return envelope(db, scope, None, features=("learnsets",), assumptions=[*result["assumptions"], *warnings])
    return envelope(
        db,
        scope,
        result,
        features=("learnsets", "machines", "tutors", "breeding", "item-acquisition"),
        include_evidence=False,
        assumptions=[move_access.ASSUMPTION, *result["assumptions"], *warnings],
    )


@router.post("/pokemon/{pokemon}/evolution-requirements", response_model=Envelope)
def pokemon_evolution_requirements(pokemon: str, body: EvolutionRequirementsIn, db: sqlite3.Connection = Depends(get_db)):
    """Evolution rules for this Pokemon, evaluated against your progress."""
    scope, ctx, warnings = _resolve(db, body.context)
    if not scope.imported:
        return unsupported(db, scope)
    result = evolution.requirements(db, scope, ctx, pokemon.lower(), _member(ctx, body.member))
    if result.get("data", False) is None:
        return envelope(db, scope, None, features=("evolution",), assumptions=[*result["assumptions"], *warnings])
    return envelope(
        db,
        scope,
        result,
        features=("evolution",),
        include_evidence=False,
        assumptions=[evolution.ASSUMPTION, *result["assumptions"], *warnings],
    )
