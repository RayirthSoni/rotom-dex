"""Games, coverage, issues, evidence, types and natures."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from rotom_dex.api.deps import GameParam, get_db
from rotom_dex.api.schemas import Envelope
from rotom_dex.repositories import games as games_repo
from rotom_dex.repositories import natures as natures_repo
from rotom_dex.repositories import types as types_repo
from rotom_dex.repositories.common import coverage_rows, envelope, resolve_game
from rotom_dex.repositories.evidence import evidence_detail

router = APIRouter()


@router.get("/games", response_model=Envelope)
def list_games(db: sqlite3.Connection = Depends(get_db)):
    return games_repo.list_games(db)


@router.get("/games/{game}", response_model=Envelope)
def game_detail(game: str, db: sqlite3.Connection = Depends(get_db)):
    return games_repo.game_detail(db, game)


@router.get("/coverage", response_model=Envelope)
def coverage(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    scope = resolve_game(db, game)
    rows_ = coverage_rows(db, scope.id)
    return envelope(db, scope, rows_, coverage=rows_, include_evidence=False)


@router.get("/issues", response_model=Envelope)
def issues(game: str | None = Query(None), db: sqlite3.Connection = Depends(get_db)):
    scope = resolve_game(db, game) if game else None
    return games_repo.issues(db, scope)


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, db: sqlite3.Connection = Depends(get_db)):
    return evidence_detail(db, evidence_id)


@router.get("/types", response_model=Envelope)
def list_types(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return types_repo.list_types(db, game)


@router.get("/type-effectiveness", response_model=Envelope)
def matchup(
    game: str = GameParam,
    attack: str = Query(..., min_length=1),
    defense: str = Query(..., min_length=1),
    defense2: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    return types_repo.matchup(db, game, attack, defense, defense2)


@router.get("/type-effectiveness/chart", response_model=Envelope)
def chart(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return types_repo.chart(db, game)


@router.get("/natures", response_model=Envelope)
def list_natures(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return natures_repo.list_natures(db, game)


@router.get("/natures/{nature}", response_model=Envelope)
def nature_detail(nature: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return natures_repo.nature_detail(db, game, nature)
