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

from rotom_dex.domain.conditions import leaves, validate_condition

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MECHANICS = ROOT / "data/mechanics/version_groups.json"
DEFAULT_ABILITY_EFFECTS = ROOT / "data/mechanics/ability_type_effects.json"
DEFAULT_PACKS_DIR = ROOT / "data/game-packs"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# `badge`, `elite-four` and `champion` are the main-story checkpoints coverage counts rosters
# against; the rest are ordinary steps.
MILESTONE_KINDS = ("story", "badge", "elite-four", "champion", "hm", "event")

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


APPLIES_TO = ("type", "super-effective", "non-super-effective")
DAMAGE_FACTORS = (0, 25, 50, 75, 125, 200)


class AbilityTypeEffectsPack:
    """Reviewed type-based defensive modifiers granted by abilities.

    Deliberately narrow: an entry may only scale damage from one attacking type, or from
    super-effective / non-super-effective moves as a class. Anything conditional on a move flag, the
    weather, the field or the holder's HP belongs in `excluded`, where it becomes a data issue.
    """

    def __init__(self, path: Path = DEFAULT_ABILITY_EFFECTS):
        self.path = Path(path)
        self.raw_bytes = self.path.read_bytes()
        data = json.loads(self.raw_bytes)
        _check_keys(
            data,
            {"reviewed_at", "review_status", "policy", "kinds", "damage_factors", "references", "abilities", "excluded"},
            {"reviewed_at", "references", "abilities"},
            "ability type effects pack",
        )
        for ref_id, ref in data["references"].items():
            _check_keys(ref, {"url", "accessed", "license", "note"}, {"url", "accessed", "license"}, f"reference {ref_id}")
            _require(str(ref["url"]).startswith("http"), f"reference {ref_id} needs an http url")
        for slug, entry in data["abilities"].items():
            where = f"ability {slug}"
            _require(bool(SLUG.match(slug)), f"{where} is not a slug")
            _check_keys(entry, {"since_generation", "references", "effects"}, {"since_generation", "references", "effects"}, where)
            _require(type(entry["since_generation"]) is int and 1 <= entry["since_generation"] <= 9, f"{where} needs a generation 1-9")
            _require(bool(entry["references"]), f"{where} cites no reference")
            for ref in entry["references"]:
                _require(ref in data["references"], f"{where} cites unknown reference {ref}")
            _require(bool(entry["effects"]), f"{where} has no effects; use `excluded` instead")
            seen = set()
            for effect in entry["effects"]:
                _check_keys(effect, {"applies_to", "type", "damage_factor", "note"}, {"applies_to", "damage_factor"}, f"{where} effect")
                _require(effect["applies_to"] in APPLIES_TO, f"{where} has unknown applies_to {effect['applies_to']!r}")
                _require(effect["damage_factor"] in DAMAGE_FACTORS, f"{where} has unsupported damage factor {effect['damage_factor']!r}")
                typed = effect["applies_to"] == "type"
                _require(typed == ("type" in effect), f"{where}: applies_to 'type' requires a type, the others forbid one")
                key = (effect["applies_to"], effect.get("type"))
                _require(key not in seen, f"{where} repeats {key}")
                seen.add(key)
        for item in data.get("excluded", []):
            _check_keys(item, {"ability", "reason"}, {"ability", "reason"}, "excluded entry")
            _require(item["ability"] not in data["abilities"], f"{item['ability']} is both modelled and excluded")
        self.data = data
        self.reviewed_at = data["reviewed_at"]
        self.review_status = data.get("review_status", "reference-reviewed")
        self.references: dict[str, dict] = data["references"]
        self.abilities: dict[str, dict] = data["abilities"]
        self.excluded: list[dict] = data.get("excluded", [])

    def sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


class GamePack:
    ALLOWED = {
        "format_version",
        "game",
        "reviewed_at",
        "policy",
        "references",
        "mechanics",
        "main_story_end",
        "milestones",
        "location_gates",
        "method_gates",
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
            _require(m["kind"] in MILESTONE_KINDS, f"milestone {m['slug']} has unknown kind {m['kind']!r}; choose from {list(MILESTONE_KINDS)}")
            self._refs(m["references"], f"milestone {m['slug']}")
        slugs = [m["slug"] for m in self.milestones]
        _require(len(slugs) == len(set(slugs)), "duplicate milestone slug")
        # A milestone leaf naming something this pack does not define is an authoring error, not a
        # weaker claim: it would silently evaluate to unknown forever.
        for ms in self.milestones:
            self._milestones_exist(ms["prerequisites"], slugs, f"milestone {ms['slug']}")

        # The declared end of the reviewed main story. Its presence is what lets coverage report
        # `progression: complete`; the connectivity check that earns it lives in the importer, which
        # is the only place that can see whether every prerequisite resolves.
        self.main_story_end: str | None = data.get("main_story_end")
        if self.main_story_end is not None:
            _require(self.main_story_end in slugs, f"main_story_end {self.main_story_end!r} is not a milestone in this pack")

        # Reviewed access conditions for a location. A gate replaces the blanket `unknown` leaf that
        # every source encounter otherwise carries, so an encounter in a reviewed location can be
        # settled by the player's recorded progress instead of staying permanently unknown.
        self.location_gates = data.get("location_gates", [])
        gated = set()
        for gate in self.location_gates:
            _check_keys(
                gate,
                {"location", "prerequisites", "references", "verification_status", "note"},
                {"location", "prerequisites", "references"},
                "location gate",
            )
            _require(bool(SLUG.match(gate["location"])), f"location gate {gate['location']!r} is not a slug")
            _require(gate["location"] not in gated, f"duplicate location gate for {gate['location']}")
            gated.add(gate["location"])
            validate_condition(gate["prerequisites"])
            self._milestones_exist(gate["prerequisites"], slugs, f"location gate {gate['location']}")
            self._refs(gate["references"], f"location gate {gate['location']}")
        # What an encounter *method* costs on top of reaching the location: Surf needs the HM,
        # a rod needs the rod. Without this a Surf slot on an early route would read as reachable
        # the moment the route does, which is exactly the kind of over-claim this project forbids.
        self.method_gates = data.get("method_gates", [])
        methods = set()
        for entry in self.method_gates:
            _check_keys(
                entry,
                {"method", "prerequisites", "references", "note"},
                {"method", "prerequisites", "references"},
                "method gate",
            )
            _require(entry["method"] not in methods, f"duplicate method gate for {entry['method']}")
            methods.add(entry["method"])
            validate_condition(entry["prerequisites"])
            self._milestones_exist(entry["prerequisites"], slugs, f"method gate {entry['method']}")
            self._refs(entry["references"], f"method gate {entry['method']}")
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
            self._milestones_exist(a["prerequisites"], slugs, f"acquisition {a['id']}")
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
            self._milestones_exist(s.get("prerequisites", {"op": "always"}), slugs, f"shop {s['id']}")
            for entry in s["items"]:
                _check_keys(entry, {"item", "price", "prerequisites"}, {"item"}, f"shop {s['id']} item")
                validate_condition(entry.get("prerequisites", {"op": "always"}))
                self._milestones_exist(entry.get("prerequisites", {"op": "always"}), slugs, f"shop {s['id']} item {entry['item']}")
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
            self._milestones_exist(t.get("prerequisites", {"op": "always"}), slugs, f"tutor {t['id']}")
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

    def _milestones_exist(self, condition: dict, slugs: list[str], where: str) -> None:
        for leaf in leaves(condition):
            if leaf["op"] == "milestone":
                _require(leaf["value"] in slugs, f"{where} cites unknown milestone {leaf['value']!r}")

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
