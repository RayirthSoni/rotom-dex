"""Exact-version isolation: paired games share group data but never encounter data."""


def test_paired_games_share_learnsets_but_not_encounters(db):
    def encounters(game):
        return set(
            db.execute(
                "SELECT form_id, location_area_id, method, min_level, max_level FROM acquisitions "
                "WHERE game_id=? AND method NOT IN ('evolution','breeding')",
                (game,),
            ).fetchall()
        )

    red, blue = encounters(1), encounters(2)
    assert red and blue and red != blue
    assert db.execute("SELECT count(*) FROM learnsets WHERE version_group_id=1").fetchone()[0] > 4000
    ruby, emerald = encounters(7), encounters(9)
    assert ruby != emerald
    assert (
        db.execute("SELECT count(*) FROM learnsets WHERE version_group_id=5").fetchone()[0]
        != db.execute("SELECT count(*) FROM learnsets WHERE version_group_id=6").fetchone()[0]
    )


def test_synthetic_other_game_rows_do_not_leak(db, client):
    evidence = db.execute("SELECT id FROM evidence LIMIT 1").fetchone()[0]
    db.execute(
        "INSERT INTO acquisitions (id, game_id, form_id, item_id, location_id, location_area_id, method, "
        "min_level, max_level, chance_percent, availability, prerequisites, encounter_conditions, "
        "verification_status, note, evidence_id) VALUES ('test:ruby',7,280,NULL,NULL,NULL,'test-only',1,1,NULL,"
        "'unavailable','{\"op\":\"always\"}','{\"op\":\"always\"}','source-derived','',?)",
        (evidence,),
    )
    db.commit()
    from rotom_dex.repositories.pokemon import pokemon_acquisition

    ruby = pokemon_acquisition(db, "ruby", "ralts")["data"]["routes"]
    emerald = pokemon_acquisition(db, "emerald", "ralts")["data"]["routes"]
    assert any(r["method"] == "test-only" and r["availability"] == "unavailable" for r in ruby)
    assert not any(r["method"] == "test-only" for r in emerald)


def test_generation_scoped_data_does_not_bleed(client):
    red = client.get("/api/pokemon/gengar?game=red").json()["data"]
    emerald = client.get("/api/pokemon/gengar?game=emerald").json()["data"]
    assert red["abilities"] == [] and red["abilities_note"]
    assert [a["ability"] for a in emerald["abilities"]] == ["levitate"]
    assert {s["stat"] for s in red["stats"]} == {"hp", "attack", "defense", "special", "speed"}
    assert len(emerald["stats"]) == 6
