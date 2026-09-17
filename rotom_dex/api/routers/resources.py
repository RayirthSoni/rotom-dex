"""Moves, items, abilities, machines, locations and progression."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from rotom_dex.api.deps import GameParam, LimitParam, OffsetParam, QParam, get_db
from rotom_dex.api.schemas import Envelope
from rotom_dex.repositories import abilities as abilities_repo
from rotom_dex.repositories import items as items_repo
from rotom_dex.repositories import locations as locations_repo
from rotom_dex.repositories import moves as moves_repo
from rotom_dex.repositories import progression as progression_repo
from rotom_dex.repositories.common import envelope, resolve_game, rows, unsupported

router = APIRouter()


@router.get("/moves", response_model=Envelope)
def search_moves(
    game: str = GameParam,
    q: str | None = QParam,
    type: str | None = Query(None, max_length=20),
    damage_class: str | None = Query(None, pattern="^(physical|special|status)$"),
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return moves_repo.search_moves(db, game, q, type, damage_class, limit, offset)


@router.get("/moves/{move}", response_model=Envelope)
def move_detail(move: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return moves_repo.move_detail(db, game, move)


@router.get("/moves/{move}/learners", response_model=Envelope)
def move_learners(
    move: str,
    game: str = GameParam,
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return moves_repo.move_learners(db, game, move, limit, offset)


@router.get("/items", response_model=Envelope)
def search_items(
    game: str = GameParam,
    q: str | None = QParam,
    category: str | None = Query(None, max_length=40),
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return items_repo.search_items(db, game, q, category, limit, offset)


@router.get("/items/{item}", response_model=Envelope)
def item_detail(item: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return items_repo.item_detail(db, game, item)


@router.get("/abilities", response_model=Envelope)
def search_abilities(
    game: str = GameParam,
    q: str | None = QParam,
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return abilities_repo.search_abilities(db, game, q, limit, offset)


@router.get("/abilities/{ability}", response_model=Envelope)
def ability_detail(ability: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return abilities_repo.ability_detail(db, game, ability)


@router.get("/machines", response_model=Envelope)
def machines(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    found = rows(
        db,
        """SELECT mc.kind, mc.machine_number, i.slug AS item, i.name AS item_name, m.slug AS move,
                        m.name AS move_name, t.slug AS type, mc.evidence_id FROM machines mc
                        JOIN items i ON i.id=mc.item_id JOIN moves m ON m.id=mc.move_id
                        JOIN move_game_data mg ON mg.move_id=mc.move_id AND mg.version_group_id=mc.version_group_id
                        JOIN types t ON t.id=mg.type_id WHERE mc.version_group_id=?
                        ORDER BY mc.kind, mc.machine_number""",
        (scope.version_group_id,),
    )
    data = {
        "machines": found,
        "rules": {k: scope.mechanics.get(k) for k in ("tm_present", "tm_reusable", "hm_present", "tr_present")},
    }
    return envelope(
        db,
        scope,
        data,
        features=("machines",),
        include_evidence=False,
        assumptions=["Machine locations, prices and one-time availability are not in the source; see item acquisition."],
    )


@router.get("/tutors", response_model=Envelope)
def tutors(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    """Move tutors: where a tutor stands and what it charges.

    Separate from the `tutor` rows in a learnset, which establish only that a Pokemon is *eligible*.
    The pinned source carries no tutor locations, so this list is empty for every game and the
    coverage row says so; that is why tutor access is reported as unknown rather than unavailable.
    """
    scope = resolve_game(db, game)
    if not scope.imported:
        return unsupported(db, scope)
    found = rows(
        db,
        """SELECT t.id, m.slug AS move, m.name AS move_name, l.slug AS location, l.name AS location_name,
                  i.slug AS cost_item, t.cost_amount, t.prerequisites, t.verification_status, t.evidence_id
           FROM tutors t JOIN moves m ON m.id=t.move_id
           LEFT JOIN locations l ON l.id=t.location_id LEFT JOIN items i ON i.id=t.cost_item_id
           WHERE t.version_group_id=? ORDER BY m.slug""",
        (scope.version_group_id,),
    )
    eligible = db.execute(
        "SELECT count(*) FROM learnsets WHERE version_group_id=? AND method='tutor'",
        (scope.version_group_id,),
    ).fetchone()[0]
    data = {"tutors": found, "eligible_learnset_rows": eligible}
    return envelope(
        db,
        scope,
        data,
        features=("tutors",),
        assumptions=[
            f"{eligible} learnset rows say a Pokemon can be taught a move by a tutor in this version group; "
            f"{len(found)} tutor locations are recorded. Eligibility is established, access is not.",
        ],
    )


@router.get("/locations", response_model=Envelope)
def search_locations(
    game: str = GameParam,
    q: str | None = QParam,
    limit: int = LimitParam,
    offset: int = OffsetParam,
    db: sqlite3.Connection = Depends(get_db),
):
    return locations_repo.search_locations(db, game, q, limit, offset)


@router.get("/locations/{location}/encounters", response_model=Envelope)
def location_encounters(location: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return locations_repo.location_encounters(db, game, location)


@router.get("/milestones", response_model=Envelope)
def milestones(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return progression_repo.list_milestones(db, game)


@router.get("/battles", response_model=Envelope)
def battles(game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return progression_repo.list_battles(db, game)


@router.get("/battles/{battle}", response_model=Envelope)
def battle_detail(battle: str, game: str = GameParam, db: sqlite3.Connection = Depends(get_db)):
    return progression_repo.battle_detail(db, game, battle)
