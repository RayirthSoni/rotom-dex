"""
Document Builder — Phase 2 of the rotom-dex pipeline.

WHAT THIS FILE DOES
───────────────────
Reads raw JSON files (output of the scrapers) and converts them into
plain-English "documents" that can be embedded and stored in ChromaDB.

WHY PLAIN ENGLISH?
──────────────────
The embedding model (all-MiniLM-L6-v2) and the LLM both understand
natural language far better than raw JSON.  When a user asks:

  "What moves does Charizard learn in FireRed?"

The embedding of that question is semantically close to a document that
reads:

  "Charizard in FireRed / LeafGreen: Level-up moves: Scratch (Lv.1),
   Ember (Lv.7), Flamethrower (Lv.46)..."

It would NOT be close to the raw JSON:
  {"name": "charizard", "moves": {"firered-leafgreen": [...]}}

DOCUMENT TYPES PRODUCED
────────────────────────
1. pokemon_overview  — General facts: stats, abilities, evolution (game-agnostic)
2. pokemon_game      — Game-specific: moves available, where to find, held items
3. elite4            — Full Elite Four + Champion per game
4. gym_leaders       — All gym leaders per game
5. move              — Move details: power, accuracy, effect, TM/HM info
6. type_chart        — Type strengths and weaknesses
7. game_summary      — High-level game facts (answers "how many Pokemon in X")

OUTPUT
──────
Each document is saved as one line in a JSONL file:
  data/docs/pokemon_overview.jsonl
  data/docs/pokemon_game.jsonl
  data/docs/elite4.jsonl
  ...

Each line looks like:
  {"id": "pokemon_overview_0006", "text": "Charizard ...", "metadata": {...}}

The embedder (Phase 3) reads these JSONL files and loads them into ChromaDB.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GAME_DISPLAY_NAMES: dict[str, str] = {
    "firered-leafgreen": "FireRed / LeafGreen",
    "gold-silver": "Gold / Silver",
    "crystal": "Crystal",
    "heartgold-soulsilver": "HeartGold / SoulSilver",
    "diamond-pearl": "Diamond / Pearl",
    "platinum": "Platinum",
}

# Which individual game versions belong to each version-group
VERSION_GROUP_VERSIONS: dict[str, list[str]] = {
    "firered-leafgreen": ["fire-red", "leaf-green"],
    "gold-silver": ["gold", "silver"],
    "crystal": ["crystal"],
    "heartgold-soulsilver": ["heartgold", "soulsilver"],
    "diamond-pearl": ["diamond", "pearl"],
    "platinum": ["platinum"],
}

VERSION_GROUP_REGION: dict[str, str] = {
    "firered-leafgreen": "kanto",
    "gold-silver": "johto",
    "crystal": "johto",
    "heartgold-soulsilver": "johto",
    "diamond-pearl": "sinnoh",
    "platinum": "sinnoh",
}

# Human-readable labels for the 6 base stats
STAT_LABELS: dict[str, str] = {
    "hp": "HP",
    "attack": "Atk",
    "defense": "Def",
    "special-attack": "SpAtk",
    "special-defense": "SpDef",
    "speed": "Spd",
}

# Simple type-weakness cheat-sheet used in Elite Four documents
TYPE_WEAKNESSES: dict[str, str] = {
    "normal":   "Fighting",
    "fire":     "Water, Rock, Ground",
    "water":    "Electric, Grass",
    "grass":    "Fire, Ice, Poison, Flying, Bug",
    "electric": "Ground",
    "ice":      "Fire, Fighting, Rock, Steel",
    "fighting": "Psychic, Flying, Fairy",
    "poison":   "Ground, Psychic",
    "ground":   "Water, Grass, Ice",
    "flying":   "Electric, Ice, Rock",
    "psychic":  "Dark, Bug, Ghost",
    "bug":      "Fire, Flying, Rock",
    "rock":     "Water, Grass, Fighting, Ground, Steel",
    "ghost":    "Ghost, Dark",
    "dragon":   "Ice, Dragon, Fairy",
    "dark":     "Fighting, Bug, Fairy",
    "steel":    "Fire, Fighting, Ground",
    "fairy":    "Poison, Steel",
}


# ---------------------------------------------------------------------------
# Document dataclass
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """
    One chunk of text that will be embedded and stored in ChromaDB.

    Fields
    ------
    id : str
        Unique identifier used as the ChromaDB document ID.
        Examples: "pokemon_overview_0006", "elite4_platinum", "move_flamethrower"

    text : str
        The plain-English content that gets turned into an embedding vector.
        This is what the LLM reads as "context" when answering a question.

    category : str
        Which builder produced this document.  Used for filtering:
        "only search pokemon_game documents" etc.

    metadata : dict
        Filterable key-value pairs stored alongside the embedding in ChromaDB.
        Used for WHERE-clause filtering:
            collection.query(where={"game": "platinum"})
        IMPORTANT: ChromaDB metadata values must be str, int, float, or bool.
        Lists must be stored as comma-separated strings.

    source_file : str
        Which raw JSON file this document came from — useful for debugging.
    """

    id: str
    text: str
    category: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Document":
        return cls(
            id=d["id"],
            text=d["text"],
            category=d["category"],
            metadata=d.get("metadata", {}),
            source_file=d.get("source_file", ""),
        )


# ---------------------------------------------------------------------------
# Main builder class
# ---------------------------------------------------------------------------


class DocumentBuilder:
    """
    Reads raw JSON scraped data and produces Document objects for ChromaDB.

    Usage
    -----
    ::

        builder = DocumentBuilder(raw_dir="data/raw", output_dir="data/docs")
        docs = builder.build_all()
        # → writes data/docs/*.jsonl
        # → returns list of all Document objects

    Parameters
    ----------
    raw_dir : Path
        Root of the scraped data tree (output of the scrapers).
    output_dir : Path
        Where to write the JSONL document files.
    """

    def __init__(
        self,
        raw_dir: str | Path = "data/raw",
        output_dir: str | Path = "data/docs",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-loaded caches so each JSON file is read at most once
        self._move_cache: dict[str, Optional[dict]] = {}
        self._ability_cache: dict[str, Optional[dict]] = {}

    # ------------------------------------------------------------------
    # Private text-formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slug_to_title(slug: str) -> str:
        """'fire-red-leaf-green' → 'Fire Red Leaf Green'"""
        return slug.replace("-", " ").title()

    @staticmethod
    def _location_name(slug: str) -> str:
        """
        Convert a raw PokeAPI location-area slug to a readable place name.

        'pallet-town-area'  → 'Pallet Town'
        'mt-moon-b2f'       → 'Mt Moon B2F'
        'route-1-area'      → 'Route 1'
        """
        # Remove noise suffixes
        slug = re.sub(r"-area$", "", slug)
        slug = re.sub(r"-(1f|2f|3f|b1f|b2f|b3f)$", r" \1", slug)
        return slug.replace("-", " ").title()

    @staticmethod
    def _stat_line(stats: dict[str, int]) -> str:
        """
        Format the 6 base stats as a compact readable line.

        {'hp': 78, 'attack': 84, ...}
        → 'HP: 78 | Atk: 84 | Def: 78 | SpAtk: 109 | SpDef: 85 | Spd: 100 | Total: 534'
        """
        parts = []
        for key, label in STAT_LABELS.items():
            if key in stats:
                parts.append(f"{label}: {stats[key]}")
        if parts:
            total = sum(stats.values())
            parts.append(f"Total: {total}")
        return " | ".join(parts)

    def _load_move(self, move_name: str) -> Optional[dict]:
        """Load move JSON once and cache it."""
        if move_name not in self._move_cache:
            path = self.raw_dir / "moves" / f"{move_name}.json"
            try:
                self._move_cache[move_name] = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                self._move_cache[move_name] = None
        return self._move_cache[move_name]

    def _move_line(self, move_name: str) -> str:
        """
        Format a move as a one-line summary including type, class, power, accuracy.

        'flamethrower' → 'Flamethrower (Fire, Special, Pow: 90, Acc: 100%)'
        'growl'        → 'Growl (Normal, Status, Acc: 100%)'
        """
        data = self._load_move(move_name)
        display = move_name.replace("-", " ").title()
        if not data:
            return display

        parts: list[str] = []
        if data.get("type"):
            parts.append(data["type"].title())
        if data.get("damage_class"):
            parts.append(data["damage_class"].title())
        if data.get("power"):
            parts.append(f"Pow: {data['power']}")
        if data.get("accuracy"):
            parts.append(f"Acc: {data['accuracy']}%")

        return f"{display} ({', '.join(parts)})" if parts else display

    @staticmethod
    def _evo_chain_text(chain: list[dict]) -> str:
        """
        Convert the flat evolution-steps list into a readable chain string.

        Input (from scraper):
          [
            {"from": "charmander", "to": "charmeleon",
             "trigger": "level-up", "conditions": {"min_level": 16}},
            {"from": "charmeleon", "to": "charizard",
             "trigger": "level-up", "conditions": {"min_level": 36}},
          ]

        Output:
          "Charmander → (Lv. 16) → Charmeleon → (Lv. 36) → Charizard"
        """
        if not chain:
            return "Does not evolve."

        def condition_label(step: dict) -> str:
            trigger = step.get("trigger", "")
            cond = step.get("conditions", {})
            if trigger == "level-up":
                lvl = cond.get("min_level")
                if cond.get("time_of_day"):
                    return f"Lv. {lvl} at {cond['time_of_day'].title()}" if lvl else "Level up"
                if cond.get("min_happiness"):
                    return f"High friendship{f' (Lv. {lvl})' if lvl else ''}"
                return f"Lv. {lvl}" if lvl else "Level up"
            if trigger == "use-item":
                item = cond.get("item", "").replace("-", " ").title()
                return f"use {item}"
            if trigger == "trade":
                item = cond.get("held_item", "").replace("-", " ").title()
                return f"Trade{f' holding {item}' if item else ''}"
            return trigger.replace("-", " ").title() if trigger else "?"

        # Build ordered species list with conditions between them
        # chain is already flat: [{from, to, trigger, conditions}, ...]
        # We reconstruct: species0 →(cond)→ species1 →(cond)→ species2 ...
        segments: list[str] = []
        first_step = chain[0]
        segments.append(first_step["from"].replace("-", " ").title())

        for step in chain:
            cond = condition_label(step)
            segments.append(f"→ ({cond}) →")
            segments.append(step["to"].replace("-", " ").title())

        return " ".join(segments)

    # ------------------------------------------------------------------
    # 1. Pokemon Overview documents
    # ------------------------------------------------------------------

    def build_pokemon_overview_docs(self) -> list[Document]:
        """
        Build one document per Pokemon containing general information that
        does NOT change between games: types, base stats, abilities, evolution.

        Example output for Charizard
        ────────────────────────────
        Charizard (National Dex #006) is a Fire / Flying type Pokémon.
        Category: Flame Pokémon. Generation: I.
        Height: 1.7 m | Weight: 90.5 kg | Base Experience: 267.
        Base Stats → HP: 78 | Atk: 84 | Def: 78 | SpAtk: 109 | SpDef: 85 | Spd: 100 | Total: 534.
        Abilities: Blaze. Hidden Ability: Solar Power.
        Egg Groups: Monster, Dragon. Growth Rate: Medium Slow. Capture Rate: 45.
        Legendary: No. Mythical: No.
        Evolution chain: Charmander → (Lv. 16) → Charmeleon → (Lv. 36) → Charizard.
        Pokédex: Spits fire that is hot enough to melt boulders.
        """
        docs: list[Document] = []
        pokemon_dir = self.raw_dir / "pokemon"

        if not pokemon_dir.exists():
            logger.warning(f"Pokemon directory not found: {pokemon_dir}. Run pokeapi.py first.")
            return docs

        for json_file in sorted(pokemon_dir.glob("*.json")):
            try:
                p: dict = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Could not read {json_file}: {exc}")
                continue

            dex_num: int = p.get("national_dex", 0)
            name: str = p.get("name", "unknown").replace("-", " ").title()
            types: str = " / ".join(t.title() for t in p.get("types", []))
            gen: str = (p.get("generation_introduced") or "").replace("generation-", "").upper()

            # ---- Abilities ----
            abilities = p.get("abilities", [])
            normal_ab = [a["name"].replace("-", " ").title() for a in abilities if not a["is_hidden"]]
            hidden_ab = [a["name"].replace("-", " ").title() for a in abilities if a["is_hidden"]]
            ability_str = "Abilities: " + (", ".join(normal_ab) or "None")
            if hidden_ab:
                ability_str += ". Hidden Ability: " + ", ".join(hidden_ab)

            # ---- Evolution chain ----
            evo_text = self._evo_chain_text(p.get("evolution_chain", []))

            # ---- Pokédex flavor text (take first available) ----
            flavor_texts: dict[str, str] = p.get("flavor_texts", {})
            flavor = next(iter(flavor_texts.values()), "")

            # ---- Assemble ----
            text = (
                f"{name} (National Dex #{dex_num:03d}) is a {types} type Pokémon.\n"
                f"Category: {p.get('genus', 'Unknown Pokémon')}. Generation: {gen}.\n"
                f"Height: {(p.get('height_dm') or 0) / 10:.1f} m | "
                f"Weight: {(p.get('weight_hg') or 0) / 10:.1f} kg | "
                f"Base Experience: {p.get('base_experience', '?')}.\n"
                f"Base Stats → {self._stat_line(p.get('base_stats', {}))}.\n"
                f"{ability_str}.\n"
                f"Egg Groups: {', '.join(p.get('egg_groups', [])) or 'None'}. "
                f"Growth Rate: {(p.get('growth_rate') or '').replace('-', ' ').title()}. "
                f"Capture Rate: {p.get('capture_rate', '?')}.\n"
                f"Legendary: {'Yes' if p.get('is_legendary') else 'No'}. "
                f"Mythical: {'Yes' if p.get('is_mythical') else 'No'}.\n"
                f"Evolution: {evo_text}"
            )
            if flavor:
                text += f"\nPokédex: {flavor}"

            # NOTE: ChromaDB metadata values must be str/int/float/bool — NOT lists.
            # We join list values as comma-separated strings for filtering.
            docs.append(Document(
                id=f"pokemon_overview_{dex_num:04d}",
                text=text,
                category="pokemon_overview",
                metadata={
                    "national_dex":  dex_num,
                    "name":          p.get("name", ""),
                    "types":         ",".join(p.get("types", [])),   # "fire,flying"
                    "generation":    p.get("generation_introduced", ""),
                    "is_legendary":  p.get("is_legendary", False),
                    "is_mythical":   p.get("is_mythical", False),
                    "category":      "pokemon_overview",
                },
                source_file=str(json_file),
            ))

        logger.info(f"Built {len(docs)} pokemon_overview documents.")
        return docs

    # ------------------------------------------------------------------
    # 2. Pokemon × Game documents
    # ------------------------------------------------------------------

    def build_pokemon_game_docs(self) -> list[Document]:
        """
        Build one document per (Pokemon, version-group) with game-specific data.
        Only creates a document if the Pokemon actually exists in that game
        (has learnable moves or known encounter locations).

        Example output for Charizard in FireRed/LeafGreen
        ──────────────────────────────────────────────────
        Charizard in FireRed / LeafGreen:
        Availability: Not found in the wild. Evolves from Charmeleon.
        How to obtain: Starter Pokémon — Charmander is received from Professor Oak.

        Level-up moves:
          Lv.  1  Scratch (Normal, Physical, Pow: 40, Acc: 100%)
          Lv.  1  Growl (Normal, Status, Acc: 100%)
          Lv.  7  Ember (Fire, Special, Pow: 40, Acc: 100%)
          Lv. 13  Metal Claw (Steel, Physical, Pow: 50, Acc: 95%)
          Lv. 46  Flamethrower (Fire, Special, Pow: 95, Acc: 100%)
          ...

        TM / HM moves: Dragon Claw (Steel, Physical, Pow: 80, Acc: 100%), Fly, ...
        Egg moves: Dragon Dance, Belly Drum
        Wild held items: None
        """
        docs: list[Document] = []
        pokemon_dir = self.raw_dir / "pokemon"

        if not pokemon_dir.exists():
            return docs

        for json_file in sorted(pokemon_dir.glob("*.json")):
            try:
                p: dict = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            dex_num: int = p.get("national_dex", 0)
            name: str = p.get("name", "unknown").replace("-", " ").title()
            moves_by_vg: dict = p.get("moves", {})
            enc_by_version: dict = p.get("encounters", {})
            held_by_version: dict = p.get("held_items", {})

            for vg, game_display in GAME_DISPLAY_NAMES.items():
                game_moves: list[dict] = moves_by_vg.get(vg, [])

                # Gather encounters for all versions in this group
                versions = VERSION_GROUP_VERSIONS.get(vg, [])
                game_encounters: dict[str, list] = {
                    v: enc_by_version[v]
                    for v in versions
                    if v in enc_by_version
                }
                game_held: dict[str, list] = {
                    v: held_by_version[v]
                    for v in versions
                    if v in held_by_version
                }

                # Skip if this Pokemon simply doesn't exist in this game
                if not game_moves and not game_encounters:
                    continue

                # ── Availability / location ──────────────────────────────
                if game_encounters:
                    # Deduplicate by location name
                    seen: set[str] = set()
                    loc_lines: list[str] = []
                    for version, encs in game_encounters.items():
                        for enc in encs:
                            loc = self._location_name(enc["location_area"])
                            key = f"{version}:{loc}"
                            if key in seen:
                                continue
                            seen.add(key)
                            loc_lines.append(
                                f"  {loc} "
                                f"(method: {enc['method']}, "
                                f"levels {enc['min_level']}–{enc['max_level']}, "
                                f"{enc['chance']}% encounter rate)"
                            )
                    location_text = "Locations:\n" + "\n".join(loc_lines)
                else:
                    evolves_from = p.get("evolves_from", "")
                    if evolves_from:
                        location_text = (
                            f"Not found in the wild in {game_display}. "
                            f"Evolves from {evolves_from.replace('-', ' ').title()}."
                        )
                    else:
                        location_text = (
                            f"Not found in the wild in {game_display} "
                            f"(starter, gift, in-game trade, or import only)."
                        )

                # ── Move sections ────────────────────────────────────────
                level_up = [m for m in game_moves if m["learn_method"] == "level-up"]
                machines  = [m for m in game_moves if m["learn_method"] == "machine"]
                egg_moves = [m for m in game_moves if m["learn_method"] == "egg"]
                tutor     = [m for m in game_moves if m["learn_method"] == "tutor"]

                sections: list[str] = [f"{name} in {game_display}:", location_text]

                if level_up:
                    lines = [
                        f"  Lv. {m['level']:3d}  {self._move_line(m['name'])}"
                        for m in level_up[:25]   # cap to keep documents a sane size
                    ]
                    if len(level_up) > 25:
                        lines.append(f"  ... and {len(level_up) - 25} more level-up moves")
                    sections.append("Level-up moves:\n" + "\n".join(lines))

                if machines:
                    tm_names = [self._move_line(m["name"]) for m in machines]
                    sections.append("TM / HM moves: " + ", ".join(tm_names))

                if egg_moves:
                    egg_names = [m["name"].replace("-", " ").title() for m in egg_moves]
                    sections.append("Egg moves: " + ", ".join(egg_names))

                if tutor:
                    tutor_names = [m["name"].replace("-", " ").title() for m in tutor]
                    sections.append("Move tutor moves: " + ", ".join(tutor_names))

                # ── Held items ───────────────────────────────────────────
                if game_held:
                    held_parts: list[str] = []
                    for items in game_held.values():
                        for item in items:
                            held_parts.append(
                                f"{item['name'].replace('-', ' ').title()} "
                                f"({item['rarity']}% chance)"
                            )
                    sections.append("Wild held items: " + ", ".join(held_parts))
                else:
                    sections.append("Wild held items: None")

                docs.append(Document(
                    id=f"pokemon_game_{dex_num:04d}_{vg}",
                    text="\n".join(sections),
                    category="pokemon_game",
                    metadata={
                        "national_dex": dex_num,
                        "name":         p.get("name", ""),
                        "types":        ",".join(p.get("types", [])),
                        "game":         vg,
                        "category":     "pokemon_game",
                    },
                    source_file=str(json_file),
                ))

        logger.info(f"Built {len(docs)} pokemon_game documents.")
        return docs

    # ------------------------------------------------------------------
    # 3. Elite Four + Champion documents
    # ------------------------------------------------------------------

    def build_elite4_docs(self) -> list[Document]:
        """
        Build one document per game describing the full Elite Four + Champion.

        Example output (Kanto — FireRed / LeafGreen)
        ─────────────────────────────────────────────
        Elite Four and Champion — FireRed / LeafGreen:

        1. Lorelei — Ice-type specialist
          • Dewgong (Lv. 54): Surf, Ice Beam, Growl, Confuse Ray
          • Cloyster (Lv. 53): Surf, Ice Beam, Spike Cannon, Aurora Beam
          • Slowbro (Lv. 54): Surf, Psychic, Ice Beam, Amnesia
          • Jynx (Lv. 56): Lovely Kiss, Blizzard, Psychic, Body Slam
          • Lapras (Lv. 60): Surf, Ice Beam, Confuse Ray, Body Slam
          → Counters: Electric types dominate (4 Water/Ice), Fire for Jynx,
            Rock/Fighting also effective.
          → Weak to: Fire, Fighting, Rock, Steel

        2. Bruno — Fighting-type specialist
          ...

        Champion: Blue / Gary
          ...
        """
        docs: list[Document] = []
        games_dir = self.raw_dir / "games"

        if not games_dir.exists():
            logger.warning(f"Games directory not found: {games_dir}. Run pokemondb.py first.")
            return docs

        for game_dir in sorted(games_dir.iterdir()):
            if not game_dir.is_dir():
                continue

            e4_file = game_dir / "elite4.json"
            if not e4_file.exists():
                continue

            vg = game_dir.name
            game_display = GAME_DISPLAY_NAMES.get(vg, vg)

            try:
                trainers: list[dict] = json.loads(e4_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            if not trainers:
                continue

            lines: list[str] = [f"Elite Four and Champion — {game_display}:", ""]

            for trainer in trainers:
                role      = trainer.get("role", "")
                tname     = trainer.get("name", "Unknown")
                specialty = trainer.get("specialty_type", "").strip()
                order     = trainer.get("order")

                # Header line
                if role == "elite_four" and order:
                    lines.append(f"{order}. {tname} — {specialty.title()}-type specialist")
                elif role == "champion":
                    lines.append(f"Champion: {tname}")
                else:
                    lines.append(tname)

                # Pokemon team
                for pkmn in trainer.get("pokemon", []):
                    pname  = pkmn.get("name", "?")
                    level  = pkmn.get("level", "?")
                    held   = pkmn.get("held_item", "")
                    moves  = pkmn.get("moves", [])
                    types  = pkmn.get("types", [])

                    p_line = f"  • {pname} (Lv. {level})"
                    if held:
                        p_line += f" @ {held.replace('-', ' ').title()}"
                    if types:
                        p_line += f" [{'/'.join(t.title() for t in types)}]"
                    if moves:
                        p_line += ": " + ", ".join(m.replace("-", " ").title() for m in moves)
                    lines.append(p_line)

                # Type weakness hint
                weakness = TYPE_WEAKNESSES.get(specialty.lower(), "")
                if weakness:
                    lines.append(f"  → Weak to: {weakness}")

                lines.append("")  # blank line between trainers

            docs.append(Document(
                id=f"elite4_{vg}",
                text="\n".join(lines).strip(),
                category="elite4",
                metadata={
                    "game":     vg,
                    "region":   VERSION_GROUP_REGION.get(vg, ""),
                    "category": "elite4",
                },
                source_file=str(e4_file),
            ))

        logger.info(f"Built {len(docs)} elite4 documents.")
        return docs

    # ------------------------------------------------------------------
    # 4. Gym Leader documents
    # ------------------------------------------------------------------

    def build_gym_leader_docs(self) -> list[Document]:
        """
        Build one document per game listing all gym leaders in order.

        Example output (Kanto)
        ──────────────────────
        Gym Leaders — FireRed / LeafGreen:

        Gym 1: Brock (Rock-type) — Boulder Badge. TM: Rock Tomb.
          • Geodude (Lv. 12)
          • Onix (Lv. 14)
          → Weak to: Water, Grass, Fighting, Ground, Steel

        Gym 2: Misty (Water-type) — Cascade Badge. TM: Water Pulse.
          ...
        """
        docs: list[Document] = []
        games_dir = self.raw_dir / "games"

        if not games_dir.exists():
            return docs

        for game_dir in sorted(games_dir.iterdir()):
            if not game_dir.is_dir():
                continue

            gyms_file = game_dir / "gym_leaders.json"
            if not gyms_file.exists():
                continue

            vg = game_dir.name
            game_display = GAME_DISPLAY_NAMES.get(vg, vg)

            try:
                leaders: list[dict] = json.loads(gyms_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            if not leaders:
                continue

            lines: list[str] = [f"Gym Leaders — {game_display}:", ""]

            for leader in leaders:
                lname     = leader.get("name", "?")
                specialty = leader.get("specialty_type", "").strip()
                badge     = leader.get("badge", "")
                gym_num   = leader.get("gym_number", "?")
                tm        = leader.get("tm_reward", "")
                location  = leader.get("location", "")

                header = f"Gym {gym_num}: {lname} ({specialty.title()}-type)"
                if badge:
                    header += f" — {badge}"
                if location:
                    header += f" — {location}"
                lines.append(header)

                if tm:
                    lines.append(f"  TM reward: {tm}")

                for pkmn in leader.get("pokemon", []):
                    pname = pkmn.get("name", "?")
                    level = pkmn.get("level", "?")
                    moves = pkmn.get("moves", [])
                    p_line = f"  • {pname} (Lv. {level})"
                    if moves:
                        p_line += ": " + ", ".join(m.replace("-", " ").title() for m in moves)
                    lines.append(p_line)

                weakness = TYPE_WEAKNESSES.get(specialty.lower(), "")
                if weakness:
                    lines.append(f"  → Weak to: {weakness}")
                lines.append("")

            docs.append(Document(
                id=f"gym_leaders_{vg}",
                text="\n".join(lines).strip(),
                category="gym_leaders",
                metadata={
                    "game":     vg,
                    "region":   VERSION_GROUP_REGION.get(vg, ""),
                    "category": "gym_leaders",
                },
                source_file=str(gyms_file),
            ))

        logger.info(f"Built {len(docs)} gym_leaders documents.")
        return docs

    # ------------------------------------------------------------------
    # 5. Move documents
    # ------------------------------------------------------------------

    def build_move_docs(self) -> list[Document]:
        """
        Build one document per move with its full details.

        Example output for Flamethrower
        ─────────────────────────────────
        Flamethrower — Fire type, Special move.
        Power: 95 | Accuracy: 100% | PP: 15 | Priority: 0.
        Effect: Shoots a stream of fire. Has a 10% chance to burn the target.
        TM: TM35 in FireRed / LeafGreen | TM35 in HeartGold / SoulSilver | TM35 in Platinum.
        """
        docs: list[Document] = []
        moves_dir = self.raw_dir / "moves"

        if not moves_dir.exists():
            logger.warning(f"Moves directory not found: {moves_dir}.")
            return docs

        for json_file in sorted(moves_dir.glob("*.json")):
            try:
                m: dict = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            display_name = m.get("name", "").replace("-", " ").title()
            move_type    = (m.get("type") or "?").title()
            dmg_class    = (m.get("damage_class") or "?").title()
            power        = m.get("power") or "—"
            accuracy     = m.get("accuracy") or "—"
            pp           = m.get("pp") or "?"
            effect       = m.get("short_effect") or m.get("effect") or "No description available."

            # TM/HM info across target games
            machines: dict[str, str] = m.get("machines", {})
            tm_parts: list[str] = []
            for vg, tm_name in machines.items():
                game = GAME_DISPLAY_NAMES.get(vg, vg)
                tm_parts.append(f"{tm_name.upper()} in {game}")

            text = (
                f"{display_name} — {move_type} type, {dmg_class} move.\n"
                f"Power: {power} | Accuracy: {accuracy}% | PP: {pp} | Priority: {m.get('priority', 0)}.\n"
                f"Effect: {effect}"
            )
            if tm_parts:
                text += "\nTM/HM: " + " | ".join(tm_parts)

            docs.append(Document(
                id=f"move_{m.get('name', 'unknown')}",
                text=text,
                category="move",
                metadata={
                    "name":         m.get("name", ""),
                    "move_type":    m.get("type", ""),
                    "damage_class": m.get("damage_class", ""),
                    "category":     "move",
                },
                source_file=str(json_file),
            ))

        logger.info(f"Built {len(docs)} move documents.")
        return docs

    # ------------------------------------------------------------------
    # 6. Type chart documents
    # ------------------------------------------------------------------

    def build_type_docs(self) -> list[Document]:
        """
        Build one document per type describing its full effectiveness chart.

        Example output for Fire type
        ─────────────────────────────
        Fire type — strengths and weaknesses:

        ATTACKING:
          Super-effective against (2×): Grass, Ice, Bug, Steel
          Not very effective against (½×): Fire, Water, Rock, Dragon
          No effect against (0×): None

        DEFENDING:
          Weak to (2×): Water, Ground, Rock
          Resists (½×): Fire, Grass, Ice, Bug, Steel, Fairy
          Immune to (0×): None
        """
        docs: list[Document] = []
        types_dir = self.raw_dir / "types"

        if not types_dir.exists():
            logger.warning(f"Types directory not found: {types_dir}.")
            return docs

        for json_file in sorted(types_dir.glob("*.json")):
            try:
                t: dict = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            type_name = t.get("name", "unknown")
            display   = type_name.title()

            def fmt(names: list[str]) -> str:
                return ", ".join(n.title() for n in names) if names else "None"

            text = (
                f"{display} type — strengths and weaknesses:\n\n"
                f"ATTACKING:\n"
                f"  Super-effective against (2×): {fmt(t.get('double_damage_to', []))}\n"
                f"  Not very effective against (½×): {fmt(t.get('half_damage_to', []))}\n"
                f"  No effect against (0×): {fmt(t.get('no_damage_to', []))}\n\n"
                f"DEFENDING:\n"
                f"  Weak to (2×): {fmt(t.get('double_damage_from', []))}\n"
                f"  Resists (½×): {fmt(t.get('half_damage_from', []))}\n"
                f"  Immune to (0×): {fmt(t.get('no_damage_from', []))}"
            )

            docs.append(Document(
                id=f"type_{type_name}",
                text=text,
                category="type_chart",
                metadata={
                    "name":           type_name,
                    "weak_to":        ",".join(t.get("double_damage_from", [])),
                    "strong_against": ",".join(t.get("double_damage_to", [])),
                    "category":       "type_chart",
                },
                source_file=str(json_file),
            ))

        logger.info(f"Built {len(docs)} type_chart documents.")
        return docs

    # ------------------------------------------------------------------
    # 7. Game summary documents
    # ------------------------------------------------------------------

    def build_game_summary_docs(self) -> list[Document]:
        """
        Build one document per game with high-level facts.

        These directly answer count questions like "how many Pokemon are in Platinum?"
        without needing semantic search at all (the classifier routes these to a
        metadata lookup instead of RAG).

        Example output
        ──────────────
        Platinum — Game Summary:
        Region: Sinnoh
        Total obtainable Pokémon: 210
        Gym Leaders: 8
        Elite Four members: 4
        Champion: Cynthia
        """
        docs: list[Document] = []
        games_dir = self.raw_dir / "games"

        if not games_dir.exists():
            return docs

        for game_dir in sorted(games_dir.iterdir()):
            if not game_dir.is_dir():
                continue

            vg = game_dir.name
            game_display = GAME_DISPLAY_NAMES.get(vg, vg)

            # Load metadata.json (written by pokemondb scraper)
            meta: dict = {}
            meta_file = game_dir / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            # Count from pokedex.json if metadata is missing
            total_pokemon = meta.get("total_obtainable_pokemon", 0)
            if not total_pokemon:
                pokedex_file = game_dir / "pokedex.json"
                if pokedex_file.exists():
                    try:
                        total_pokemon = len(json.loads(pokedex_file.read_text()))
                    except (json.JSONDecodeError, OSError):
                        pass

            # Find champion name from elite4.json
            champion_name = ""
            e4_file = game_dir / "elite4.json"
            if e4_file.exists():
                try:
                    trainers = json.loads(e4_file.read_text(encoding="utf-8"))
                    for t in trainers:
                        if t.get("role") == "champion":
                            champion_name = t.get("name", "")
                            break
                except (json.JSONDecodeError, OSError):
                    pass

            text = (
                f"{game_display} — Game Summary:\n"
                f"Region: {meta.get('region', VERSION_GROUP_REGION.get(vg, '?')).title()}\n"
                f"Total obtainable Pokémon: {total_pokemon}\n"
                f"Gym Leaders: {meta.get('total_gym_leaders', '?')}\n"
                f"Elite Four members: {meta.get('total_elite_four_members', '?')}"
            )
            if champion_name:
                text += f"\nChampion: {champion_name}"

            docs.append(Document(
                id=f"game_summary_{vg}",
                text=text,
                category="game_summary",
                metadata={
                    "game":           vg,
                    "region":         meta.get("region", VERSION_GROUP_REGION.get(vg, "")),
                    "total_pokemon":  total_pokemon,
                    "category":       "game_summary",
                },
                source_file=str(game_dir),
            ))

        logger.info(f"Built {len(docs)} game_summary documents.")
        return docs

    # ------------------------------------------------------------------
    # Orchestrator — runs all builders and saves JSONL output
    # ------------------------------------------------------------------

    def build_all(self) -> list[Document]:
        """
        Run all document builders and save results to data/docs/*.jsonl.

        JSONL format = one JSON object per line.  The embedder reads these
        files and loads them into ChromaDB.

        Returns all produced Document objects.
        """
        logger.info("=" * 60)
        logger.info("Document Builder — starting")
        logger.info("=" * 60)

        # Each tuple: (output filename stem, builder method)
        builders: list[tuple[str, Callable[[], list[Document]]]] = [
            ("pokemon_overview", self.build_pokemon_overview_docs),
            ("pokemon_game",     self.build_pokemon_game_docs),
            ("elite4",           self.build_elite4_docs),
            ("gym_leaders",      self.build_gym_leader_docs),
            ("moves",            self.build_move_docs),
            ("type_chart",       self.build_type_docs),
            ("game_summary",     self.build_game_summary_docs),
        ]

        all_docs: list[Document] = []

        for stem, builder_fn in builders:
            docs = builder_fn()
            all_docs.extend(docs)

            # Save as JSONL
            out_file = self.output_dir / f"{stem}.jsonl"
            with open(out_file, "w", encoding="utf-8") as fh:
                for doc in docs:
                    fh.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")

            logger.info(f"  ✓ {stem:20s} {len(docs):>6,} docs  →  {out_file}")

        logger.info("=" * 60)
        logger.info(f"Total: {len(all_docs):,} documents written to {self.output_dir}")
        logger.info("=" * 60)
        return all_docs

    # ------------------------------------------------------------------
    # Load helper (used by the embedder in Phase 3)
    # ------------------------------------------------------------------

    @staticmethod
    def load_all(docs_dir: str | Path) -> list[Document]:
        """
        Read all *.jsonl files from docs_dir and return Document objects.

        The embedder calls this to load documents before embedding them.

        Example
        -------
        ::

            docs = DocumentBuilder.load_all("data/docs")
            # → [Document(id="pokemon_overview_0001", ...), ...]
        """
        docs: list[Document] = []
        for jsonl_file in sorted(Path(docs_dir).glob("*.jsonl")):
            with open(jsonl_file, encoding="utf-8") as fh:
                for line_num, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        docs.append(Document.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.warning(f"Skipping bad line {line_num} in {jsonl_file}: {exc}")
        logger.info(f"Loaded {len(docs):,} documents from {docs_dir}")
        return docs
