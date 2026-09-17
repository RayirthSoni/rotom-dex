"""Shared import state handed to every importer."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property

from rotom_dex.ingestion.cache import PokeAPICache
from rotom_dex.ingestion.registry import GameEntry, Registry
from rotom_dex.ingestion.writer import Writer

MAX_TYPE_ID = 18  # normal..fairy; 'stellar', 'unknown' and 'shadow' are not battle types here.
STAT_SLUGS = {
    1: "hp",
    2: "attack",
    3: "defense",
    4: "special-attack",
    5: "special-defense",
    6: "speed",
    9: "special",
}


@dataclass
class VersionGroupInfo:
    id: int
    slug: str
    generation_id: int
    order: int
    games: list[GameEntry] = field(default_factory=list)
    region_ids: set[int] = field(default_factory=set)
    # Version group whose learnsets/machines/move data are used when this one has none
    # (PokéAPI stores expansion content under the base game's group).
    data_source_id: int | None = None

    @property
    def source_id(self) -> int:
        return self.data_source_id or self.id


class Context:
    def __init__(
        self,
        cache: PokeAPICache,
        registry: Registry,
        games: list[GameEntry],
        mechanics,
        packs: dict,
        writer: Writer,
        snapshot_id: str,
        ability_effects=None,
    ):
        self.cache = cache
        self.registry = registry
        self.games = games
        self.mechanics = mechanics
        self.ability_effects = ability_effects
        self.packs = packs
        self.w = writer
        self.snapshot_id = snapshot_id
        groups = cache.index("version_groups")
        regions = defaultdict(set)
        for r in cache.rows("version_group_regions"):
            regions[int(r["version_group_id"])].add(int(r["region_id"]))
        self.version_groups: dict[int, VersionGroupInfo] = {}
        for game in games:
            info = self.version_groups.get(game.version_group_id)
            if info is None:
                g = groups[game.version_group_id]
                info = VersionGroupInfo(
                    int(g["id"]),
                    g["identifier"],
                    int(g["generation_id"]),
                    int(g["order"]),
                    region_ids=regions[int(g["id"])],
                )
                self.version_groups[info.id] = info
            info.games.append(game)
        inherit = registry.inherits
        slugs = {g["identifier"]: int(g["id"]) for g in groups.values()}
        for info in self.version_groups.values():
            if info.slug in inherit:
                info.data_source_id = slugs[inherit[info.slug]]
        self.generations: set[int] = {v.generation_id for v in self.version_groups.values()}
        self.group_order: dict[int, int] = {int(g["id"]): int(g["order"]) for g in groups.values()}
        self.group_generation: dict[int, int] = {int(g["id"]): int(g["generation_id"]) for g in groups.values()}
        self.all_groups = groups
        self.game_ids: set[int] = {g.id for g in games}

    # -- evidence helpers -------------------------------------------------------
    def ev(self, *refs: tuple[str, str]) -> str:
        return self.w.evidence(*refs)

    @property
    def registry_ref(self) -> tuple[str, str]:
        return ("registry", "data/games/registry.json; support policy")

    @property
    def normalizer_ref(self) -> tuple[str, str]:
        return ("normalizer", "rotom_dex.ingestion; documented normalization rules")

    # -- cached lookups ----------------------------------------------------------
    @cached_property
    def species(self) -> dict[int, dict]:
        return self.cache.index("pokemon_species")

    @cached_property
    def pokemon(self) -> dict[int, dict]:
        return self.cache.index("pokemon")

    @cached_property
    def default_form_of_species(self) -> dict[int, int]:
        return {int(r["species_id"]): int(r["id"]) for r in self.cache.rows("pokemon") if r["is_default"] == "1"}

    @cached_property
    def form_variants(self) -> dict[int, dict]:
        return self.cache.index("pokemon_forms")

    @cached_property
    def form_intro_generation(self) -> dict[int, int]:
        """Earliest generation in which a form (pokemon.csv row) has any variant."""
        intro: dict[int, int] = {}
        for r in self.cache.rows("pokemon_forms"):
            pid = int(r["pokemon_id"])
            vg = r["introduced_in_version_group_id"]
            gen = self.group_generation[int(vg)] if vg else int(self.species[int(self.pokemon[pid]["species_id"])]["generation_id"])
            intro[pid] = min(intro.get(pid, 99), gen)
        for pid, p in self.pokemon.items():
            intro.setdefault(pid, int(self.species[int(p["species_id"])]["generation_id"]))
        return intro

    @cached_property
    def types(self) -> dict[int, dict]:
        return {i: r for i, r in self.cache.index("types").items() if i <= MAX_TYPE_ID}

    @cached_property
    def type_slugs(self) -> dict[int, str]:
        return {i: r["identifier"] for i, r in self.types.items()}

    @cached_property
    def moves(self) -> dict[int, dict]:
        return self.cache.index("moves")

    @cached_property
    def items(self) -> dict[int, dict]:
        return self.cache.index("items")

    @cached_property
    def item_generations(self) -> dict[int, set[int]]:
        out = defaultdict(set)
        for r in self.cache.rows("item_game_indices"):
            out[int(r["item_id"])].add(int(r["generation_id"]))
        return out

    @cached_property
    def abilities(self) -> dict[int, dict]:
        return self.cache.index("abilities")

    @cached_property
    def locations(self) -> dict[int, dict]:
        return self.cache.index("locations")

    @cached_property
    def location_areas(self) -> dict[int, dict]:
        return self.cache.index("location_areas")

    @cached_property
    def slug_to_location(self) -> dict[str, int]:
        return {r["identifier"]: i for i, r in self.locations.items()}

    @cached_property
    def slug_to_pokemon(self) -> dict[str, int]:
        return {r["identifier"]: i for i, r in self.pokemon.items()}

    @cached_property
    def slug_to_item(self) -> dict[str, int]:
        return {r["identifier"]: i for i, r in self.items.items()}

    @cached_property
    def slug_to_move(self) -> dict[str, int]:
        return {r["identifier"]: i for i, r in self.moves.items()}

    @cached_property
    def slug_to_ability(self) -> dict[str, int]:
        return {r["identifier"]: i for i, r in self.abilities.items()}

    @cached_property
    def slug_to_type(self) -> dict[str, int]:
        return {s: i for i, s in self.type_slugs.items()}

    def english(self, table: str, key: str, field_name: str = "name") -> dict[int, str]:
        return self.cache.english(table, key, field_name)

    def mechanic(self, version_group_id: int, key: str) -> int | None:
        return self.mechanics.value(self.version_groups[version_group_id].slug, key)
