"""
PokemonDB.net scraper for rotom-dex.

Fills the gaps that PokeAPI does not cover well:

  - Which Pokemon are actually obtainable in each specific game
    (regional Pokedex availability per version)
  - Gym leader teams  (name, badge, specialty type, Pokemon with levels)
  - Elite Four + Champion teams per game
  - In-game item locations (Pokemart shops, item balls, hidden items)

Data is saved under::

    data/raw/games/{game_slug}/
        pokedex.json       # obtainable Pokemon for this game
        gym_leaders.json   # ordered list of gym leaders + their teams
        elite4.json        # Elite Four + Champion teams
        items.json         # notable item locations

Source: https://pokemondb.net
  Game dex   → /pokedex/game/{slug}
  Gym leaders→ /gym/{region}
  Elite Four → /elite-four/{region}

NOTE: pokemondb.net is an HTML site — its CSS selectors may change over
time.  All parsing functions log a WARNING when they cannot find expected
elements rather than crashing, so a scrape with partial failures still
saves what it could retrieve.  Re-run after adjusting selectors to fill
any gaps.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from src.scraper.base import BaseScraper, ScrapeConfig

logger = logging.getLogger(__name__)

POKEMONDB_BASE = "https://pokemondb.net"

# ---------------------------------------------------------------------------
# Game / region constants
# ---------------------------------------------------------------------------

# Maps our internal game slug → pokemondb URL slug for the game dex page
GAME_DEX_SLUGS: dict[str, str] = {
    "fire-red": "fire-red-leaf-green",
    "leaf-green": "fire-red-leaf-green",
    "gold": "gold-silver",
    "silver": "gold-silver",
    "crystal": "crystal",
    "heartgold": "heartgold-soulsilver",
    "soulsilver": "heartgold-soulsilver",
    "diamond": "diamond-pearl",
    "pearl": "diamond-pearl",
    "platinum": "platinum",
}

# Maps version-group slug → region name used in gym / elite-four URLs
VERSION_GROUP_TO_REGION: dict[str, str] = {
    "fire-red-leaf-green": "kanto",
    "gold-silver": "johto",
    "crystal": "johto",
    "heartgold-soulsilver": "johto",
    "diamond-pearl": "sinnoh",
    "platinum": "sinnoh",
}

# All version-group slugs we care about (de-duplicated)
ALL_VERSION_GROUPS: list[str] = list(dict.fromkeys(GAME_DEX_SLUGS.values()))

# Human-readable game names for logging / output
GAME_DISPLAY_NAMES: dict[str, str] = {
    "fire-red-leaf-green": "FireRed / LeafGreen",
    "gold-silver": "Gold / Silver",
    "crystal": "Crystal",
    "heartgold-soulsilver": "HeartGold / SoulSilver",
    "diamond-pearl": "Diamond / Pearl",
    "platinum": "Platinum",
}

# ---------------------------------------------------------------------------
# Data dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GameDexEntry:
    """A single Pokemon's entry in a game's obtainable Pokedex."""

    national_dex: int
    name: str
    types: list[str]
    # URL path on pokemondb, e.g. "/pokedex/bulbasaur"
    url_path: str = ""


@dataclass
class TrainerPokemon:
    """A Pokemon used by an in-game trainer (gym leader, Elite Four, etc.)."""

    name: str
    level: int
    types: list[str] = field(default_factory=list)
    held_item: Optional[str] = None
    ability: Optional[str] = None
    # Known moves for this trainer's Pokemon (scraped when available)
    moves: list[str] = field(default_factory=list)


@dataclass
class TrainerData:
    """
    A named in-game trainer — covers gym leaders, Elite Four, and the Champion.

    ``role`` is one of: ``"gym_leader"``, ``"elite_four"``, ``"champion"``.
    """

    name: str
    role: str  # "gym_leader" | "elite_four" | "champion"
    specialty_type: str
    game_version_group: str
    # Gym leaders only
    gym_number: Optional[int] = None
    badge: Optional[str] = None
    tm_reward: Optional[str] = None
    # Elite Four only
    order: Optional[int] = None  # 1-4 for Elite Four members
    # Team
    pokemon: list[TrainerPokemon] = field(default_factory=list)
    # Location in the game (e.g. "Pewter City Gym")
    location: str = ""


@dataclass
class ItemLocation:
    """A notable item and where to find it in a specific game."""

    name: str
    location: str
    method: str  # "shop", "item_ball", "hidden", "gift", "prize"
    price: Optional[int] = None  # for shop items
    notes: str = ""


# ---------------------------------------------------------------------------
# Helper: pretty-print a dataclass as a plain dict (for JSON serialisation)
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses and lists to JSON-serialisable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------


class PokemonDBScraper(BaseScraper):
    """
    Scrapes pokemondb.net for game-specific data that PokeAPI does not expose.

    Parameters
    ----------
    config : ScrapeConfig
        Shared configuration (cache dir, output dir, rate limit, …).
        Use ``ScrapeConfig(cache_dir="data/raw/scraper_cache/pokemondb")``
        to keep pokemondb HTML separate from the PokeAPI JSON cache.
    """

    def __init__(self, config: Optional[ScrapeConfig] = None) -> None:
        if config is None:
            config = ScrapeConfig(
                cache_dir=Path("data/raw/scraper_cache/pokemondb"),
                output_dir=Path("data/raw/games"),
                calls_per_second=0.8,  # be extra polite to an HTML site
            )
        super().__init__(config)

    # ------------------------------------------------------------------
    # Internal URL builders
    # ------------------------------------------------------------------

    def _game_dex_url(self, version_group_slug: str) -> str:
        return f"{POKEMONDB_BASE}/pokedex/game/{version_group_slug}"

    def _gym_url(self, region: str) -> str:
        return f"{POKEMONDB_BASE}/gym/{region}"

    def _elite_four_url(self, region: str) -> str:
        return f"{POKEMONDB_BASE}/elite-four/{region}"

    def _pokemon_url(self, name: str) -> str:
        return f"{POKEMONDB_BASE}/pokedex/{name.lower().replace(' ', '-')}"

    # ------------------------------------------------------------------
    # HTML → BeautifulSoup
    # ------------------------------------------------------------------

    def _soup(self, url: str) -> Optional[BeautifulSoup]:
        html = self.get_html(url)
        if html is None:
            return None
        return BeautifulSoup(html, "lxml")

    # ------------------------------------------------------------------
    # Game Pokedex (which Pokemon are obtainable)
    # ------------------------------------------------------------------

    def scrape_game_pokedex(self, version_group_slug: str) -> list[GameDexEntry]:
        """
        Scrape the list of Pokemon obtainable in *version_group_slug*.

        Returns a list of :class:`GameDexEntry` objects sorted by national
        dex number.

        URL pattern: ``/pokedex/game/{version_group_slug}``

        The page renders a table (``#pokedex``) with columns:
        dex number | name | type(s) | …
        """
        url = self._game_dex_url(version_group_slug)
        self.logger.info(f"Scraping game dex: {url}")
        soup = self._soup(url)
        if soup is None:
            self.logger.warning(f"Could not fetch game dex for {version_group_slug}")
            return []

        entries: list[GameDexEntry] = []

        # Primary selector: standard pokemondb table id
        table = soup.find("table", id="pokedex")
        if table is None:
            # Fallback: any table that looks like a Pokedex listing
            table = soup.find("table", class_=lambda c: c and "pokedex" in c.lower())

        if table is None:
            self.logger.warning(
                f"Could not find Pokedex table on {url}. "
                "The page structure may have changed — update selectors."
            )
            return []

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue  # header row or empty

            # ---- Dex number ----
            num_cell = cells[0]
            num_text = num_cell.get_text(strip=True).lstrip("#")
            try:
                national_dex = int(num_text)
            except ValueError:
                continue

            # ---- Pokemon name + link ----
            name_cell = cells[1]
            name_link = name_cell.find("a", class_="ent-name")
            if name_link is None:
                name_link = name_cell.find("a")
            if name_link is None:
                continue
            name = name_link.get_text(strip=True)
            url_path = name_link.get("href", "")

            # ---- Types ----
            types: list[str] = []
            # Types are usually in a dedicated cell (3rd column)
            if len(cells) >= 3:
                type_cell = cells[2]
                type_links = type_cell.find_all("a", class_=lambda c: c and "itype" in c)
                if not type_links:
                    # Fallback: any <a> inside the type cell
                    type_links = type_cell.find_all("a")
                types = [a.get_text(strip=True).lower() for a in type_links]

            entries.append(
                GameDexEntry(
                    national_dex=national_dex,
                    name=name,
                    types=types,
                    url_path=url_path,
                )
            )

        entries.sort(key=lambda e: e.national_dex)
        self.logger.info(
            f"  → {len(entries)} Pokemon found for {GAME_DISPLAY_NAMES.get(version_group_slug, version_group_slug)}"
        )
        return entries

    # ------------------------------------------------------------------
    # Trainer Pokemon helper
    # ------------------------------------------------------------------

    def _parse_trainer_pokemon(self, container: Tag) -> list[TrainerPokemon]:
        """
        Parse a list of TrainerPokemon from a trainer's detail container.

        pokemondb trainer pages list each Pokemon in a ``<div class="infocard">``
        or similar structure with the Pokemon name and level visible.
        Falls back to broad text search if the standard structure is absent.
        """
        pokemon_list: list[TrainerPokemon] = []

        # Strategy 1: look for infocard divs (standard pokemondb structure)
        cards = container.find_all("div", class_=lambda c: c and "infocard" in c)
        for card in cards:
            name_tag = card.find("a", class_="ent-name") or card.find("a")
            if name_tag is None:
                continue
            name = name_tag.get_text(strip=True)

            level = 0
            level_tag = card.find(string=lambda t: t and "Lv." in t)
            if level_tag:
                try:
                    level = int(level_tag.split("Lv.")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

            held_item: Optional[str] = None
            item_tag = card.find("dt", string=lambda t: t and "Held item" in (t or ""))
            if item_tag:
                item_val = item_tag.find_next_sibling("dd")
                if item_val:
                    held_item = item_val.get_text(strip=True)

            types: list[str] = []
            type_tags = card.find_all("a", class_=lambda c: c and "itype" in c)
            types = [a.get_text(strip=True).lower() for a in type_tags]

            moves: list[str] = []
            move_section = card.find("td", class_=lambda c: c and "move" in c)
            if move_section:
                moves = [
                    a.get_text(strip=True)
                    for a in move_section.find_all("a")
                ]

            pokemon_list.append(
                TrainerPokemon(
                    name=name,
                    level=level,
                    types=types,
                    held_item=held_item,
                    moves=moves,
                )
            )

        if pokemon_list:
            return pokemon_list

        # Strategy 2: look for a dl/dt/dd structure (alternate pokemondb layout)
        # <dt>Pokémon</dt><dd>Pikachu Lv.50</dd>
        dts = container.find_all("dt")
        for dt in dts:
            if "pokemon" in dt.get_text(strip=True).lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    text = dd.get_text(strip=True)
                    # Attempt to parse "Pikachu Lv.50" style text
                    if "Lv." in text:
                        parts = text.split("Lv.")
                        p_name = parts[0].strip()
                        try:
                            p_level = int(parts[1].strip().split()[0])
                        except (ValueError, IndexError):
                            p_level = 0
                        pokemon_list.append(
                            TrainerPokemon(name=p_name, level=p_level)
                        )

        return pokemon_list

    # ------------------------------------------------------------------
    # Gym leaders
    # ------------------------------------------------------------------

    def scrape_gym_leaders(self, region: str) -> list[TrainerData]:
        """
        Scrape all gym leaders for *region*.

        URL pattern: ``/gym/{region}``

        Returns a list of :class:`TrainerData` with ``role="gym_leader"``
        ordered by gym number (ascending).
        """
        url = self._gym_url(region)
        self.logger.info(f"Scraping gym leaders: {url}")
        soup = self._soup(url)
        if soup is None:
            self.logger.warning(f"Could not fetch gym page for region '{region}'")
            return []

        leaders: list[TrainerData] = []

        # pokemondb gym pages wrap each gym in a <div class="grid-col"> or
        # a <section> with an <h2> heading containing the leader's name.
        # We look for headings that identify gym leaders.
        gym_sections = soup.find_all(
            ["section", "div"],
            class_=lambda c: c and any(
                kw in c for kw in ("gym", "trainer-box", "leader")
            ),
        )

        if not gym_sections:
            # Fallback: find by h2/h3 headings that precede trainer info
            gym_sections = soup.find_all(["h2", "h3"])

        gym_number = 0
        for section in gym_sections:
            # Determine the heading text
            if section.name in ("h2", "h3"):
                heading_text = section.get_text(strip=True)
                container = section.find_next_sibling()
            else:
                heading = section.find(["h2", "h3"])
                heading_text = heading.get_text(strip=True) if heading else ""
                container = section

            if container is None:
                continue

            # Look for the leader's name and specialty type
            leader_name = ""
            specialty = ""

            # Name is often in an <h3> or a paragraph inside the section
            name_tag = (
                section.find("a", class_="ent-name")
                or section.find("strong")
                or section.find("h3")
            )
            if name_tag:
                leader_name = name_tag.get_text(strip=True)

            # Specialty type from a type badge link
            type_tag = section.find("a", class_=lambda c: c and "itype" in c)
            if type_tag:
                specialty = type_tag.get_text(strip=True).lower()

            if not leader_name:
                continue  # couldn't identify a trainer here

            # Badge and TM reward
            badge = ""
            tm_reward = None
            badge_tag = section.find(string=lambda t: t and "Badge" in (t or ""))
            if badge_tag:
                badge = badge_tag.strip()
            tm_tag = section.find(string=lambda t: t and "TM" in (t or ""))
            if tm_tag:
                tm_reward = tm_tag.strip()

            gym_number += 1
            pkmn = self._parse_trainer_pokemon(section)

            leaders.append(
                TrainerData(
                    name=leader_name,
                    role="gym_leader",
                    specialty_type=specialty,
                    game_version_group=self._region_to_version_group(region),
                    gym_number=gym_number,
                    badge=badge,
                    tm_reward=tm_reward,
                    pokemon=pkmn,
                    location=f"{region.title()} Gym #{gym_number}",
                )
            )

        self.logger.info(f"  → {len(leaders)} gym leaders found for {region}")
        return leaders

    # ------------------------------------------------------------------
    # Elite Four + Champion
    # ------------------------------------------------------------------

    def scrape_elite_four(self, region: str) -> list[TrainerData]:
        """
        Scrape the Elite Four and Champion for *region*.

        URL pattern: ``/elite-four/{region}``

        Returns a list of up to 5 :class:`TrainerData` objects:
        4 Elite Four members (``role="elite_four"``) + 1 Champion
        (``role="champion"``), ordered as encountered on the page.
        """
        url = self._elite_four_url(region)
        self.logger.info(f"Scraping Elite Four: {url}")
        soup = self._soup(url)
        if soup is None:
            self.logger.warning(f"Could not fetch Elite Four page for region '{region}'")
            return []

        trainers: list[TrainerData] = []
        order = 0

        # Each trainer is usually wrapped in a <div> or <section>.
        # pokemondb uses headings to separate trainers on these pages.
        trainer_headings = soup.find_all(["h2", "h3"])

        for heading in trainer_headings:
            trainer_name = heading.get_text(strip=True)
            if not trainer_name or len(trainer_name) < 2:
                continue

            # The container for this trainer is everything between this
            # heading and the next one at the same level.
            container = BeautifulSoup("<div></div>", "lxml").div
            assert container is not None
            for sib in heading.next_siblings:
                if sib.name in ("h2", "h3"):
                    break
                if hasattr(sib, "name"):
                    container.append(sib.__copy__())

            specialty = ""
            type_tag = heading.find_next("a", class_=lambda c: c and "itype" in c)
            if type_tag:
                specialty = type_tag.get_text(strip=True).lower()

            # Determine role
            text_lower = trainer_name.lower()
            if "champion" in text_lower:
                role = "champion"
                order_val = None
            else:
                order += 1
                role = "elite_four"
                order_val = order

            pkmn = self._parse_trainer_pokemon(container)

            trainers.append(
                TrainerData(
                    name=trainer_name,
                    role=role,
                    specialty_type=specialty,
                    game_version_group=self._region_to_version_group(region),
                    order=order_val,
                    pokemon=pkmn,
                    location="Pokemon League",
                )
            )

        self.logger.info(f"  → {len(trainers)} Elite Four / Champion entries for {region}")
        return trainers

    # ------------------------------------------------------------------
    # Item locations (Pokemart + notable items)
    # ------------------------------------------------------------------

    def scrape_items(self, version_group_slug: str) -> list[ItemLocation]:
        """
        Scrape notable item locations for a game.

        pokemondb item pages are at ``/item/{item-name}`` and list which
        games each item appears in along with how to obtain it.

        This method returns a combined list across several key items
        (evolution stones, held items, TM locations).  For a full item list
        you would iterate over all item pages, which is expensive — call
        this to get the most useful subset.

        Returns a list of :class:`ItemLocation` objects.
        """
        # Key items relevant for team-building advice
        KEY_ITEMS = [
            # Evolution stones
            "fire-stone", "water-stone", "thunder-stone", "leaf-stone",
            "moon-stone", "sun-stone", "shiny-stone", "dusk-stone", "dawn-stone",
            # Held items (competitive)
            "leftovers", "shell-bell", "choice-band", "choice-scarf",
            "choice-specs", "life-orb", "focus-sash",
            # Common battle items
            "hyper-potion", "max-potion", "full-restore", "revive", "max-revive",
            "full-heal", "antidote", "paralyze-heal", "awakening", "burn-heal",
            "ice-heal",
            # Vitamins
            "hp-up", "protein", "iron", "calcium", "zinc", "carbos",
        ]

        locations: list[ItemLocation] = []
        target_versions = self._version_group_to_versions(version_group_slug)

        for item_slug in KEY_ITEMS:
            url = f"{POKEMONDB_BASE}/item/{item_slug}"
            soup = self._soup(url)
            if soup is None:
                continue

            # Find sections that match our target game versions
            # pokemondb item pages have a table listing games → locations
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    game_text = cells[0].get_text(strip=True).lower()
                    # Check if this row is for one of our target versions
                    if not any(v.replace("-", " ") in game_text for v in target_versions):
                        continue

                    location_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    method_text = cells[2].get_text(strip=True).lower() if len(cells) > 2 else ""

                    # Infer method
                    if "shop" in method_text or "mart" in method_text or "buy" in method_text:
                        method = "shop"
                    elif "hidden" in method_text:
                        method = "hidden"
                    elif "gift" in method_text or "receive" in method_text:
                        method = "gift"
                    else:
                        method = "item_ball"

                    # Price (if shop)
                    price: Optional[int] = None
                    price_tag = row.find(string=lambda t: t and "₽" in (t or "") or "P" in (t or ""))
                    if price_tag:
                        import re
                        digits = re.sub(r"\D", "", price_tag)
                        if digits:
                            price = int(digits)

                    item_display_name = item_slug.replace("-", " ").title()
                    locations.append(
                        ItemLocation(
                            name=item_display_name,
                            location=location_text,
                            method=method,
                            price=price,
                        )
                    )

        self.logger.info(
            f"  → {len(locations)} item locations for {version_group_slug}"
        )
        return locations

    # ------------------------------------------------------------------
    # Region ↔ version-group helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _region_to_version_group(region: str) -> str:
        reverse = {v: k for k, v in VERSION_GROUP_TO_REGION.items()}
        return reverse.get(region, region)

    @staticmethod
    def _version_group_to_versions(vg: str) -> list[str]:
        from src.scraper.pokeapi import VERSION_GROUP_MAP
        return VERSION_GROUP_MAP.get(vg, [vg])

    # ------------------------------------------------------------------
    # Per-game save helpers
    # ------------------------------------------------------------------

    def _game_out_dir(self, version_group_slug: str) -> Path:
        return self.config.output_dir / version_group_slug

    def _save_game_data(
        self,
        version_group_slug: str,
        filename: str,
        data: list[Any],
    ) -> None:
        out_path = self._game_out_dir(version_group_slug) / filename
        serialisable = [_to_dict(item) for item in data]
        self.save_json(serialisable, out_path)

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def scrape_version_group(self, version_group_slug: str) -> dict[str, Any]:
        """
        Run all scrapers for one version group (e.g. ``"fire-red-leaf-green"``).

        Saves four JSON files under ``data/raw/games/{version_group_slug}/``
        and returns a summary dict.
        """
        display = GAME_DISPLAY_NAMES.get(version_group_slug, version_group_slug)
        region = VERSION_GROUP_TO_REGION.get(version_group_slug, "")
        self.logger.info(f"{'=' * 50}")
        self.logger.info(f"Scraping {display} …")

        # ---- 1. Obtainable Pokemon ----
        dex_path = self._game_out_dir(version_group_slug) / "pokedex.json"
        if dex_path.exists():
            self.logger.info("  pokedex.json already exists — skipping.")
            pokedex = self.load_json(dex_path) or []
        else:
            pokedex_entries = self.scrape_game_pokedex(version_group_slug)
            self._save_game_data(version_group_slug, "pokedex.json", pokedex_entries)
            pokedex = [_to_dict(e) for e in pokedex_entries]

        # ---- 2. Gym leaders ----
        gyms_path = self._game_out_dir(version_group_slug) / "gym_leaders.json"
        if gyms_path.exists():
            self.logger.info("  gym_leaders.json already exists — skipping.")
            gym_leaders = self.load_json(gyms_path) or []
        else:
            if region:
                gym_leader_entries = self.scrape_gym_leaders(region)
            else:
                self.logger.warning(f"No region mapping for {version_group_slug} — skipping gyms.")
                gym_leader_entries = []
            self._save_game_data(version_group_slug, "gym_leaders.json", gym_leader_entries)
            gym_leaders = [_to_dict(e) for e in gym_leader_entries]

        # ---- 3. Elite Four ----
        e4_path = self._game_out_dir(version_group_slug) / "elite4.json"
        if e4_path.exists():
            self.logger.info("  elite4.json already exists — skipping.")
            elite4 = self.load_json(e4_path) or []
        else:
            if region:
                elite4_entries = self.scrape_elite_four(region)
            else:
                self.logger.warning(f"No region mapping for {version_group_slug} — skipping Elite Four.")
                elite4_entries = []
            self._save_game_data(version_group_slug, "elite4.json", elite4_entries)
            elite4 = [_to_dict(e) for e in elite4_entries]

        # ---- 4. Items ----
        items_path = self._game_out_dir(version_group_slug) / "items.json"
        if items_path.exists():
            self.logger.info("  items.json already exists — skipping.")
            items = self.load_json(items_path) or []
        else:
            item_entries = self.scrape_items(version_group_slug)
            self._save_game_data(version_group_slug, "items.json", item_entries)
            items = [_to_dict(e) for e in item_entries]

        # ---- Game metadata (counts, etc.) ----
        meta_path = self._game_out_dir(version_group_slug) / "metadata.json"
        metadata = {
            "version_group": version_group_slug,
            "display_name": display,
            "region": region,
            "total_obtainable_pokemon": len(pokedex),
            "total_gym_leaders": len(gym_leaders),
            "total_elite_four_members": sum(
                1 for t in elite4 if t.get("role") == "elite_four"
            ),
        }
        self.save_json(metadata, meta_path)

        return {
            "pokedex": pokedex,
            "gym_leaders": gym_leaders,
            "elite4": elite4,
            "items": items,
            "metadata": metadata,
        }

    def scrape_all(self) -> dict[str, Any]:
        """
        Run :py:meth:`scrape_version_group` for every target game.

        Returns a dict keyed by version-group slug.
        """
        self.logger.info("=" * 60)
        self.logger.info("rotom-dex PokemonDB scraper — starting full run")
        self.logger.info("=" * 60)

        results: dict[str, Any] = {}
        for vg_slug in ALL_VERSION_GROUPS:
            results[vg_slug] = self.scrape_version_group(vg_slug)

        self.logger.info("=" * 60)
        self.logger.info("PokemonDB scrape complete.")
        for slug, data in results.items():
            meta = data.get("metadata", {})
            self.logger.info(
                f"  {GAME_DISPLAY_NAMES.get(slug, slug)}: "
                f"{meta.get('total_obtainable_pokemon', '?')} Pokemon, "
                f"{meta.get('total_gym_leaders', '?')} gyms, "
                f"Elite Four included: {meta.get('total_elite_four_members', 0) > 0}"
            )
        self.logger.info("=" * 60)
        return results


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
        description="Scrape PokemonDB.net data for the rotom-dex chatbot."
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/games",
        help="Root output directory (default: data/raw/games)",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/raw/scraper_cache/pokemondb",
        help="HTML response cache directory",
    )
    parser.add_argument(
        "--game",
        choices=ALL_VERSION_GROUPS + ["all"],
        default="all",
        help="Scrape a specific game version-group (default: all)",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=0.8,
        help="Requests per second — keep ≤ 1 for HTML sites (default: 0.8)",
    )
    args = parser.parse_args()

    config = ScrapeConfig(
        cache_dir=Path(args.cache_dir),
        output_dir=Path(args.output_dir),
        calls_per_second=args.rps,
    )
    scraper = PokemonDBScraper(config=config)

    if args.game == "all":
        scraper.scrape_all()
    else:
        scraper.scrape_version_group(args.game)
