"""Immutable records for the SQLite foundation; IDs follow PokéAPI where possible."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class GameVersion:
    table: ClassVar[str] = "game_versions"
    id: int
    slug: str
    version_group_id: int
    version_group: str
    generation: int
    support_status: str
    evidence_id: str


@dataclass(frozen=True)
class Species:
    table: ClassVar[str] = "species"
    id: int
    slug: str
    evidence_id: str


@dataclass(frozen=True)
class PokemonForm:
    table: ClassVar[str] = "pokemon_forms"
    id: int
    species_id: int
    slug: str
    form_name: str
    height_dm: int
    weight_hg: int
    evidence_id: str


@dataclass(frozen=True)
class PokemonGameData:
    table: ClassVar[str] = "pokemon_game_data"
    form_id: int
    game_id: int
    availability: str
    evidence_id: str


@dataclass(frozen=True)
class PokemonType:
    table: ClassVar[str] = "pokemon_types"
    form_id: int
    game_id: int
    slot: int
    type_id: int
    evidence_id: str


@dataclass(frozen=True)
class PokemonStat:
    table: ClassVar[str] = "pokemon_stats"
    form_id: int
    game_id: int
    stat: str
    base_stat: int
    evidence_id: str


@dataclass(frozen=True)
class Ability:
    table: ClassVar[str] = "abilities"
    id: int
    slug: str
    evidence_id: str


@dataclass(frozen=True)
class PokemonAbility:
    table: ClassVar[str] = "pokemon_abilities"
    form_id: int
    game_id: int
    slot: int
    ability_id: int
    is_hidden: bool
    evidence_id: str


@dataclass(frozen=True)
class Move:
    table: ClassVar[str] = "moves"
    id: int
    slug: str
    evidence_id: str


@dataclass(frozen=True)
class MoveGameData:
    table: ClassVar[str] = "move_game_data"
    move_id: int
    game_id: int
    type_id: int
    damage_class: str
    power: int | None
    accuracy: int | None
    pp: int
    effect: str | None
    evidence_id: str


@dataclass(frozen=True)
class LearnsetEntry:
    table: ClassVar[str] = "learnsets"
    form_id: int
    game_id: int
    move_id: int
    method: str
    level: int
    machine_item_id: int | None
    evidence_id: str


@dataclass(frozen=True)
class EvolutionRule:
    table: ClassVar[str] = "evolution_rules"
    id: int
    game_id: int
    from_form_id: int
    to_form_id: int
    trigger: str
    conditions: dict
    evidence_id: str


@dataclass(frozen=True)
class Item:
    table: ClassVar[str] = "items"
    id: int
    slug: str
    evidence_id: str


@dataclass(frozen=True)
class ItemGameData:
    table: ClassVar[str] = "item_game_data"
    item_id: int
    game_id: int
    effect: str | None
    evidence_id: str


@dataclass(frozen=True)
class Location:
    table: ClassVar[str] = "locations"
    id: int
    game_id: int
    slug: str
    area: str
    evidence_id: str


@dataclass(frozen=True)
class Acquisition:
    table: ClassVar[str] = "acquisitions"
    id: str
    game_id: int
    form_id: int | None
    item_id: int | None
    location_id: int | None
    method: str
    min_level: int | None
    max_level: int | None
    chance_percent: int | None
    availability: str
    prerequisites: dict
    encounter_conditions: dict
    evidence_id: str


@dataclass(frozen=True)
class Nature:
    table: ClassVar[str] = "natures"
    id: int
    game_id: int
    slug: str
    increased_stat: str
    decreased_stat: str
    evidence_id: str


@dataclass(frozen=True)
class Type:
    table: ClassVar[str] = "types"
    id: int
    slug: str
    evidence_id: str


@dataclass(frozen=True)
class TypeEffectiveness:
    table: ClassVar[str] = "type_effectiveness"
    game_id: int
    attack_type_id: int
    defense_type_id: int
    damage_factor: int
    evidence_id: str


@dataclass(frozen=True)
class SourceReference:
    table: ClassVar[str] = "sources"
    id: str
    url: str
    retrieved_at: str
    sha256: str
    snapshot_id: str
    local_path: str
    review_status: str


@dataclass(frozen=True)
class Coverage:
    table: ClassVar[str] = "coverage"
    game_id: int
    subject: str
    feature: str
    status: str
    note: str
    evidence_id: str
