"""Immutable records, one per table. IDs follow PokéAPI where a PokéAPI entity exists.

Scope columns follow the schema: generation_id for battle data, version_group_id for
moves/learnsets/items, game_id for encounters, acquisitions, progression and coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

SOURCE_DERIVED = "source-derived"
REFERENCE_REVIEWED = "reference-reviewed"
UNVERIFIED = "unverified"
DISPUTED = "disputed"
VERIFICATION_STATUSES = (SOURCE_DERIVED, REFERENCE_REVIEWED, UNVERIFIED, DISPUTED)


@dataclass(frozen=True)
class Snapshot:
    table: ClassVar[str] = "snapshots"
    id: str
    created_at: str
    manifest_sha256: str
    packs_sha256: str
    normalizer: str


@dataclass(frozen=True)
class SourceReference:
    table: ClassVar[str] = "sources"
    id: str
    kind: str
    url: str
    retrieved_at: str
    sha256: str | None
    license: str
    local_path: str | None
    review_status: str
    snapshot_id: str


@dataclass(frozen=True)
class Generation:
    table: ClassVar[str] = "generations"
    id: int
    slug: str
    name: str
    evidence_id: str


@dataclass(frozen=True)
class VersionGroup:
    table: ClassVar[str] = "version_groups"
    id: int
    slug: str
    name: str
    generation_id: int
    ord: int
    evidence_id: str


@dataclass(frozen=True)
class GameVersion:
    table: ClassVar[str] = "game_versions"
    id: int
    slug: str
    name: str
    version_group_id: int
    is_main_series: bool
    support_tier: str
    note: str
    evidence_id: str


@dataclass(frozen=True)
class Region:
    table: ClassVar[str] = "regions"
    id: int
    slug: str
    name: str
    evidence_id: str


@dataclass(frozen=True)
class VersionGroupRegion:
    table: ClassVar[str] = "version_group_regions"
    version_group_id: int
    region_id: int


@dataclass(frozen=True)
class GameMechanic:
    table: ClassVar[str] = "game_mechanics"
    version_group_id: int
    key: str
    value: int
    note: str
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class Type:
    table: ClassVar[str] = "types"
    id: int
    slug: str
    name: str
    generation_id: int
    evidence_id: str


@dataclass(frozen=True)
class TypeEffectiveness:
    table: ClassVar[str] = "type_effectiveness"
    generation_id: int
    attack_type_id: int
    defense_type_id: int
    damage_factor: int
    evidence_id: str


@dataclass(frozen=True)
class Species:
    table: ClassVar[str] = "species"
    id: int
    slug: str
    name: str
    generation_id: int
    evolves_from_species_id: int | None
    evolution_chain_id: int | None
    gender_rate: int | None
    capture_rate: int | None
    base_happiness: int | None
    hatch_counter: int | None
    growth_rate: str | None
    is_baby: bool
    is_legendary: bool
    is_mythical: bool
    evidence_id: str


@dataclass(frozen=True)
class PokemonForm:
    table: ClassVar[str] = "pokemon_forms"
    id: int
    species_id: int
    slug: str
    name: str
    is_default: bool
    height_dm: int | None
    weight_hg: int | None
    base_experience: int | None
    ord: int | None
    evidence_id: str


@dataclass(frozen=True)
class FormVariant:
    table: ClassVar[str] = "form_variants"
    id: int
    form_id: int
    slug: str
    form_name: str
    is_default: bool
    is_mega: bool
    is_battle_only: bool
    introduced_in_version_group_id: int | None
    evidence_id: str


@dataclass(frozen=True)
class PokemonEggGroup:
    table: ClassVar[str] = "pokemon_egg_groups"
    species_id: int
    egg_group: str
    evidence_id: str


@dataclass(frozen=True)
class Pokedex:
    table: ClassVar[str] = "pokedexes"
    id: int
    slug: str
    name: str
    region_id: int | None
    is_main_series: bool
    evidence_id: str


@dataclass(frozen=True)
class PokedexVersionGroup:
    table: ClassVar[str] = "pokedex_version_groups"
    pokedex_id: int
    version_group_id: int


@dataclass(frozen=True)
class PokemonDexNumber:
    table: ClassVar[str] = "pokemon_dex_numbers"
    species_id: int
    pokedex_id: int
    number: int
    evidence_id: str


@dataclass(frozen=True)
class PokemonType:
    table: ClassVar[str] = "pokemon_types"
    form_id: int
    generation_id: int
    slot: int
    type_id: int
    evidence_id: str


@dataclass(frozen=True)
class PokemonStat:
    table: ClassVar[str] = "pokemon_stats"
    form_id: int
    generation_id: int
    stat: str
    base_stat: int
    effort: int
    evidence_id: str


@dataclass(frozen=True)
class Ability:
    table: ClassVar[str] = "abilities"
    id: int
    slug: str
    name: str
    generation_id: int
    is_main_series: bool
    evidence_id: str


@dataclass(frozen=True)
class PokemonAbility:
    table: ClassVar[str] = "pokemon_abilities"
    form_id: int
    generation_id: int
    slot: int
    ability_id: int
    is_hidden: bool
    evidence_id: str


@dataclass(frozen=True)
class PokemonVersionGroup:
    table: ClassVar[str] = "pokemon_version_groups"
    form_id: int
    version_group_id: int
    presence: str
    evidence_id: str


@dataclass(frozen=True)
class AbilityEffect:
    table: ClassVar[str] = "ability_effects"
    ability_id: int
    short_effect: str
    effect: str
    wording: str
    evidence_id: str


@dataclass(frozen=True)
class AbilityTypeEffect:
    table: ClassVar[str] = "ability_type_effects"
    id: str
    ability_id: int
    generation_id: int
    applies_to: str
    type_id: int | None
    damage_factor: int
    note: str
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class AbilityFlavorText:
    table: ClassVar[str] = "ability_flavor_text"
    ability_id: int
    version_group_id: int
    text: str
    evidence_id: str


@dataclass(frozen=True)
class AbilityChange:
    table: ClassVar[str] = "ability_changes"
    ability_id: int
    changed_in_version_group_id: int
    effect: str
    evidence_id: str


@dataclass(frozen=True)
class Move:
    table: ClassVar[str] = "moves"
    id: int
    slug: str
    name: str
    generation_id: int
    evidence_id: str


@dataclass(frozen=True)
class MoveEffect:
    table: ClassVar[str] = "move_effects"
    id: int
    short_effect: str
    effect: str
    wording: str
    evidence_id: str


@dataclass(frozen=True)
class MoveGameData:
    table: ClassVar[str] = "move_game_data"
    move_id: int
    version_group_id: int
    type_id: int
    damage_class: str
    power: int | None
    accuracy: int | None
    pp: int | None
    priority: int
    target: str
    effect_id: int | None
    effect_chance: int | None
    evidence_id: str


@dataclass(frozen=True)
class MoveFlavorText:
    table: ClassVar[str] = "move_flavor_text"
    move_id: int
    version_group_id: int
    text: str
    evidence_id: str


@dataclass(frozen=True)
class MoveMeta:
    table: ClassVar[str] = "move_meta"
    move_id: int
    category: str
    ailment: str
    min_hits: int | None
    max_hits: int | None
    min_turns: int | None
    max_turns: int | None
    drain: int
    healing: int
    crit_rate: int
    ailment_chance: int
    flinch_chance: int
    stat_chance: int
    evidence_id: str


@dataclass(frozen=True)
class MoveFlag:
    table: ClassVar[str] = "move_flags"
    move_id: int
    flag: str
    evidence_id: str


@dataclass(frozen=True)
class LearnsetEntry:
    table: ClassVar[str] = "learnsets"
    form_id: int
    version_group_id: int
    move_id: int
    method: str
    level: int
    ord: int | None
    evidence_id: str


@dataclass(frozen=True)
class Item:
    table: ClassVar[str] = "items"
    id: int
    slug: str
    name: str
    category: str
    pocket: str
    default_cost: int | None
    fling_power: int | None
    evidence_id: str


@dataclass(frozen=True)
class Machine:
    table: ClassVar[str] = "machines"
    version_group_id: int
    machine_number: int
    kind: str
    item_id: int
    move_id: int
    evidence_id: str


@dataclass(frozen=True)
class Tutor:
    table: ClassVar[str] = "tutors"
    id: str
    version_group_id: int
    move_id: int
    location_id: int | None
    cost_item_id: int | None
    cost_amount: int | None
    prerequisites: dict
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class EvolutionRule:
    table: ClassVar[str] = "evolution_rules"
    id: int
    from_form_id: int
    to_form_id: int
    trigger: str
    introduced_version_group_id: int | None
    conditions: dict
    raw: dict
    evidence_id: str


@dataclass(frozen=True)
class EvolutionApplicability:
    table: ClassVar[str] = "evolution_applicability"
    rule_id: int
    version_group_id: int
    status: str
    reason: str
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class Location:
    table: ClassVar[str] = "locations"
    id: int
    region_id: int | None
    slug: str
    name: str
    evidence_id: str


@dataclass(frozen=True)
class LocationArea:
    table: ClassVar[str] = "location_areas"
    id: int
    location_id: int
    slug: str
    name: str
    evidence_id: str


@dataclass(frozen=True)
class EncounterRate:
    table: ClassVar[str] = "encounter_rates"
    location_area_id: int
    method: str
    game_id: int
    rate: int
    evidence_id: str


@dataclass(frozen=True)
class Acquisition:
    table: ClassVar[str] = "acquisitions"
    id: str
    game_id: int
    form_id: int | None
    item_id: int | None
    location_id: int | None
    location_area_id: int | None
    method: str
    min_level: int | None
    max_level: int | None
    chance_percent: int | None
    availability: str
    prerequisites: dict
    encounter_conditions: dict
    verification_status: str
    note: str
    evidence_id: str


@dataclass(frozen=True)
class PokemonHeldItem:
    table: ClassVar[str] = "pokemon_held_items"
    form_id: int
    game_id: int
    item_id: int
    rarity: int
    evidence_id: str


@dataclass(frozen=True)
class ItemGeneration:
    table: ClassVar[str] = "item_generations"
    item_id: int
    generation_id: int
    game_index: int
    evidence_id: str


@dataclass(frozen=True)
class ItemGameData:
    table: ClassVar[str] = "item_game_data"
    item_id: int
    version_group_id: int
    flavor_text: str | None
    purchase_price: int | None
    sell_price: int | None
    price_provenance: str
    evidence_id: str


@dataclass(frozen=True)
class ItemEffect:
    table: ClassVar[str] = "item_effects"
    item_id: int
    short_effect: str
    effect: str
    wording: str
    evidence_id: str


@dataclass(frozen=True)
class ItemAttribute:
    table: ClassVar[str] = "item_attributes"
    item_id: int
    flag: str
    evidence_id: str


@dataclass(frozen=True)
class Shop:
    table: ClassVar[str] = "shops"
    id: str
    game_id: int
    location_id: int | None
    name: str
    prerequisites: dict
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class ShopItem:
    table: ClassVar[str] = "shop_items"
    shop_id: str
    item_id: int
    price: int | None
    prerequisites: dict
    evidence_id: str


@dataclass(frozen=True)
class Nature:
    table: ClassVar[str] = "natures"
    id: int
    slug: str
    name: str
    increased_stat: str
    decreased_stat: str
    likes_flavor: str | None
    hates_flavor: str | None
    evidence_id: str


@dataclass(frozen=True)
class Milestone:
    table: ClassVar[str] = "milestones"
    id: str
    game_id: int
    slug: str
    name: str
    ord: int
    kind: str
    location_id: int | None
    prerequisites: dict
    spoiler_level: str
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class TrainerBattle:
    table: ClassVar[str] = "trainer_battles"
    id: str
    game_id: int
    milestone_id: str | None
    name: str
    trainer_class: str
    location_id: int | None
    prize_money: int | None
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class TrainerPartyMember:
    table: ClassVar[str] = "trainer_party"
    battle_id: str
    slot: int
    form_id: int
    level: int
    gender: str | None
    ability_id: int | None
    held_item_id: int | None
    moves: list | None
    verification_status: str
    evidence_id: str


@dataclass(frozen=True)
class Coverage:
    table: ClassVar[str] = "coverage"
    game_id: int
    feature: str
    subject: str
    status: str
    note: str
    evidence_id: str


@dataclass(frozen=True)
class DataIssue:
    table: ClassVar[str] = "data_issues"
    id: str
    game_id: int | None
    feature: str
    subject: str
    kind: str
    description: str
    evidence_id: str
