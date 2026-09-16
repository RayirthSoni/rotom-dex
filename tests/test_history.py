"""Historical mechanics: values must match the generation/version group of the exact game."""


def factor(db, gen, attack, defense):
    return db.execute(
        "SELECT t.damage_factor FROM type_effectiveness t JOIN types a ON a.id=t.attack_type_id "
        "JOIN types d ON d.id=t.defense_type_id WHERE t.generation_id=? AND a.slug=? AND d.slug=?",
        (gen, attack, defense),
    ).fetchone()[0]


def test_generation_one_type_chart_and_types(db):
    assert db.execute("SELECT count(*) FROM types WHERE generation_id<=1").fetchone()[0] == 15
    assert db.execute("SELECT count(*) FROM type_effectiveness WHERE generation_id=1").fetchone()[0] == 225
    assert factor(db, 1, "ghost", "psychic") == 0
    assert factor(db, 1, "bug", "poison") == 200
    assert factor(db, 1, "poison", "bug") == 200
    assert factor(db, 1, "ice", "fire") == 100
    assert factor(db, 3, "ghost", "psychic") == 200
    assert factor(db, 3, "ice", "fire") == 50


def test_steel_and_fairy_history(db):
    assert factor(db, 3, "ghost", "steel") == 50
    assert factor(db, 3, "dark", "steel") == 50
    assert factor(db, 6, "ghost", "steel") == 100
    assert factor(db, 6, "dark", "steel") == 100
    assert db.execute("SELECT count(*) FROM type_effectiveness WHERE generation_id=3").fetchone()[0] == 289
    assert db.execute("SELECT count(*) FROM type_effectiveness WHERE generation_id=6").fetchone()[0] == 324
    assert factor(db, 6, "fairy", "dragon") == 200
    assert db.execute("SELECT count(*) FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE t.slug='fairy' AND pt.generation_id<6").fetchone()[0] == 0


def test_ralts_typing_by_generation(db):
    def types(gen):
        return [
            r[0]
            for r in db.execute(
                "SELECT t.slug FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE pt.form_id=280 AND pt.generation_id=? ORDER BY pt.slot",
                (gen,),
            )
        ]

    assert types(3) == ["psychic"]
    assert types(4) == ["psychic"]
    assert types(6) == ["psychic", "fairy"]


def test_generation_one_stats_and_absent_mechanics(db):
    stats = dict(db.execute("SELECT stat, base_stat FROM pokemon_stats WHERE form_id=1 AND generation_id=1"))
    assert stats == {"hp": 45, "attack": 49, "defense": 49, "special": 65, "speed": 45}
    modern = dict(db.execute("SELECT stat, base_stat FROM pokemon_stats WHERE form_id=1 AND generation_id=3"))
    assert modern["special-attack"] == 65 and modern["special-defense"] == 65 and "special" not in modern
    assert db.execute("SELECT count(*) FROM pokemon_abilities WHERE generation_id=1").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM pokemon_held_items WHERE game_id=1").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM acquisitions WHERE game_id=1 AND method='breeding'").fetchone()[0] == 0
    mechanics = dict(db.execute("SELECT key, value FROM game_mechanics WHERE version_group_id=1"))
    assert mechanics["abilities"] == 0 and mechanics["natures"] == 0 and mechanics["tm_reusable"] == 0


def test_move_history_rewind_and_damage_class(db):
    def move(mid, vg):
        return db.execute(
            "SELECT t.slug, damage_class, power, accuracy, pp FROM move_game_data m JOIN types t ON t.id=m.type_id WHERE move_id=? AND version_group_id=?",
            (mid, vg),
        ).fetchone()

    assert tuple(move(44, 1)) == ("normal", "physical", 60, 100, 25)  # Bite, Generation I
    assert tuple(move(44, 6)) == ("dark", "special", 60, 100, 25)  # Dark and type-based special in Gen III
    assert tuple(move(44, 9)) == ("dark", "physical", 60, 100, 25)  # Physical after the Gen IV split
    assert tuple(move(33, 6))[2:4] == (35, 95)  # Tackle in Emerald
    assert tuple(move(33, 15))[2:4] == (50, 100)  # Tackle in X/Y
    assert tuple(move(348, 6))[1:3] == ("special", 70)  # Leaf Blade in Emerald
    assert tuple(move(348, 9))[1:3] == ("physical", 90)  # Leaf Blade in Platinum
    assert move(16, 1)[0] == "normal"  # Gust in Generation I


def test_hidden_abilities_only_from_generation_five(db):
    for gen in (3, 4):
        assert db.execute("SELECT count(*) FROM pokemon_abilities WHERE generation_id=? AND is_hidden=1", (gen,)).fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM pokemon_abilities WHERE generation_id=6 AND is_hidden=1").fetchone()[0] > 0
    assert [r[0] for r in db.execute("SELECT a.slug FROM pokemon_abilities pa JOIN abilities a ON a.id=pa.ability_id WHERE pa.form_id=286 AND pa.generation_id=3")] == [
        "effect-spore"
    ]
    assert [r[0] for r in db.execute("SELECT a.slug FROM pokemon_abilities pa JOIN abilities a ON a.id=pa.ability_id WHERE pa.form_id=263 AND pa.generation_id=3")] == ["pickup"]


def test_item_text_is_version_group_specific(db):
    text = db.execute("SELECT flavor_text FROM item_game_data WHERE item_id=135 AND version_group_id=6").fetchone()[0]
    assert "30 HP" in text
    later = db.execute("SELECT flavor_text FROM item_game_data WHERE item_id=135 AND version_group_id=9").fetchone()[0]
    assert "30 HP" not in later


def test_gallade_rule_applicability_by_game(db):
    status = dict(db.execute("SELECT version_group_id, status FROM evolution_applicability WHERE rule_id=243"))
    assert status[6] == "not-applicable"  # Emerald: Gallade absent
    assert status[9] == "applies"  # Platinum
    assert status[15] == "applies"  # X
    assert status[1] == "not-applicable"
