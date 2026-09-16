"""Pokémon search, detail and sub-resources."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from rotom_dex.api.deps import GameParam, LimitParam, OffsetParam, QParam, get_db
from rotom_dex.api.schemas import Envelope
from rotom_dex.repositories import pokemon as repo

router = APIRouter(prefix="/pokemon")


@router.get("", response_model=Envelope)
def search(
    game: str = GameParam,
    q: str | None = QParam,
    type: str | None = Query(None, max_length=20),
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return repo.search_pokemon(db, game, q, type, limit, offset)


@router.get("/{pokemon}", response_model=Envelope)
def detail(pokemon: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return repo.pokemon_core(db, game, pokemon)


@router.get("/{pokemon}/acquisition", response_model=Envelope)
def acquisition(pokemon: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return repo.pokemon_acquisition(db, game, pokemon)


@router.get("/{pokemon}/evolution", response_model=Envelope)
def evolution(pokemon: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return repo.pokemon_evolution(db, game, pokemon)


@router.get("/{pokemon}/learnset", response_model=Envelope)
def learnset(
    pokemon: str,
    game: str = GameParam,
    method: str | None = Query(None, max_length=40),
    max_level: int | None = Query(None, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    return repo.pokemon_learnset(db, game, pokemon, method, max_level)
