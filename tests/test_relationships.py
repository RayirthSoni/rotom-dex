"""Cross-table relationships: machines, evolution chains, held items, breeding, packs."""


def test_machine_counts_and_links(db):
    counts = {(vg, kind): n for vg, kind, n in db.execute("SELECT version_group_id, kind, count(*) FROM machines GROUP BY 1, 2")}
    assert counts[(1, "tm")] == 50 and counts[(1, "hm")] == 5
    assert counts[(6, "tm")] == 50 and counts[(6, "hm")] == 8
    assert counts[(9, "tm")] == 92 and counts[(9, "hm")] == 8
    bad = db.execute("""SELECT count(*) FROM machines mc JOIN items i ON i.id=mc.item_id
                        WHERE i.slug != mc.kind || printf('%02d', mc.machine_number)""").fetchone()[0]
    assert bad == 0
    tm39 = db.execute("SELECT m.slug FROM machines mc JOIN moves m ON m.id=mc.move_id WHERE mc.version_group_id=6 AND mc.kind='tm' AND mc.machine_number=39").fetchone()[0]
    assert tm39 == "rock-tomb"


def test_evolution_chain_and_derived_routes(db):
    rules = db.execute(
        """SELECT f.slug, t.slug, a.status FROM evolution_rules r
           JOIN pokemon_forms f ON f.id=r.from_form_id JOIN pokemon_forms t ON t.id=r.to_form_id
           JOIN evolution_applicability a ON a.rule_id=r.id AND a.version_group_id=6
           WHERE f.slug IN ('ralts','kirlia') ORDER BY r.id"""
    ).fetchall()
    assert [tuple(r) for r in rules] == [
        ("ralts", "kirlia", "applies"),
        ("kirlia", "gardevoir", "applies"),
        ("kirlia", "gallade", "not-applicable"),
    ]
    routes = {r[0] for r in db.execute("SELECT method FROM acquisitions WHERE game_id=9 AND form_id=282")}
    assert routes == {"evolution"}
    assert db.execute("SELECT count(*) FROM acquisitions WHERE id='evolution:14:243'").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM acquisitions WHERE id='evolution:9:243'").fetchone()[0] == 0


def test_held_items_and_breeding_follow_mechanics(db):
    assert db.execute("SELECT count(*) FROM pokemon_held_items WHERE game_id=9").fetchone()[0] > 0
    assert db.execute("SELECT count(*) FROM pokemon_held_items WHERE game_id=1").fetchone()[0] == 0
    ralts = db.execute("SELECT prerequisites FROM acquisitions WHERE id='breeding:9:280'").fetchone()[0]
    assert "gardevoir" in ralts and "unknown" in ralts
    assert db.execute("SELECT count(*) FROM acquisitions WHERE game_id=9 AND method='breeding' AND form_id=150").fetchone()[0] == 0


def test_curated_pack_relationships(db):
    party = db.execute(
        """SELECT f.slug, tp.level, i.slug, tp.moves FROM trainer_party tp
           JOIN pokemon_forms f ON f.id=tp.form_id LEFT JOIN items i ON i.id=tp.held_item_id
           WHERE tp.battle_id='emerald:roxanne' ORDER BY tp.slot"""
    ).fetchall()
    assert [tuple(r)[:3] for r in party] == [
        ("geodude", 12, None),
        ("geodude", 12, None),
        ("nosepass", 15, "oran-berry"),
    ]
    milestones = [r[0] for r in db.execute("SELECT slug FROM milestones WHERE game_id=9 ORDER BY ord")]
    assert milestones[0] == "littleroot-arrival" and milestones[-1] == "stone-badge"
    shop = db.execute("SELECT count(*) FROM shop_items WHERE shop_id='emerald:rustboro-poke-mart'").fetchone()[0]
    assert shop == 12
    tm39 = db.execute("SELECT prerequisites FROM acquisitions WHERE id='pack:9:tm39-roxanne'").fetchone()[0]
    assert "stone-badge" in tm39
