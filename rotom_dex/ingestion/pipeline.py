"""Repeatable, transactional import of every selected main-series game.

Order: catalogs -> Pokémon -> moves -> items -> presence/learnsets -> evolution ->
encounters/derived acquisitions -> mechanics and packs -> coverage -> validation.
Foreign keys are deferred to commit time and checked explicitly before it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

from rotom_dex.db.connection import connect
from rotom_dex.db.migrations import migrate
from rotom_dex.domain import models as m
from rotom_dex.domain.conditions import validate_condition
from rotom_dex.ingestion.cache import PokeAPICache
from rotom_dex.ingestion.context import Context
from rotom_dex.ingestion.importers import (
    catalog,
    coverage,
    curated,
    encounters,
    evolution,
    items,
    learnsets,
    moves,
    pokemon,
)
from rotom_dex.ingestion.importers.catalog import expected_type_count
from rotom_dex.ingestion.packs import (
    DEFAULT_MECHANICS,
    DEFAULT_PACKS_DIR,
    MechanicsPack,
    load_packs,
)
from rotom_dex.ingestion.registry import DEFAULT_REGISTRY, Registry
from rotom_dex.ingestion.writer import Writer

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data/sources/pokeapi"
NORMALIZER = "rotom-normalizer-v2"
POKEAPI_LICENSE = "BSD-3-Clause (PokéAPI/pokeapi LICENSE.md, retained in data/sources/pokeapi)"


def import_games(
    db_path: str | Path,
    games: list[str] | None = None,
    *,
    cache_path: Path = DEFAULT_CACHE,
    registry_path: Path = DEFAULT_REGISTRY,
    mechanics_path: Path = DEFAULT_MECHANICS,
    packs_dir: Path = DEFAULT_PACKS_DIR,
) -> dict:
    cache = PokeAPICache(Path(cache_path))
    registry = Registry(cache, registry_path)
    selected = registry.select(games)
    mechanics = MechanicsPack(mechanics_path)
    packs = load_packs(packs_dir)
    unknown_packs = set(packs) - set(registry.games)
    if unknown_packs:
        raise ValueError(f"Game packs for unknown games: {sorted(unknown_packs)}")
    packs_sha = hashlib.sha256(
        registry.raw_bytes + mechanics.raw_bytes + b"".join(packs[k].raw_bytes for k in sorted(packs))
    ).hexdigest()
    snapshot_id = hashlib.sha256((cache.manifest_sha256() + packs_sha + NORMALIZER).encode()).hexdigest()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = connect(db_path)
    try:
        migrate(db)
        with db:
            db.execute("BEGIN")  # explicit, so the deferral below survives temp-table DDL
            db.execute("PRAGMA defer_foreign_keys = ON")
            existing = [r[0] for r in db.execute("SELECT id FROM snapshots")]
            if existing and existing != [snapshot_id]:
                raise ValueError("Different source snapshot; import into a new database and review the changes")
            w = Writer(db)
            created = (
                db.execute("SELECT created_at FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
                or [dt.datetime.now(dt.UTC).isoformat()]
            )[0]
            w.add(m.Snapshot(snapshot_id, created, cache.manifest_sha256(), packs_sha, NORMALIZER))
            _sources(w, cache, registry, mechanics, packs, snapshot_id)
            ctx = Context(cache, registry, selected, mechanics, packs, w, snapshot_id)
            for step in (
                catalog,
                pokemon,
                moves,
                items,
                learnsets,
                evolution,
                encounters,
                curated,
                coverage,
            ):
                step.run(ctx)
            w.flush()
            validate_database(db, ctx)
        return {
            "snapshot_id": snapshot_id,
            "games": [g.slug for g in selected],
            "counts": table_counts(db),
            "inserted": dict(sorted(w.inserted.items())),
        }
    finally:
        db.close()


def _sources(w: Writer, cache, registry, mechanics, packs, snapshot_id: str) -> None:
    for source in cache.manifest["sources"]:
        w.add(
            m.SourceReference(
                source["id"],
                "dataset",
                source["url"],
                source["retrieved_at"],
                source["sha256"],
                POKEAPI_LICENSE,
                "data/sources/pokeapi/" + source["path"],
                m.SOURCE_DERIVED,
                snapshot_id,
            )
        )
    w.add(
        m.SourceReference(
            "registry",
            "game-pack",
            "local:data/games/registry.json",
            json.loads(registry.raw_bytes)["reviewed_at"],
            hashlib.sha256(registry.raw_bytes).hexdigest(),
            "project",
            "data/games/registry.json",
            m.REFERENCE_REVIEWED,
            snapshot_id,
        )
    )
    w.add(
        m.SourceReference(
            "mechanics",
            "game-pack",
            "local:data/mechanics/version_groups.json",
            mechanics.reviewed_at,
            mechanics.sha256(),
            "project",
            "data/mechanics/version_groups.json",
            m.REFERENCE_REVIEWED,
            snapshot_id,
        )
    )
    w.add(
        m.SourceReference(
            "normalizer",
            "code",
            "local:rotom_dex/ingestion",
            NORMALIZER,
            hashlib.sha256(NORMALIZER.encode()).hexdigest(),
            "project",
            "rotom_dex/ingestion",
            "documented-normalization",
            snapshot_id,
        )
    )
    for key, url in mechanics.references.items():
        w.add(
            m.SourceReference(
                f"ref:mechanics:{key}",
                "reference",
                url,
                mechanics.reviewed_at,
                None,
                "CC BY-NC-SA 2.5 (Bulbapedia); read for verification, no prose copied",
                None,
                "read-for-verification",
                snapshot_id,
            )
        )
    for slug, pack in packs.items():
        w.add(
            m.SourceReference(
                f"pack:{slug}",
                "game-pack",
                f"local:data/game-packs/{slug}/pack.json",
                pack.reviewed_at,
                pack.sha256(),
                "project",
                f"data/game-packs/{slug}/pack.json",
                m.REFERENCE_REVIEWED,
                snapshot_id,
            )
        )
        for ref_id, ref in pack.references.items():
            w.add(
                m.SourceReference(
                    f"ref:{slug}:{ref_id}",
                    "reference",
                    ref["url"],
                    ref["accessed"],
                    None,
                    ref["license"],
                    None,
                    "read-for-verification",
                    snapshot_id,
                )
            )


def table_counts(db: sqlite3.Connection) -> dict[str, int]:
    tables = [
        r[0]
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


def validate_database(db: sqlite3.Connection, ctx: Context | None = None) -> None:
    """Integrity plus mechanics-aware invariants. Works without ctx for `rotom check`."""
    broken = db.execute("PRAGMA foreign_key_check").fetchmany(5)
    if broken:
        raise ValueError(f"Broken foreign keys: {[tuple(r) for r in broken]}")
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Database integrity check failed")
    if db.execute(
        "SELECT 1 FROM evidence e LEFT JOIN evidence_members em ON em.evidence_id=e.id "
        "WHERE em.evidence_id IS NULL LIMIT 1"
    ).fetchone():
        raise ValueError("Evidence without sources")
    for table, fields in (
        ("evolution_rules", ["conditions"]),
        ("acquisitions", ["prerequisites", "encounter_conditions"]),
        ("milestones", ["prerequisites"]),
        ("shops", ["prerequisites"]),
        ("shop_items", ["prerequisites"]),
        ("tutors", ["prerequisites"]),
    ):
        for row in db.execute(f"SELECT {','.join(fields)} FROM {table}"):
            for value in row:
                validate_condition(json.loads(value))
    for (gen,) in db.execute("SELECT DISTINCT generation_id FROM type_effectiveness"):
        count = db.execute("SELECT count(*) FROM type_effectiveness WHERE generation_id=?", (gen,)).fetchone()[0]
        if count != expected_type_count(gen) ** 2:
            raise ValueError(f"Type chart for generation {gen} incomplete ({count})")
        if (
            gen < 6
            and db.execute(
                "SELECT 1 FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE pt.generation_id=?"
                " AND t.slug='fairy' LIMIT 1",
                (gen,),
            ).fetchone()
        ):
            raise ValueError(f"Fairy typing leaked into generation {gen}")
        expected_stats = 5 if gen == 1 else 6
        bad = db.execute(
            "SELECT form_id, count(*) AS n FROM pokemon_stats WHERE generation_id=? GROUP BY form_id HAVING n!=?",
            (gen, expected_stats),
        ).fetchone()
        if bad:
            raise ValueError(f"Form {bad[0]} has {bad[1]} stats in generation {gen}")
        if gen < 3 and db.execute("SELECT 1 FROM pokemon_abilities WHERE generation_id=? LIMIT 1", (gen,)).fetchone():
            raise ValueError(f"Abilities recorded for generation {gen}")
        if (
            gen < 5
            and db.execute(
                "SELECT 1 FROM pokemon_abilities WHERE generation_id=? AND is_hidden=1 LIMIT 1",
                (gen,),
            ).fetchone()
        ):
            raise ValueError(f"Hidden abilities recorded for generation {gen}")
        if gen >= 3:
            orphan = db.execute(
                "SELECT s.form_id FROM pokemon_stats s WHERE s.generation_id=? AND NOT EXISTS (SELECT 1 FROM "
                "pokemon_abilities a WHERE a.form_id=s.form_id AND a.generation_id=s.generation_id) AND NOT "
                "EXISTS (SELECT 1 FROM data_issues d WHERE d.feature='abilities' AND d.subject='pokemon:' || "
                "s.form_id) LIMIT 1",
                (gen,),
            ).fetchone()
            if orphan:
                raise ValueError(f"Form {orphan[0]} has stats but no abilities or recorded gap in generation {gen}")
    missing = db.execute(
        "SELECT p.form_id, p.version_group_id FROM pokemon_version_groups p JOIN version_groups v "
        "ON v.id=p.version_group_id WHERE p.presence='present' AND NOT EXISTS (SELECT 1 FROM "
        "pokemon_stats s WHERE s.form_id=p.form_id AND s.generation_id=v.generation_id) LIMIT 1"
    ).fetchone()
    if missing:
        raise ValueError(f"Present form {missing[0]} lacks stats for version group {missing[1]}")
    if db.execute("SELECT 1 FROM acquisitions WHERE form_id IS NULL AND item_id IS NULL LIMIT 1").fetchone():
        raise ValueError("Acquisition without subject")
