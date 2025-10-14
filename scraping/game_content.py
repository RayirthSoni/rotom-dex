"""Utilities for scraping generation-specific game content.

The module exposes high level helpers that try to gather structured
information about move tutors, TM/HM machines, encounter locations,
trainer rosters and general item data. The helpers attempt to use the
official [PokeAPI](https://pokeapi.co) REST interface when network
connectivity is available. When the network is unreachable (e.g. during
offline development or CI runs) the functions automatically fall back to
light-weight sample datasets that live inside the repository under
``scraping/data_samples``.

Each scraper returns a list of dictionaries with a harmonised schema so
that the downstream data pipeline can reason about the different data
sources in a uniform fashion.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

from configs.constants import Constants


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Generation:
    """Simple data holder describing a Pokémon generation."""

    slug: str
    label: str
    regions: List[str]
    version_groups: List[str]


def _load_generations() -> Dict[str, Generation]:
    """Create ``Generation`` objects from ``Constants.GENERATION_CONFIG``."""

    generations: Dict[str, Generation] = {}
    for slug, payload in Constants.GENERATION_CONFIG.items():
        generations[slug] = Generation(
            slug=slug,
            label=payload["label"],
            regions=list(payload.get("regions", [])),
            version_groups=list(payload.get("version_groups", [])),
        )
    return generations


GENERATIONS = _load_generations()


def _sample_file(dataset_name: str) -> Path:
    """Return the path to a bundled sample dataset."""

    return Path(__file__).with_name("data_samples") / f"{dataset_name}.json"


def _load_sample(dataset_name: str) -> List[Dict]:
    """Load a bundled sample dataset used as offline fallback."""

    sample_path = _sample_file(dataset_name)
    if not sample_path.exists():
        LOGGER.warning("Sample dataset %s is missing", dataset_name)
        return []
    with sample_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _ensure_requests_session() -> requests.Session:
    """Create a requests session with sane defaults."""

    session = requests.Session()
    session.headers.update({"User-Agent": "PokemonGamesChatbot/1.0"})
    return session


@lru_cache(maxsize=4)
def _csv_client() -> "CsvClient":
    return CsvClient(Constants.POKEAPI_CSV_BASE_URL)


class CsvClient:
    """Utility used to lazily download CSV files from the PokeAPI dataset."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = _ensure_requests_session()
        self._cache: Dict[str, List[Dict[str, str]]] = {}

    def fetch(self, name: str) -> List[Dict[str, str]]:
        """Fetch and cache a CSV as a list of dictionaries."""

        if name in self._cache:
            return self._cache[name]
        url = f"{self.base_url}/{name}.csv"
        LOGGER.debug("Fetching %s", url)
        response = self._session.get(url, timeout=30)
        response.raise_for_status()
        with StringIO(response.text) as buffer:
            reader = csv.DictReader(buffer)
            self._cache[name] = list(reader)
        return self._cache[name]


def _generation_slug(version_group: str) -> Optional[str]:
    for slug, generation in GENERATIONS.items():
        if version_group in generation.version_groups:
            return slug
    return None


def _enrich_with_generation(records: Iterable[Dict], version_key: str) -> List[Dict]:
    enriched: List[Dict] = []
    for entry in records:
        version_group = entry.get(version_key)
        slug = _generation_slug(version_group) if version_group else None
        if slug:
            entry.setdefault("generation", slug)
            entry.setdefault("generation_label", GENERATIONS[slug].label)
        enriched.append(entry)
    return enriched


def _safe_request(url: str, session: Optional[requests.Session] = None) -> Optional[Dict]:
    session = session or _ensure_requests_session()
    try:
        LOGGER.debug("Requesting %s", url)
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network failure path
        LOGGER.warning("Falling back to bundled sample for %s (%s)", url, exc)
        return None
    return response.json()


def get_move_tutor_data(limit_pokemon: Optional[int] = None) -> List[Dict]:
    """Return move tutor availability grouped by generation.

    When the network is unavailable the function will return the sample
    payload stored in ``scraping/data_samples/move_tutors.json``.
    """

    session = _ensure_requests_session()
    base_url = Constants.POKEAPI_BASE_URL
    generation_url = f"{base_url}/generation"
    generation_payload = _safe_request(generation_url, session=session)
    if not generation_payload:  # offline fallback
        return _load_sample("move_tutors")

    results: List[Dict] = []
    generations = generation_payload.get("results", [])
    for idx, generation in enumerate(generations, start=1):
        slug = generation["name"]
        if slug not in GENERATIONS:
            continue
        species_payload = _safe_request(generation["url"], session=session)
        if not species_payload:
            continue
        species_entries = species_payload.get("pokemon_species", [])
        if limit_pokemon:
            species_entries = species_entries[:limit_pokemon]
        for species in species_entries:
            pokemon_name = species["name"]
            pokemon_payload = _safe_request(
                f"{base_url}/pokemon/{pokemon_name}", session=session
            )
            if not pokemon_payload:
                continue
            for move in pokemon_payload.get("moves", []):
                move_name = move["move"]["name"]
                for detail in move.get("version_group_details", []):
                    learn_method = detail.get("move_learn_method", {}).get("name")
                    version_group = detail.get("version_group", {}).get("name")
                    if learn_method != "tutor":
                        continue
                    record = {
                        "generation": slug,
                        "generation_label": GENERATIONS[slug].label,
                        "regions": GENERATIONS[slug].regions,
                        "pokemon": pokemon_name,
                        "move": move_name,
                        "version_group": version_group,
                        "source": "tutor",
                    }
                    results.append(record)
    if not results:
        return _load_sample("move_tutors")
    return results


def get_tm_hm_data() -> List[Dict]:
    """Return TM/HM machine data grouped by generation."""

    client = _csv_client()
    try:
        machines = client.fetch("machine")
        items = {row["id"]: row for row in client.fetch("item")}
        moves = {row["id"]: row for row in client.fetch("move")}
        move_types = {row["id"]: row for row in client.fetch("type")}
        damage_classes = {
            row["id"]: row for row in client.fetch("move_damage_class")
        }
        version_groups = {
            row["id"]: row for row in client.fetch("version_group")
        }
        regions = {row["id"]: row for row in client.fetch("region")}
    except requests.RequestException:  # pragma: no cover - network failure path
        return _load_sample("machines")

    dataset: List[Dict] = []
    for machine in machines:
        version_group_id = machine.get("version_group_id")
        version_group_entry = version_groups.get(version_group_id, {})
        version_group = version_group_entry.get("identifier")
        move_id = machine.get("move_id")
        item_id = machine.get("item_id")
        move = moves.get(move_id, {})
        item = items.get(item_id, {})
        type_entry = move_types.get(move.get("type_id"), {})
        damage_class_entry = damage_classes.get(move.get("damage_class_id"), {})
        region_name = regions.get(version_group_entry.get("region_id"), {}).get(
            "identifier"
        )
        entry = {
            "machine_id": machine.get("id"),
            "version_group_id": version_group_id,
            "item_id": item_id,
            "move_id": move_id,
            "machine_number": item.get("identifier"),
            "move": move.get("identifier"),
            "move_type": type_entry.get("identifier"),
            "move_damage_class": damage_class_entry.get("identifier"),
            "region": region_name,
            "version_group": version_group,
        }
        dataset.append(entry)

    dataset = _enrich_with_generation(dataset, "version_group")
    if not dataset:
        return _load_sample("machines")
    return dataset


def get_encounter_data(limit_locations: Optional[int] = None) -> List[Dict]:
    """Return encounter locations for Pokémon per generation."""

    session = _ensure_requests_session()
    base_url = Constants.POKEAPI_BASE_URL
    encounter_url = f"{base_url}/encounter-method"
    payload = _safe_request(encounter_url, session=session)
    if not payload:
        return _load_sample("encounters")

    results: List[Dict] = []
    methods = payload.get("results", [])
    for method in methods:
        method_payload = _safe_request(method["url"], session=session)
        if not method_payload:
            continue
        for location in method_payload.get("locations", [])[: limit_locations or None]:
            location_payload = _safe_request(location["url"], session=session)
            if not location_payload:
                continue
            region = location_payload.get("region", {}).get("name")
            for area in location_payload.get("areas", []):
                area_payload = _safe_request(area["url"], session=session)
                if not area_payload:
                    continue
                encounters = area_payload.get("pokemon_encounters", [])
                for encounter in encounters:
                    pokemon = encounter.get("pokemon", {}).get("name")
                    for detail in encounter.get("version_details", []):
                        version_group = detail.get("version", {}).get("name")
                        for encounter_detail in detail.get("encounter_details", []):
                            record = {
                                "region": region,
                                "location": location.get("name"),
                                "location_area": area_payload.get("name"),
                                "pokemon": pokemon,
                                "version_group": version_group,
                                "method": method_payload.get("name"),
                                "chance": encounter_detail.get("chance"),
                                "min_level": encounter_detail.get("min_level"),
                                "max_level": encounter_detail.get("max_level"),
                            }
                            results.append(record)
    results = _enrich_with_generation(results, "version_group")
    if not results:
        return _load_sample("encounters")
    return results


def get_trainer_rosters() -> List[Dict]:
    """Return trainer rosters using the published PokeAPI CSV dump."""

    client = _csv_client()
    try:
        trainers = client.fetch("trainer")
        trainer_classes = {row["id"]: row for row in client.fetch("trainer_class")}
        trainer_pokemon = client.fetch("trainer_pokemon")
        pokemon = {row["id"]: row for row in client.fetch("pokemon")}
        moves = {row["id"]: row for row in client.fetch("move")}
        version_groups = {
            row["id"]: row for row in client.fetch("version_group")
        }
        locations = {row["id"]: row for row in client.fetch("location")}
        regions = {row["id"]: row for row in client.fetch("region")}
    except requests.RequestException:  # pragma: no cover - network failure path
        return _load_sample("trainers")

    pokemon_by_trainer: Dict[str, List[Dict[str, str]]] = {}
    for entry in trainer_pokemon:
        trainer_id = entry.get("trainer_id")
        pokemon_id = entry.get("pokemon_id")
        move_1 = moves.get(entry.get("move_1_id"), {}).get("identifier")
        move_2 = moves.get(entry.get("move_2_id"), {}).get("identifier")
        move_3 = moves.get(entry.get("move_3_id"), {}).get("identifier")
        move_4 = moves.get(entry.get("move_4_id"), {}).get("identifier")
        pokemon_entry = pokemon.get(pokemon_id, {})
        pokemon_by_trainer.setdefault(trainer_id, []).append(
            {
                "pokemon": pokemon_entry.get("identifier"),
                "level": entry.get("level"),
                "moves": [m for m in [move_1, move_2, move_3, move_4] if m],
            }
        )

    dataset: List[Dict] = []
    for trainer in trainers:
        trainer_id = trainer.get("id")
        version_group_id = trainer.get("version_group_id")
        version_group_entry = version_groups.get(version_group_id, {})
        version_group = version_group_entry.get("identifier")
        trainer_class = trainer_classes.get(trainer.get("trainer_class_id"), {})
        location_entry = locations.get(trainer.get("location_id"), {})
        region_name = regions.get(version_group_entry.get("region_id"), {}).get(
            "identifier"
        )
        entry = {
            "trainer_id": trainer_id,
            "trainer_name": trainer.get("name"),
            "trainer_class": trainer_class.get("name") or trainer.get("trainer_class_id"),
            "location": location_entry.get("identifier") or trainer.get("location_id"),
            "version_group": version_group,
            "version_group_id": version_group_id,
            "reward": trainer.get("base_payout"),
            "team": pokemon_by_trainer.get(trainer_id, []),
            "region": region_name,
        }
        dataset.append(entry)

    dataset = _enrich_with_generation(dataset, "version_group")
    if not dataset:
        return _load_sample("trainers")
    return dataset


def get_item_data() -> List[Dict]:
    """Return general item data across games."""

    client = _csv_client()
    try:
        items = client.fetch("item")
        item_names = client.fetch("item_names")
        item_effect_text = client.fetch("item_effect_text")
        item_categories = {row["id"]: row for row in client.fetch("item_category")}
        item_game_indices = client.fetch("item_game_index")
        regions = {row["id"]: row for row in client.fetch("region")}
        version_groups = {row["id"]: row for row in client.fetch("version_group")}
    except requests.RequestException:  # pragma: no cover - network failure path
        return _load_sample("items")

    name_by_item: Dict[str, str] = {}
    for entry in item_names:
        if entry.get("language_id") == "9":  # english
            name_by_item[entry["item_id"]] = entry.get("name")

    effect_by_item: Dict[str, str] = {}
    for entry in item_effect_text:
        if entry.get("language_id") == "9":
            effect_by_item[entry["item_id"]] = entry.get("short_effect")

    indices_by_item: Dict[str, List[Dict[str, str]]] = {}
    for entry in item_game_indices:
        indices_by_item.setdefault(entry.get("item_id"), []).append(entry)

    dataset: List[Dict] = []
    for item in items:
        item_id = item.get("id")
        category = item_categories.get(item.get("item_category_id"), {})
        base_entry = {
            "item_id": item_id,
            "item": name_by_item.get(item_id, item.get("identifier")),
            "category": category.get("identifier"),
            "cost": item.get("cost"),
            "fling_power": item.get("fling_power"),
            "effect": effect_by_item.get(item_id),
        }
        for index in indices_by_item.get(item_id, []) or [{}]:
            version_group_id = index.get("version_group_id")
            version_group_entry = version_groups.get(version_group_id, {})
            version_group = version_group_entry.get("identifier")
            region_id = version_group_entry.get("region_id")
            region_name = regions.get(region_id, {}).get("identifier") if region_id else None
            entry = {
                **base_entry,
                "version_group": version_group,
                "version_group_id": version_group_id,
                "region": region_name,
                "game_index": index.get("game_index"),
            }
            dataset.append(entry)

    dataset = _enrich_with_generation(dataset, "version_group")
    if not dataset:
        return _load_sample("items")
    return dataset


__all__ = [
    "Generation",
    "GENERATIONS",
    "get_move_tutor_data",
    "get_tm_hm_data",
    "get_encounter_data",
    "get_trainer_rosters",
    "get_item_data",
]

