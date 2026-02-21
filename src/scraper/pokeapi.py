"""
PokeAPI scraper for the rotom-dex RAG chatbot.

Collects comprehensive Pokemon data from https://pokeapi.co for the following games:
  Gen 1 remakes : FireRed, LeafGreen
  Gen 2 originals: Gold, Silver, Crystal
  Gen 2 remakes  : HeartGold, SoulSilver
  Gen 4          : Diamond, Pearl, Platinum

Data fetched per Pokemon:
  - Basic info    : types, base stats, abilities, height, weight, forms
  - Species info  : Pokedex entries per game, capture rate, egg groups, habitat …
  - Moves         : every learnable move per version-group (level-up, TM/HM, egg, tutor)
  - Encounters    : where / how to find the Pokemon per game version
  - Evolution     : full chain with trigger conditions (level, item, friendship …)
  - Held items    : wild held-item table per game version

Supplementary data scraped:
  - Full move details (power, accuracy, PP, effect, TM/HM mapping)
  - Full ability details (effect text per game)
  - Type effectiveness charts (all 18 types)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.scraper.base import BaseScraper, ScrapeConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POKEAPI_BASE = "https://pokeapi.co/api/v2"

# Version-group name  →  individual game versions it contains
VERSION_GROUP_MAP: dict[str, list[str]] = {
    "firered-leafgreen": ["fire-red", "leaf-green"],
    "gold-silver": ["gold", "silver"],
    "crystal": ["crystal"],
    "heartgold-soulsilver": ["heartgold", "soulsilver"],
    "diamond-pearl": ["diamond", "pearl"],
    "platinum": ["platinum"],
}

TARGET_VERSION_GROUPS: set[str] = set(VERSION_GROUP_MAP.keys())
TARGET_VERSIONS: set[str] = {v for vs in VERSION_GROUP_MAP.values() for v in vs}

# National Dex range covered (Gen 1–4: Bulbasaur → Arceus)
GEN1_4_RANGE = range(1, 494)


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------


class PokeAPIScraper(BaseScraper):
    """
    Fetches and caches PokeAPI data for Gen 1-4 Pokemon games.

    Inherits HTTP session management, disk caching, and rate limiting from
    :class:`~src.scraper.base.BaseScraper`.

    Parameters
    ----------
    config : ScrapeConfig
        Shared scraper configuration.  Defaults to sensible paths if omitted.
    """

    def __init__(self, config: Optional[ScrapeConfig] = None) -> None:
        if config is None:
            config = ScrapeConfig(
                cache_dir=Path("data/raw/scraper_cache/pokeapi"),
                output_dir=Path("data/raw"),
                calls_per_second=1.5,  # PokeAPI asks for ≤ 2 req/s
            )
        super().__init__(config)

    # ------------------------------------------------------------------
    # PokeAPI-specific get() — supports relative paths AND full URLs
    # ------------------------------------------------------------------

    def get(self, endpoint: str, use_cache: bool = True) -> Optional[Any]:
        """
        Fetch *endpoint* from PokeAPI with disk caching and rate limiting.

        Parameters
        ----------
        endpoint : str
            Either a relative path (``"/pokemon/1"``) or a full URL.
        use_cache : bool
            When ``True`` (default) a previously cached response is returned
            without making an HTTP request.

        Returns
        -------
        dict | list | None
            Parsed JSON response, or ``None`` on 404 / unrecoverable error.
        """
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{POKEAPI_BASE}{endpoint}"

        return self.get_json(url, use_cache=use_cache)

    # ------------------------------------------------------------------
    # Raw fetch wrappers
    # ------------------------------------------------------------------

    def fetch_pokemon(self, pokemon_id: int) -> Optional[dict]:
        return self.get(f"/pokemon/{pokemon_id}")

    def fetch_pokemon_species(self, pokemon_id: int) -> Optional[dict]:
        return self.get(f"/pokemon-species/{pokemon_id}")

    def fetch_evolution_chain(self, chain_id: int) -> Optional[dict]:
        return self.get(f"/evolution-chain/{chain_id}")

    def fetch_encounters(self, pokemon_id: int) -> list[dict]:
        """Returns the location-area encounter list (may be empty)."""
        data = self.get(f"/pokemon/{pokemon_id}/encounters")
        return data if isinstance(data, list) else []

    def fetch_move(self, move_name: str) -> Optional[dict]:
        return self.get(f"/move/{move_name}")

    def fetch_ability(self, ability_name: str) -> Optional[dict]:
        return self.get(f"/ability/{ability_name}")

    def fetch_type(self, type_name: str) -> Optional[dict]:
        return self.get(f"/type/{type_name}")

    def fetch_item(self, item_name: str) -> Optional[dict]:
        return self.get(f"/item/{item_name}")

    # ------------------------------------------------------------------
    # Parse helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _en(entries: list[dict], text_key: str = "flavor_text") -> str:
        """Return the first English string from a list of language-keyed entries."""
        for entry in entries:
            if entry.get("language", {}).get("name") == "en":
                return (
                    entry.get(text_key, "")
                    .replace("\n", " ")
                    .replace("\f", " ")
                    .strip()
                )
        return ""

    def _parse_stats(self, stats: list[dict]) -> dict[str, int]:
        return {s["stat"]["name"]: s["base_stat"] for s in stats}

    def _parse_abilities(self, abilities: list[dict]) -> list[dict]:
        return [
            {
                "name": a["ability"]["name"],
                "is_hidden": a["is_hidden"],
                "slot": a["slot"],
            }
            for a in abilities
        ]

    def _parse_moves(self, moves: list[dict]) -> dict[str, list[dict]]:
        """
        Group learnable moves by version-group, filtering to target games only.

        Returns
        -------
        dict
            ``{version_group: [{"name", "learn_method", "level"}]}``
            ``level`` is only set for level-up moves (otherwise ``None``).
        """
        result: dict[str, list[dict]] = {vg: [] for vg in TARGET_VERSION_GROUPS}

        for move_entry in moves:
            move_name: str = move_entry["move"]["name"]
            for vd in move_entry["version_group_details"]:
                vg: str = vd["version_group"]["name"]
                if vg not in TARGET_VERSION_GROUPS:
                    continue
                learn_method: str = vd["move_learn_method"]["name"]
                result[vg].append(
                    {
                        "name": move_name,
                        "learn_method": learn_method,
                        "level": vd["level_learned_at"]
                        if learn_method == "level-up"
                        else None,
                    }
                )

        # Sort level-up moves by level, keep others at the end
        for vg in result:
            result[vg].sort(
                key=lambda m: (m["learn_method"] != "level-up", m["level"] or 0)
            )

        return {vg: ms for vg, ms in result.items() if ms}

    def _parse_held_items(self, held_items: list[dict]) -> dict[str, list[dict]]:
        """Returns ``{version: [{"name", "rarity"}]}`` for target game versions."""
        result: dict[str, list[dict]] = {}
        for item_entry in held_items:
            item_name: str = item_entry["item"]["name"]
            for vd in item_entry["version_details"]:
                version: str = vd["version"]["name"]
                if version not in TARGET_VERSIONS:
                    continue
                result.setdefault(version, []).append(
                    {"name": item_name, "rarity": vd["rarity"]}
                )
        return result

    def _parse_flavor_texts(self, entries: list[dict]) -> dict[str, str]:
        """Returns ``{version: text}`` for target game versions (English only)."""
        result: dict[str, str] = {}
        for entry in entries:
            if entry.get("language", {}).get("name") != "en":
                continue
            version: str = entry.get("version", {}).get("name", "")
            if version not in TARGET_VERSIONS:
                continue
            text = (
                entry.get("flavor_text", "")
                .replace("\n", " ")
                .replace("\f", " ")
                .strip()
            )
            result[version] = text
        return result

    def _parse_encounters(self, encounter_data: list[dict]) -> dict[str, list[dict]]:
        """
        Returns
        -------
        dict
            ``{version: [{"location_area", "method", "chance",
                           "min_level", "max_level", "conditions"}]}``
        """
        result: dict[str, list[dict]] = {}
        for loc_entry in encounter_data:
            location_area: str = loc_entry["location_area"]["name"]
            for vd in loc_entry["version_details"]:
                version: str = vd["version"]["name"]
                if version not in TARGET_VERSIONS:
                    continue
                for enc in vd["encounter_details"]:
                    result.setdefault(version, []).append(
                        {
                            "location_area": location_area,
                            "method": enc["method"]["name"],
                            "chance": enc["chance"],
                            "min_level": enc["min_level"],
                            "max_level": enc["max_level"],
                            "conditions": [
                                c["name"] for c in enc.get("condition_values", [])
                            ],
                        }
                    )
        return result

    # ---- Evolution chain ----

    def _parse_evolution_chain(self, chain_root: dict) -> list[dict]:
        """
        Flatten a nested evolution chain into a list of transition steps.

        Each step::

            {
              "from": "bulbasaur",
              "to": "ivysaur",
              "trigger": "level-up",
              "conditions": {"min_level": 16}
            }
        """
        steps: list[dict] = []
        self._walk_chain(chain_root, steps, from_species=None)
        return steps

    def _walk_chain(
        self,
        node: dict,
        steps: list[dict],
        from_species: Optional[str],
    ) -> None:
        current: str = node["species"]["name"]
        if from_species is not None:
            for details in node.get("evolution_details", []):
                steps.append(
                    {
                        "from": from_species,
                        "to": current,
                        "trigger": details.get("trigger", {}).get("name"),
                        "conditions": self._extract_evo_conditions(details),
                    }
                )
        for child in node.get("evolves_to", []):
            self._walk_chain(child, steps, from_species=current)

    @staticmethod
    def _extract_evo_conditions(details: dict) -> dict[str, Any]:
        """
        Return a dict of non-null / non-False evolution conditions,
        normalising nested ``{name: …}`` objects to plain strings.
        """
        skip = {"trigger"}
        conditions: dict[str, Any] = {}
        for key, value in details.items():
            if key in skip or value is None or value is False:
                continue
            if isinstance(value, dict):
                name = value.get("name")
                if name:
                    conditions[key] = name
            elif value:
                conditions[key] = value
        return conditions

    # ------------------------------------------------------------------
    # Composite builders
    # ------------------------------------------------------------------

    def build_pokemon_data(self, pokemon_id: int) -> Optional[dict]:
        """
        Assemble a complete data record for a single Pokemon.

        Fetches the ``/pokemon/{id}``, ``/pokemon-species/{id}``,
        ``/evolution-chain/{id}``, and ``/pokemon/{id}/encounters``
        endpoints and merges them into one structured dict.
        """
        pokemon = self.fetch_pokemon(pokemon_id)
        if pokemon is None:
            return None

        species = self.fetch_pokemon_species(pokemon_id)
        if species is None:
            return None

        # Evolution chain
        evo_url: str = (species.get("evolution_chain") or {}).get("url", "")
        evo_chain_id: Optional[int] = None
        if evo_url:
            try:
                evo_chain_id = int(evo_url.rstrip("/").split("/")[-1])
            except ValueError:
                pass
        evo_raw = self.fetch_evolution_chain(evo_chain_id) if evo_chain_id else None
        evolution_steps = (
            self._parse_evolution_chain(evo_raw["chain"]) if evo_raw else []
        )

        # Encounter locations
        encounter_data = self.fetch_encounters(pokemon_id)

        # Genus (e.g. "Seed Pokémon")
        genus = self._en(species.get("genera", []), text_key="genus")

        return {
            # ---- Identity ----
            "id": pokemon["id"],
            "name": pokemon["name"],
            "national_dex": pokemon["id"],
            "forms": [f["name"] for f in pokemon.get("forms", [])],
            "generation_introduced": (species.get("generation") or {}).get("name"),
            "is_legendary": species.get("is_legendary", False),
            "is_mythical": species.get("is_mythical", False),
            "is_baby": species.get("is_baby", False),
            # ---- Physical ----
            "height_dm": pokemon.get("height"),  # decimetres  (÷10 = metres)
            "weight_hg": pokemon.get("weight"),  # hectograms  (÷10 = kg)
            "base_experience": pokemon.get("base_experience"),
            # ---- Battle ----
            "types": [t["type"]["name"] for t in pokemon.get("types", [])],
            "base_stats": self._parse_stats(pokemon.get("stats", [])),
            "abilities": self._parse_abilities(pokemon.get("abilities", [])),
            # ---- Moves per version-group ----
            "moves": self._parse_moves(pokemon.get("moves", [])),
            # ---- Wild held items per game version ----
            "held_items": self._parse_held_items(pokemon.get("held_items", [])),
            # ---- Where to find it ----
            "encounters": self._parse_encounters(encounter_data),
            # ---- Species / Pokedex ----
            "species_name": species.get("name"),
            "genus": genus,
            "flavor_texts": self._parse_flavor_texts(
                species.get("flavor_text_entries", [])
            ),
            "capture_rate": species.get("capture_rate"),
            "base_happiness": species.get("base_happiness"),
            "growth_rate": (species.get("growth_rate") or {}).get("name"),
            "egg_groups": [eg["name"] for eg in species.get("egg_groups", [])],
            "habitat": (species.get("habitat") or {}).get("name"),
            "color": (species.get("color") or {}).get("name"),
            "shape": (species.get("shape") or {}).get("name"),
            "evolves_from": (species.get("evolves_from_species") or {}).get("name"),
            # ---- Evolution ----
            "evolution_chain": evolution_steps,
        }

    def build_move_data(self, move_name: str) -> Optional[dict]:
        """
        Fetch and parse full details for a single move.

        Includes TM/HM mapping per version-group (requires extra requests
        to the ``/machine/{id}`` endpoint — these are also cached).
        """
        data = self.fetch_move(move_name)
        if data is None:
            return None

        effect_entries = data.get("effect_entries", [])
        effect = self._en(effect_entries, text_key="effect")
        short_effect = self._en(effect_entries, text_key="short_effect")

        # Flavour text per version-group (target groups only, English)
        flavor_texts: dict[str, str] = {}
        for entry in data.get("flavor_text_entries", []):
            if entry.get("language", {}).get("name") != "en":
                continue
            vg = entry.get("version_group", {}).get("name", "")
            if vg in TARGET_VERSION_GROUPS:
                flavor_texts[vg] = (
                    entry.get("flavor_text", "").replace("\n", " ").strip()
                )

        # TM / HM name per version-group
        machines: dict[str, str] = {}
        for m in data.get("machines", []):
            vg = m.get("version_group", {}).get("name", "")
            if vg not in TARGET_VERSION_GROUPS:
                continue
            machine_url = m["machine"]["url"]
            machine_data = self.get(machine_url)
            if machine_data:
                machines[vg] = machine_data["item"]["name"]

        return {
            "id": data["id"],
            "name": data["name"],
            "type": (data.get("type") or {}).get("name"),
            "damage_class": (data.get("damage_class") or {}).get("name"),
            "power": data.get("power"),
            "accuracy": data.get("accuracy"),
            "pp": data.get("pp"),
            "priority": data.get("priority"),
            "target": (data.get("target") or {}).get("name"),
            "effect": effect,
            "short_effect": short_effect,
            "effect_chance": data.get("effect_chance"),
            "flavor_texts": flavor_texts,
            "machines": machines,
        }

    def build_ability_data(self, ability_name: str) -> Optional[dict]:
        """Fetch and parse full details for a single ability."""
        data = self.fetch_ability(ability_name)
        if data is None:
            return None

        effect_entries = data.get("effect_entries", [])
        effect = self._en(effect_entries, text_key="effect")
        short_effect = self._en(effect_entries, text_key="short_effect")

        flavor_texts: dict[str, str] = {}
        for entry in data.get("flavor_text_entries", []):
            if entry.get("language", {}).get("name") != "en":
                continue
            vg = entry.get("version_group", {}).get("name", "")
            if vg in TARGET_VERSION_GROUPS:
                flavor_texts[vg] = (
                    entry.get("flavor_text", "").replace("\n", " ").strip()
                )

        return {
            "id": data["id"],
            "name": data["name"],
            "is_main_series": data.get("is_main_series"),
            "generation": (data.get("generation") or {}).get("name"),
            "effect": effect,
            "short_effect": short_effect,
            "flavor_texts": flavor_texts,
        }

    def build_type_data(self, type_name: str) -> Optional[dict]:
        """Fetch and parse type effectiveness (damage relations) for one type."""
        data = self.fetch_type(type_name)
        if data is None:
            return None

        rels = data.get("damage_relations", {})
        return {
            "name": type_name,
            "double_damage_from": [
                t["name"] for t in rels.get("double_damage_from", [])
            ],
            "double_damage_to": [t["name"] for t in rels.get("double_damage_to", [])],
            "half_damage_from": [t["name"] for t in rels.get("half_damage_from", [])],
            "half_damage_to": [t["name"] for t in rels.get("half_damage_to", [])],
            "no_damage_from": [t["name"] for t in rels.get("no_damage_from", [])],
            "no_damage_to": [t["name"] for t in rels.get("no_damage_to", [])],
        }

    # ------------------------------------------------------------------
    # Bulk scraping
    # ------------------------------------------------------------------

    def scrape_all_pokemon(
        self,
        dex_range: range = GEN1_4_RANGE,
        save_dir: Optional[str | Path] = None,
    ) -> dict[int, dict]:
        """
        Scrape all Pokemon in *dex_range* and save each to a JSON file.

        Already-saved files are loaded from disk (skipping HTTP requests).

        Returns
        -------
        dict
            ``{national_dex_number: pokemon_data_dict}``
        """
        out_dir = Path(save_dir) if save_dir else self.config.output_dir / "pokemon"
        out_dir.mkdir(parents=True, exist_ok=True)

        all_pokemon: dict[int, dict] = {}

        for dex_num in dex_range:
            out_file = out_dir / f"{dex_num:04d}.json"

            if out_file.exists():
                self.logger.debug(f"#{dex_num:03d} already on disk — loading.")
                cached = self.load_json(out_file)
                if cached:
                    all_pokemon[dex_num] = cached
                continue

            self.logger.info(f"Scraping Pokemon #{dex_num:03d} …")
            data = self.build_pokemon_data(dex_num)

            if data:
                self.save_json(data, out_file)
                all_pokemon[dex_num] = data
                self.logger.info(f"  ✓ {data['name']} saved.")
            else:
                self.logger.warning(f"  Could not fetch Pokemon #{dex_num:03d}.")

        return all_pokemon

    def scrape_all_moves(
        self,
        pokemon_data: Optional[dict[int, dict]] = None,
        save_dir: Optional[str | Path] = None,
    ) -> dict[str, dict]:
        """
        Scrape move details for every move referenced in *pokemon_data*.

        If *pokemon_data* is omitted the full move list is fetched from
        the ``/move`` paginated endpoint instead.
        """
        out_dir = Path(save_dir) if save_dir else self.config.output_dir / "moves"
        out_dir.mkdir(parents=True, exist_ok=True)

        move_names: set[str] = set()
        if pokemon_data:
            for pkmn in pokemon_data.values():
                for vg_moves in pkmn.get("moves", {}).values():
                    for m in vg_moves:
                        move_names.add(m["name"])
        else:
            self.logger.info("Fetching full move list from API …")
            page = self.get("/move?limit=1000")
            if page:
                move_names = {m["name"] for m in page.get("results", [])}

        all_moves: dict[str, dict] = {}
        for move_name in sorted(move_names):
            out_file = out_dir / f"{move_name}.json"
            if out_file.exists():
                cached = self.load_json(out_file)
                if cached:
                    all_moves[move_name] = cached
                continue

            self.logger.info(f"  Fetching move: {move_name}")
            data = self.build_move_data(move_name)
            if data:
                self.save_json(data, out_file)
                all_moves[move_name] = data

        return all_moves

    def scrape_all_abilities(
        self,
        pokemon_data: Optional[dict[int, dict]] = None,
        save_dir: Optional[str | Path] = None,
    ) -> dict[str, dict]:
        """Scrape ability details for every ability referenced in *pokemon_data*."""
        out_dir = Path(save_dir) if save_dir else self.config.output_dir / "abilities"
        out_dir.mkdir(parents=True, exist_ok=True)

        ability_names: set[str] = set()
        if pokemon_data:
            for pkmn in pokemon_data.values():
                for ability in pkmn.get("abilities", []):
                    ability_names.add(ability["name"])
        else:
            self.logger.info("Fetching full ability list from API …")
            page = self.get("/ability?limit=400")
            if page:
                ability_names = {a["name"] for a in page.get("results", [])}

        all_abilities: dict[str, dict] = {}
        for ability_name in sorted(ability_names):
            out_file = out_dir / f"{ability_name}.json"
            if out_file.exists():
                cached = self.load_json(out_file)
                if cached:
                    all_abilities[ability_name] = cached
                continue

            self.logger.info(f"  Fetching ability: {ability_name}")
            data = self.build_ability_data(ability_name)
            if data:
                self.save_json(data, out_file)
                all_abilities[ability_name] = data

        return all_abilities

    def scrape_all_types(
        self,
        save_dir: Optional[str | Path] = None,
    ) -> dict[str, dict]:
        """Scrape type-effectiveness charts for all 18 standard types."""
        out_dir = Path(save_dir) if save_dir else self.config.output_dir / "types"
        out_dir.mkdir(parents=True, exist_ok=True)

        type_list_data = self.get("/type?limit=30")
        if not type_list_data:
            return {}

        # "unknown" and "shadow" are non-standard — exclude them
        type_names = [
            t["name"]
            for t in type_list_data.get("results", [])
            if t["name"] not in ("unknown", "shadow")
        ]

        all_types: dict[str, dict] = {}
        for type_name in type_names:
            out_file = out_dir / f"{type_name}.json"
            if out_file.exists():
                cached = self.load_json(out_file)
                if cached:
                    all_types[type_name] = cached
                continue

            self.logger.info(f"  Fetching type: {type_name}")
            data = self.build_type_data(type_name)
            if data:
                self.save_json(data, out_file)
                all_types[type_name] = data

        return all_types

    # ------------------------------------------------------------------
    # Full pipeline (implements BaseScraper.scrape_all)
    # ------------------------------------------------------------------

    def scrape_all(
        self,
        dex_range: range = GEN1_4_RANGE,
    ) -> dict[str, Any]:
        """
        Run the complete scraping pipeline in order:

        1. Pokemon data (Gen 1–4, national dex 1–493)
        2. Move details  (all moves learnable in target games)
        3. Ability details
        4. Type effectiveness charts
        """
        self.logger.info("=" * 60)
        self.logger.info("rotom-dex PokeAPI scraper — starting full run")
        self.logger.info("=" * 60)

        self.logger.info("[1/4] Scraping Pokemon …")
        pokemon_data = self.scrape_all_pokemon(dex_range=dex_range)

        self.logger.info("[2/4] Scraping moves …")
        moves_data = self.scrape_all_moves(pokemon_data=pokemon_data)

        self.logger.info("[3/4] Scraping abilities …")
        abilities_data = self.scrape_all_abilities(pokemon_data=pokemon_data)

        self.logger.info("[4/4] Scraping type effectiveness …")
        types_data = self.scrape_all_types()

        self.logger.info("=" * 60)
        self.logger.info(
            f"Done — {len(pokemon_data)} Pokemon | "
            f"{len(moves_data)} moves | "
            f"{len(abilities_data)} abilities | "
            f"{len(types_data)} types"
        )
        self.logger.info("=" * 60)

        return {
            "pokemon": pokemon_data,
            "moves": moves_data,
            "abilities": abilities_data,
            "types": types_data,
        }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Scrape PokeAPI data for the rotom-dex chatbot."
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Root output directory (default: data/raw)",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/raw/scraper_cache/pokeapi",
        help="HTTP response cache directory (default: data/raw/scraper_cache/pokeapi)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="First national dex number to scrape (default: 1)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=493,
        help="Last national dex number to scrape inclusive (default: 493)",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=1.5,
        help="API requests per second — stay ≤ 2 to be polite (default: 1.5)",
    )
    parser.add_argument(
        "--only",
        choices=["pokemon", "moves", "abilities", "types"],
        default=None,
        help="Scrape only one category instead of running the full pipeline.",
    )
    args = parser.parse_args()

    config = ScrapeConfig(
        cache_dir=Path(args.cache_dir),
        output_dir=Path(args.output_dir),
        calls_per_second=args.rps,
    )
    scraper = PokeAPIScraper(config=config)
    dex_range = range(args.start, args.end + 1)

    if args.only == "pokemon":
        scraper.scrape_all_pokemon(dex_range=dex_range)
    elif args.only == "moves":
        scraper.scrape_all_moves()
    elif args.only == "abilities":
        scraper.scrape_all_abilities()
    elif args.only == "types":
        scraper.scrape_all_types()
    else:
        scraper.scrape_all(dex_range=dex_range)
