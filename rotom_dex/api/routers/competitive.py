from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from rotom_dex.services import competitive

router = APIRouter()


class TeamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: str = Field(min_length=1, max_length=96)
    team: Annotated[str, Field(max_length=20000)] | Annotated[list[dict[str, Any]], Field(max_length=6)]


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["import", "export"]
    text: str = Field("", max_length=20000)
    team: list[dict[str, Any]] = Field(default_factory=list, max_length=6)


class Stats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hp: int | None = Field(None, ge=0, le=252)
    atk: int | None = Field(None, ge=0, le=252)
    def_: int | None = Field(None, alias="def", ge=0, le=252)
    spa: int | None = Field(None, ge=0, le=252)
    spd: int | None = Field(None, ge=0, le=252)
    spe: int | None = Field(None, ge=0, le=252)


class BattlePokemon(BaseModel):
    model_config = ConfigDict(extra="forbid")
    species: str = Field(min_length=1, max_length=80)
    name: str | None = Field(None, max_length=80)
    level: int | None = Field(None, ge=1, le=100)
    ability: str | None = Field(None, max_length=80)
    item: str | None = Field(None, max_length=80)
    nature: str | None = Field(None, max_length=80)
    gender: str | None = Field(None, max_length=1)
    evs: Stats | None = None
    ivs: Stats | None = None
    moves: list[str] = Field(default_factory=list, max_length=4)
    teraType: str | None = Field(None, max_length=20)
    isDynamaxed: bool = False
    dynamaxLevel: int | None = Field(None, ge=0, le=10)
    gigantamax: bool = False
    hpType: str | None = Field(None, max_length=20)
    pokeball: str | None = Field(None, max_length=40)
    shiny: bool = False
    happiness: int | None = Field(None, ge=0, le=255)


class BattleField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weather: Literal["Sun", "Rain", "Sand", "Hail", "Snow", "Harsh Sunshine", "Heavy Rain", "Strong Winds"] | None = None
    terrain: Literal["Electric", "Grassy", "Misty", "Psychic"] | None = None
    gameType: Literal["Singles", "Doubles"] = "Singles"
    isGravity: bool = False


class DamageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation: int = Field(ge=1, le=9)
    attacker: BattlePokemon
    defender: BattlePokemon
    move: str = Field(min_length=1, max_length=96)
    field: BattleField = Field(default_factory=BattleField)


@router.get("/competitive/formats")
def formats():
    return {"data": competitive.formats()}


@router.post("/competitive/validate")
def validate(body: TeamRequest):
    return {"data": competitive.run("validate", **body.model_dump())}


@router.post("/competitive/team")
def transfer(body: TransferRequest):
    return {"data": competitive.run(**body.model_dump())}


@router.post("/competitive/damage")
def damage(body: DamageRequest):
    return {"data": competitive.run("damage", **body.model_dump(exclude_none=True, by_alias=True))}
