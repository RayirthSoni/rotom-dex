"""Reviewed data packages: per-version-group mechanics and per-game curated content.

Both formats are validated strictly. Every curated fact names at least one
reference (URL + access date) which becomes a `reference` source; facts are
recorded as `reference-reviewed` (or `unverified` when the pack says so). Prose is
never copied from references; only structured facts are recorded.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from rotom_dex.domain.conditions import validate_condition

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MECHANICS = ROOT / "data/mechanics/version_groups.json"
DEFAULT_PACKS_DIR = ROOT / "data/game-packs"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

MECHANIC_KEYS = (
    "abilities",
    "hidden_abilities",
    "natures",
    "held_items",
    "breeding",
    "physical_special_split",
    "special_stat_single",
    "tm_present",
    "tm_reusable",
    "hm_present",
    "tr_present",
    "fairy_type",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"Invalid pack: {message}")


def _check_keys(obj: dict, allowed: set[str], required: set[str], where: str) -> None:
    _require(isinstance(obj, dict), f"{where} must be an object")
    extra = set(obj) - allowed
    _require(not extra, f"{where} has unknown keys {sorted(extra)}")
    lacking = required - set(obj)
    _require(not lacking, f"{where} lacks required keys {sorted(lacking)}")


class MechanicsPack:
    def __init__(self, path: Path = DEFAULT_MECHANICS):
        self.path = Path(path)
        self.raw_bytes = self.path.read_bytes()
        data = json.loads(self.raw_bytes)
        _check_keys(
            data,
            {
                "reviewed_at",
                "review_status",
                "policy",
                "keys",
                "references",
                "profiles",
                "version_groups",
                "unverified",
            },
            {"reviewed_at", "keys", "references", "profiles", "version_groups"},
            "mechanics pack",
        )
        _require(set(data["keys"]) == set(MECHANIC_KEYS), "mechanics keys differ from schema")
        for key in MECHANIC_KEYS:
            _require(key in data["references"], f"mechanics reference missing for {key}")
        for name, profile in data["profiles"].items():
            _check_keys(profile, set(MECHANIC_KEYS), set(), f"profile {name}")
            _require(all(v in (0, 1) for v in profile.values()), f"profile {name} values must be 0/1")
        for vg, profile in data["version_groups"].items():
            _require(profile in data["profiles"], f"{vg} uses unknown profile {profile}")
        self.data = data
        self.reviewed_at = data["reviewed_at"]
        self.references: dict[str, str] = data["references"]
        self.unverified: dict[str, dict[str, str]] = data.get("unverified", {})

    def sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()

    def covers(self, version_group_slug: str) -> bool:
        return version_group_slug in self.data["version_groups"]

    def values(self, version_group_slug: str) -> dict[str, int]:
        profile = self.data["version_groups"].get(version_group_slug)
        return dict(self.data["profiles"][profile]) if profile else {}

    def value(self, version_group_slug: str, key: str) -> int | None:
        return self.values(version_group_slug).get(key)

    def status(self, version_group_slug: str, key: str) -> tuple[str, str]:
        note = self.unverified.get(version_group_slug, {}).get(key)
        if note:
            return "unverified", note
        return "reference-reviewed", ""


class GamePack:
    ALLOWED = {
        "format_version",
        "game",
        "reviewed_at",
        "policy",
        "references",
        "mechanics",
        "milestones",
        "battles",
        "acquisitions",
        "shops",
        "tutors",
        "evolution_overrides",
        "issues",
    }

    def __init__(self, path: Path):
        self.path = Path(path)
        self.raw_bytes = self.path.read_bytes()
        data = json.loads(self.raw_bytes)
        _check_keys(
            data,
            self.ALLOWED,
            {"format_version", "game", "reviewed_at", "references"},
            f"game pack {path}",
        )
        _require(data["format_version"] == 2, "game pack format_version must be 2")
        _require(SLUG.match(data["game"]), "game must be a slug")
        self.game: str = data["game"]
        self.reviewed_at: str = data["reviewed_at"]
        self.references: dict[str, dict] = data["references"]
        for ref_id, ref in self.references.items():
            _check_keys(
                ref,
                {"url", "accessed", "license", "note"},
                {"url", "accessed", "license"},
                f"reference {ref_id}",
            )
            _require(ref["url"].startswith("http"), f"reference {ref_id} needs a URL")
        self.mechanics: dict = data.get("mechanics", {})
        for key, entry in self.mechanics.items():
            _require(key in MECHANIC_KEYS, f"unknown mechanic {key}")
            _check_keys(entry, {"value", "note", "references"}, {"value", "references"}, f"mechanic {key}")
            self._refs(entry["references"], f"mechanic {key}")
        self.milestones = data.get("milestones", [])
        for i, m in enumerate(self.milestones):
            _check_keys(
                m,
                {
                    "slug",
                    "name",
                    "kind",
                    "location",
                    "prerequisites",
                    "spoiler_level",
                    "references",
                    "verification_status",
                },
                {"slug", "name", "kind", "prerequisites", "references"},
                f"milestone {i}",
            )
            validate_condition(m["prerequisites"])
            _require(m.get("spoiler_level", "none") in ("none", "hint", "full"), "bad spoiler level")
            self._refs(m["references"], f"milestone {m['slug']}")
        self.battles = data.get("battles", [])
        for b in self.battles:
            _check_keys(
                b,
                {
                    "id",
                    "name",
                    "trainer_class",
                    "milestone",
                    "location",
                    "prize_money",
                    "party",
                    "references",
                    "verification_status",
                },
                {"id", "name", "trainer_class", "party", "references"},
                "battle",
            )
            _require(1 <= len(b["party"]) <= 6, f"battle {b['id']} party size")
            for member in b["party"]:
                _check_keys(
                    member,
                    {"pokemon", "level", "gender", "ability", "held_item", "moves"},
                    {"pokemon", "level"},
                    f"party member in {b['id']}",
                )
                _require(1 <= member["level"] <= 100, "party level range")
                moves = member.get("moves")
                _require(
                    moves is None or (isinstance(moves, list) and 1 <= len(moves) <= 4),
                    "party moves must be a list of 1-4 or null",
                )
            self._refs(b["references"], f"battle {b['id']}")
        self.acquisitions = data.get("acquisitions", [])
        for a in self.acquisitions:
            _check_keys(
                a,
                {
                    "id",
                    "pokemon",
                    "item",
                    "method",
                    "location",
                    "location_area",
                    "min_level",
                    "max_level",
                    "chance_percent",
                    "prerequisites",
                    "encounter_conditions",
                    "note",
                    "references",
                    "verification_status",
                    "availability",
                },
                {"id", "method", "prerequisites", "references"},
                "acquisition",
            )
            _require(("pokemon" in a) != ("item" in a), f"acquisition {a['id']} needs pokemon xor item")
            validate_condition(a["prerequisites"])
            validate_condition(a.get("encounter_conditions", {"op": "always"}))
            self._refs(a["references"], f"acquisition {a['id']}")
        self.shops = data.get("shops", [])
        for s in self.shops:
            _check_keys(
                s,
                {
                    "id",
                    "name",
                    "location",
                    "prerequisites",
                    "items",
                    "references",
                    "verification_status",
                },
                {"id", "name", "items", "references"},
                "shop",
            )
            validate_condition(s.get("prerequisites", {"op": "always"}))
            for entry in s["items"]:
                _check_keys(entry, {"item", "price", "prerequisites"}, {"item"}, f"shop {s['id']} item")
                validate_condition(entry.get("prerequisites", {"op": "always"}))
            self._refs(s["references"], f"shop {s['id']}")
        self.tutors = data.get("tutors", [])
        for t in self.tutors:
            _check_keys(
                t,
                {
                    "id",
                    "move",
                    "location",
                    "cost_item",
                    "cost_amount",
                    "prerequisites",
                    "references",
                    "verification_status",
                },
                {"id", "move", "references"},
                "tutor",
            )
            validate_condition(t.get("prerequisites", {"op": "always"}))
            self._refs(t["references"], f"tutor {t['id']}")
        self.evolution_overrides = data.get("evolution_overrides", [])
        for o in self.evolution_overrides:
            _check_keys(
                o,
                {"rule_id", "status", "reason", "references"},
                {"rule_id", "status", "reason", "references"},
                "evolution override",
            )
            _require(o["status"] in ("applies", "not-applicable", "unknown"), "bad override status")
            self._refs(o["references"], f"evolution override {o['rule_id']}")
        self.issues = data.get("issues", [])
        for issue in self.issues:
            _check_keys(
                issue,
                {"id", "feature", "subject", "kind", "description", "references"},
                {"id", "feature", "subject", "kind", "description"},
                "issue",
            )
            _require(issue["kind"] in ("missing", "disputed", "unverified"), "bad issue kind")
            if issue.get("references"):
                self._refs(issue["references"], f"issue {issue['id']}")

    def _refs(self, refs, where: str) -> None:
        _require(isinstance(refs, list) and refs, f"{where} needs at least one reference")
        for ref in refs:
            _require(ref in self.references, f"{where} cites unknown reference {ref}")

    def sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


def load_packs(directory: Path = DEFAULT_PACKS_DIR) -> dict[str, GamePack]:
    packs: dict[str, GamePack] = {}
    for path in sorted(Path(directory).glob("*/pack.json")):
        pack = GamePack(path)
        if pack.game in packs:
            raise ValueError(f"Duplicate pack for {pack.game}")
        if path.parent.name != pack.game:
            raise ValueError(f"Pack folder {path.parent.name} does not match game {pack.game}")
        packs[pack.game] = pack
    return packs
