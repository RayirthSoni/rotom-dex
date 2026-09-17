"""Reviewed prose facts with explicit applicability and reproducible publication.

This sidecar never mutates a published game database. Its hash travels with returned records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rotom_dex.errors import SemanticError

ROOT = Path(__file__).resolve().parents[2] / "data" / "knowledge"
CAPABILITIES = (
    "pokemon-acquisition",
    "item-acquisition",
    "shops",
    "machines",
    "tutors",
    "evolution",
    "breeding",
    "transfer-events",
    "progression",
    "bosses",
    "postgame",
    "mechanics",
    "story-advice",
    "competitive",
)


class Applicability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    games: list[str] = Field(default_factory=list)
    version_groups: list[str] = Field(default_factory=list)
    generations: list[int] = Field(default_factory=list)
    invariant: bool = False
    dlc: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    subject: str
    capability: str
    claim: str = Field(max_length=1000)
    applicability: Applicability
    keywords: list[str]
    sources: list[str] = Field(min_length=1)
    source_note: str
    reviewed_at: str
    review_status: Literal["source-reviewed", "gameplay-verified"]
    spoiler: Literal["none", "story", "postgame"]
    availability: Literal["available", "unavailable", "unknown"] = "unknown"


def load(path: Path | None = None):
    path = path or ROOT / "facts.json"
    raw = path.read_bytes()
    records = [Fact.model_validate(row) for row in json.loads(raw)]
    ids = set()
    for r in records:
        if r.id in ids or r.capability not in CAPABILITIES:
            raise SemanticError("Duplicate fact ID or unknown capability")
        ids.add(r.id)
        a = r.applicability
        if sum(bool(x) for x in (a.games, a.version_groups, a.generations, a.invariant)) != 1:
            raise SemanticError(f"{r.id}: exactly one applicability level is required")
        if not all(url.startswith("https://") for url in r.sources):
            raise SemanticError(f"{r.id}: source URLs must be HTTPS")
    return records, hashlib.sha256(raw).hexdigest()


def search(scope, query: str, spoiler="full", dlc=()):
    records, snapshot = load()
    matches = []
    normal = re.sub(r"[^a-z0-9 ]", " ", query.lower().replace("-", " "))
    normal = " ".join(normal.split())
    for r in records:
        a = r.applicability
        if a.dlc and not set(a.dlc).issubset(dlc):
            continue
        rank = 3 if scope.slug in a.games else 2 if scope.version_group in a.version_groups else 1 if scope.generation_id in a.generations else 0 if a.invariant else -1
        if rank < 0 or (spoiler != "full" and r.spoiler != "none"):
            continue
        if not any(" ".join(re.sub(r"[^a-z0-9 ]", " ", k.lower().replace("-", " ")).split()) in normal for k in r.keywords):
            continue
        matches.append((rank, r))
    # Higher specificity overrides generic facts for the same subject/capability.
    result = []
    for rank, r in matches:
        if any(other.subject == r.subject and other.capability == r.capability and other_rank > rank for other_rank, other in matches):
            continue
        result.append({**r.model_dump(), "game": scope.slug, "snapshot": snapshot})
    return result[:8]


def audit(db, path: Path | None = None):
    records, snapshot = load(path)
    games = [
        dict(r)
        for r in db.execute(
            "SELECT g.slug,g.version_group_id,vg.slug AS version_group,vg.generation_id FROM game_versions g "
            "JOIN version_groups vg ON vg.id=g.version_group_id WHERE g.is_main_series=1"
        )
    ]
    game_ids = {g["slug"] for g in games}
    group_ids = {g["version_group"] for g in games}
    generations = {g["generation_id"] for g in games}
    errors = []
    conflicts = []
    for r in records:
        a = r.applicability
        if set(a.games) - game_ids or set(a.version_groups) - group_ids or set(a.generations) - generations:
            errors.append(f"{r.id}: unknown applicability")
    for i, r in enumerate(records):
        for other in records[i + 1 :]:
            if r.subject == other.subject and r.capability == other.capability and r.applicability == other.applicability and r.claim != other.claim:
                conflicts.append([r.id, other.id])
    inventory = []
    for g in games:
        applicable = [
            r
            for r in records
            if g["slug"] in r.applicability.games
            or g["version_group"] in r.applicability.version_groups
            or g["generation_id"] in r.applicability.generations
            or r.applicability.invariant
        ]
        inventory.append(
            {
                "game": g["slug"],
                "deep_support": False,
                "reviewed_facts": len(applicable),
                "capabilities": {
                    c: {"reviewed_facts": sum(r.capability == c for r in applicable), "inventory_review_complete": False, "question_suite_review_complete": False}
                    for c in CAPABILITIES
                },
            }
        )
    return {
        "snapshot": snapshot,
        "errors": errors,
        "conflicts": conflicts,
        "source_inventory": sorted({u for r in records for u in r.sources}),
        "games": inventory,
        "note": "Fact counts are not deep-support certification. Complete capability inventories and human-reviewed question suites are required.",
    }


def publish(db, target: Path, path: Path | None = None):
    report = audit(db, path)
    if report["errors"] or report["conflicts"]:
        raise SemanticError("Content has applicability errors or unresolved conflicts; publication refused.")
    target.mkdir(parents=True, exist_ok=True)
    destination = target / f"knowledge-{report['snapshot']}.json"
    if destination.exists():
        raise SemanticError("Snapshot already exists; published snapshots are immutable.")
    destination.write_bytes((path or ROOT / "facts.json").read_bytes())
    return {"snapshot": report["snapshot"], "path": str(destination)}
