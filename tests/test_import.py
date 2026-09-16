"""Idempotent, validated, conflict-safe imports and migrations."""

import gzip
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from rotom_dex.db.connection import connect
from rotom_dex.db.migrations import applied, migrate
from rotom_dex.ingestion.packs import DEFAULT_PACKS_DIR, GamePack, load_packs
from rotom_dex.ingestion.pipeline import DEFAULT_CACHE, import_games, table_counts, validate_database
from tests.conftest import GAMES, canonical, dump


def test_repeat_import_is_logically_identical(db, db_path, seed_summary):
    before = dump(db)
    again = import_games(db_path, GAMES)
    assert again["snapshot_id"] == seed_summary["snapshot_id"]
    assert again["counts"] == seed_summary["counts"]
    assert dump(db) == before


def test_incremental_import_matches_fresh_import(tmp_path):
    fresh = tmp_path / "fresh.sqlite3"
    incremental = tmp_path / "incremental.sqlite3"
    import_games(fresh, ["red", "yellow"])
    import_games(incremental, ["red"])
    import_games(incremental, ["yellow"])
    a, b = connect(fresh), connect(incremental)
    try:
        assert canonical(a) == canonical(b)  # row order differs, content must not
    finally:
        a.close()
        b.close()


def test_conflicting_fact_rolls_back(db, db_path):
    db.execute("UPDATE pokemon_stats SET base_stat=99 WHERE form_id=280 AND generation_id=3 AND stat='hp'")
    db.commit()
    before = dump(db)
    with pytest.raises(ValueError, match="Conflicting fact"):
        import_games(db_path, ["emerald"])
    assert dump(db) == before


def test_changed_pack_means_new_snapshot(db, db_path, tmp_path):
    packs = tmp_path / "packs"
    shutil.copytree(DEFAULT_PACKS_DIR, packs)
    pack = packs / "red" / "pack.json"
    pack.write_text(pack.read_text() + "\n")
    before = table_counts(db)
    with pytest.raises(ValueError, match="Different source snapshot"):
        import_games(db_path, ["red"], packs_dir=packs)
    assert table_counts(db) == before


def test_corrupt_cache_fails_before_database_creation(tmp_path):
    cache = tmp_path / "cache"
    shutil.copytree(DEFAULT_CACHE, cache)
    (cache / "versions.csv.gz").write_bytes(gzip.compress(b"corrupted"))
    target = tmp_path / "corrupt.sqlite3"
    with pytest.raises(ValueError, match="Source hash mismatch"):
        import_games(target, ["red"], cache_path=cache)
    assert not target.exists()


def test_game_selection_is_validated(tmp_path):
    with pytest.raises(ValueError, match="Unknown game"):
        import_games(tmp_path / "x.sqlite3", ["omega-red"])
    with pytest.raises(ValueError, match="excluded"):
        import_games(tmp_path / "y.sqlite3", ["colosseum"])
    with pytest.raises(ValueError, match="catalog"):
        import_games(tmp_path / "z.sqlite3", ["red-japan"])


def test_validation_passes_and_invariants_hold(db):
    validate_database(db)
    assert db.execute("SELECT count(*) FROM acquisitions WHERE availability='unavailable'").fetchone()[0] == 0
    assert (
        db.execute(
            "SELECT count(*) FROM evidence e LEFT JOIN evidence_members m ON m.evidence_id=e.id "
            "WHERE m.evidence_id IS NULL"
        ).fetchone()[0]
        == 0
    )


def test_migrations_apply_once_and_reject_legacy(tmp_path):
    fresh = connect(tmp_path / "m.sqlite3")
    assert migrate(fresh) == [1]
    assert migrate(fresh) == []
    assert applied(fresh) == [1]
    fresh.close()
    legacy = sqlite3.connect(tmp_path / "legacy.sqlite3")
    legacy.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    legacy.execute("INSERT INTO schema_version VALUES (1)")
    legacy.commit()
    with pytest.raises(ValueError, match="Legacy v1"):
        applied(legacy)
    legacy.close()


def test_pack_validation_is_strict(tmp_path):
    packs = load_packs()
    assert {"emerald", "red"} <= set(packs)
    broken = tmp_path / "pack.json"
    data = json.loads((DEFAULT_PACKS_DIR / "red" / "pack.json").read_text())
    data["surprise"] = 1
    broken.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown keys"):
        GamePack(broken)
    data.pop("surprise")
    data["battles"] = [{"id": "x", "name": "X", "trainer_class": "Leader", "party": [], "references": ["tm"]}]
    broken.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="party size"):
        GamePack(broken)
    data["battles"] = []
    data["milestones"] = [
        {"slug": "a", "name": "A", "kind": "story", "prerequisites": {"op": "nope"}, "references": ["tm"]}
    ]
    broken.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unsupported condition"):
        GamePack(broken)
    data["milestones"] = [
        {"slug": "a", "name": "A", "kind": "story", "prerequisites": {"op": "always"}, "references": ["missing-ref"]}
    ]
    broken.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown reference"):
        GamePack(broken)


def test_pack_with_unknown_slug_fails_import(tmp_path):
    packs = tmp_path / "packs"
    shutil.copytree(DEFAULT_PACKS_DIR, packs)
    pack = packs / "red" / "pack.json"
    data = json.loads(pack.read_text())
    data["acquisitions"] = [
        {
            "id": "bad",
            "pokemon": "not-a-pokemon",
            "method": "gift",
            "prerequisites": {"op": "always"},
            "references": ["tm"],
        }
    ]
    pack.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unknown pokemon slug"):
        import_games(tmp_path / "bad.sqlite3", ["red"], packs_dir=packs)
    assert (
        not Path(tmp_path / "bad.sqlite3").exists() or table_counts(connect(tmp_path / "bad.sqlite3"))["snapshots"] == 0
    )
