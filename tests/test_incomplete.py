"""Incomplete data stays visible as missing/unknown, never as unavailable."""

import json


def test_game_without_source_encounters(db, client):
    assert (
        db.execute(
            "SELECT count(*) FROM acquisitions WHERE game_id=40 AND method NOT IN ('evolution','breeding')"
        ).fetchone()[0]
        == 0
    )
    status = db.execute("SELECT status FROM coverage WHERE game_id=40 AND feature='encounters'").fetchone()[0]
    assert status == "missing"
    assert db.execute("SELECT count(*) FROM data_issues WHERE id='source:scarlet:encounters'").fetchone()[0] == 1
    body = client.get("/api/pokemon/sprigatito/acquisition?game=scarlet").json()
    assert body["coverage_status"] in ("partial", "missing")
    assert all(r["availability"] == "unknown" for r in body["data"]["routes"])
    assert {c["status"] for c in body["coverage"] if c["feature"] == "encounters"} == {"missing"}


def test_null_values_are_preserved(db):
    row = db.execute("SELECT power, accuracy FROM move_game_data WHERE move_id=69 AND version_group_id=1").fetchone()
    assert row[0] is None  # Seismic Toss has no fixed power
    row = db.execute("SELECT accuracy FROM move_game_data WHERE move_id=14 AND version_group_id=6").fetchone()
    assert row[0] is None  # Swords Dance has no accuracy check
    assert (
        db.execute("SELECT price_provenance FROM item_game_data WHERE item_id=4 AND version_group_id=6").fetchone()[0]
        == "default-cost"
    )
    assert db.execute("SELECT count(*) FROM item_game_data WHERE price_provenance='version-group'").fetchone()[0] > 0


def test_absent_pokemon_and_unimported_games(client):
    body = client.get("/api/pokemon/ralts?game=red").json()
    assert body["data"] is None and body["coverage_status"] == "missing"
    assert "does not by itself prove" in body["assumptions"][0]
    body = client.get("/api/pokemon/ralts?game=sun").json()
    assert body["data"] is None and "not imported into this database" in body["assumptions"][0]
    body = client.get("/api/pokemon/ralts?game=colosseum").json()
    assert body["data"] is None and "excluded" in body["assumptions"][0]
    body = client.get("/api/pokemon/pikachu?game=red-japan").json()
    assert body["data"] is None and "catalog" in body["assumptions"][0]
    body = client.get("/api/natures?game=red").json()
    assert body["data"] is None and "absent as a mechanic" in body["assumptions"][0]


def test_unknown_leaves_survive_round_trip(db):
    conditions = [json.loads(r[0]) for r in db.execute("SELECT conditions FROM evolution_rules")]
    assert any(c.get("op") == "unknown" or any(a.get("op") == "unknown" for a in c.get("args", [])) for c in conditions)
    starter = db.execute("SELECT prerequisites FROM acquisitions WHERE id='pack:9:starter-treecko'").fetchone()[0]
    assert "Only one of" in starter
