"""Game registry: which PokéAPI versions are main-series RPGs and at what support tier."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "data/games/registry.json"
TIERS = ("validated", "imported", "catalog", "excluded")


@dataclass(frozen=True)
class GameEntry:
    id: int
    slug: str
    version_group_id: int
    generation_id: int
    tier: str
    is_main_series: bool
    note: str

    @property
    def imports_facts(self) -> bool:
        return self.tier in ("validated", "imported")


class Registry:
    def __init__(self, cache, path: Path = DEFAULT_REGISTRY):
        self.path = Path(path)
        self.raw_bytes = self.path.read_bytes()
        data = json.loads(self.raw_bytes)
        allowed = {
            "reviewed_at",
            "policy",
            "default_tier",
            "validated",
            "catalog",
            "excluded",
            "notes",
            "inherits",
            "inherits_policy",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown registry keys: {sorted(unknown)}")
        groups = cache.index("version_groups")
        group_slugs = {g["identifier"] for g in groups.values()}
        self.inherits: dict[str, str] = data.get("inherits", {})
        for child, parent in self.inherits.items():
            if child not in group_slugs or parent not in group_slugs:
                raise ValueError(f"Registry inherits names unknown version groups: {child}->{parent}")
        self.games: dict[str, GameEntry] = {}
        for row in cache.rows("versions"):
            slug = row["identifier"]
            group = groups[int(row["version_group_id"])]
            if slug in data["excluded"]:
                tier, note, main = "excluded", data["excluded"][slug], False
            elif slug in data["catalog"]:
                tier, note, main = "catalog", data["catalog"][slug], True
            elif slug in data["validated"]:
                tier, note, main = "validated", data["notes"].get(slug, ""), True
            else:
                tier, note, main = data["default_tier"], data["notes"].get(slug, ""), True
            if tier not in TIERS:
                raise ValueError(f"Bad tier {tier}")
            self.games[slug] = GameEntry(
                int(row["id"]),
                slug,
                int(group["id"]),
                int(group["generation_id"]),
                tier,
                main,
                note,
            )
        missing = (set(data["validated"]) | set(data["catalog"]) | set(data["excluded"])) - set(self.games)
        if missing:
            raise ValueError(f"Registry names unknown versions: {sorted(missing)}")

    def select(self, requested: list[str] | None) -> list[GameEntry]:
        """Games whose facts should be imported. `None` means every importable game."""
        if requested is None:
            return [g for g in self.games.values() if g.imports_facts]
        chosen = []
        for slug in requested:
            if slug not in self.games:
                raise ValueError(f"Unknown game: {slug}; known: {', '.join(sorted(self.games))}")
            if not self.games[slug].imports_facts:
                raise ValueError(f"{slug} is {self.games[slug].tier}; its facts are not imported")
            chosen.append(self.games[slug])
        return chosen
