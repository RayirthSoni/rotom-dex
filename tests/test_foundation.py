import contextlib
import gzip
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from src.cli import main
from src.database.connection import connect
from src.domain.conditions import evaluate_condition, validate_condition
from src.ingestion.emerald import (
    DEFAULT_CACHE,
    DEFAULT_PACK,
    historical,
    import_emerald,
    table_counts,
    validate_database,
)
from src.ingestion.sources.pokeapi import PokeAPICache
from src.repositories.pokemon import lookup_pokemon


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.seed = Path(cls.folder.name) / "seed.sqlite3"
        cls.summary = import_emerald(cls.seed)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.sqlite3"
        shutil.copyfile(self.seed, self.path)
        self.db = connect(self.path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def query(self, pokemon="ralts", game="emerald", level=None):
        return lookup_pokemon(self.db, pokemon, game, level)

    def test_repeat_import_is_logically_identical(self):
        before = "\n".join(self.db.iterdump())
        again = import_emerald(self.path)
        self.assertEqual(self.summary, again)
        self.assertEqual(before, "\n".join(self.db.iterdump()))

    def test_fresh_databases_are_reproducible(self):
        second = Path(self.tmp.name) / "second.sqlite3"
        self.assertEqual(self.summary, import_emerald(second))
        db = connect(second)
        try:
            self.assertEqual("\n".join(self.db.iterdump()), "\n".join(db.iterdump()))
        finally:
            db.close()

    def test_exact_version_and_unsupported_species(self):
        self.assertIsNone(self.query(game="ruby")["data"])
        self.assertEqual(self.query(game="ruby")["coverage_status"], "missing")
        self.assertIsNone(self.query("pikachu")["data"])
        with self.assertRaisesRegex(ValueError, "Unknown game"):
            self.query(game="omega-ruby")

    def test_adversarial_other_game_records_do_not_leak(self):
        evidence = self.db.execute("SELECT id FROM evidence LIMIT 1").fetchone()[0]
        self.db.execute("UPDATE game_versions SET support_status='sample' WHERE id=7")
        self.db.execute(
            "INSERT INTO pokemon_game_data VALUES (280,7,?,?)", ("unknown", evidence)
        )
        self.db.execute(
            "INSERT INTO move_game_data SELECT move_id,7,type_id,damage_class,99,accuracy,pp,effect,evidence_id FROM move_game_data WHERE move_id=93 AND game_id=9"
        )
        self.db.execute(
            "INSERT INTO learnsets VALUES (280,7,93,'level-up',99,NULL,?)", (evidence,)
        )
        self.db.execute(
            "INSERT INTO acquisitions VALUES ('test:ruby',7,280,NULL,NULL,'test-only',1,1,NULL,'unavailable',?,?,?)",
            ('{"op":"always"}', '{"op":"always"}', evidence),
        )
        ruby = self.query(game="ruby")["data"]
        emerald = self.query()["data"]
        self.assertEqual([r["level"] for r in ruby["learnset"]], [99])
        self.assertEqual(ruby["acquisition"][0]["availability"], "unavailable")
        self.assertFalse(any(r["level"] == 99 for r in emerald["learnset"]))
        self.assertFalse(
            any(r["method"] == "test-only" for r in emerald["acquisition"])
        )
        self.assertEqual(ruby["evolution"], [])
        self.assertTrue(emerald["evolution"])

    def test_historical_types_and_abilities(self):
        self.assertEqual(
            [r["type"] for r in self.query()["data"]["types"]], ["psychic"]
        )
        self.assertEqual(
            [r["ability"] for r in self.query("breloom")["data"]["abilities"]],
            ["effect-spore"],
        )
        self.assertEqual(
            [r["ability"] for r in self.query("zigzagoon")["data"]["abilities"]],
            ["pickup"],
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM pokemon_abilities WHERE is_hidden=1"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM types WHERE slug='fairy'").fetchone()[
                0
            ],
            0,
        )

    def test_historical_move_values_and_type_based_category(self):
        r = self.db.execute(
            "SELECT power,accuracy,damage_class FROM move_game_data WHERE move_id=33 AND game_id=9"
        ).fetchone()
        self.assertEqual(tuple(r), (35, 95, "physical"))
        r = self.db.execute(
            "SELECT power,damage_class FROM move_game_data WHERE move_id=348 AND game_id=9"
        ).fetchone()
        self.assertEqual(tuple(r), (70, "special"))
        r = self.db.execute(
            "SELECT power,pp FROM move_game_data WHERE move_id=202 AND game_id=9"
        ).fetchone()
        self.assertEqual(tuple(r), (60, 5))

    def test_historical_stat_boundaries(self):
        current = [
            {"stat_id": "2", "base_stat": "100"},
            {"stat_id": "3", "base_stat": "50"},
        ]
        past = [
            {"stat_id": "2", "base_stat": "80", "generation_id": "5"},
            {"stat_id": "2", "base_stat": "70", "generation_id": "3"},
            {"stat_id": "2", "base_stat": "60", "generation_id": "1"},
        ]
        self.assertEqual(
            historical(current, past, 3, ("stat_id",))[0]["base_stat"], "70"
        )
        self.assertEqual(
            historical(current, past, 4, ("stat_id",))[0]["base_stat"], "80"
        )
        self.assertEqual(
            historical(current, past, 6, ("stat_id",))[0]["base_stat"], "100"
        )

    def test_encounter_and_evolution_facts(self):
        acquisition = self.query()["data"]["acquisition"]
        self.assertEqual(len(acquisition), 1)
        self.assertEqual(
            (
                acquisition[0]["location"],
                acquisition[0]["min_level"],
                acquisition[0]["chance_percent"],
            ),
            ("hoenn-route-102", 4, 4),
        )
        self.assertEqual(acquisition[0]["availability"], "unknown")
        rule = self.query()["data"]["evolution"][0]
        self.assertEqual(
            (rule["to_pokemon"], rule["conditions"]),
            ("kirlia", {"op": "level_at_least", "value": 20}),
        )
        starter = self.query("treecko")["data"]["acquisition"][0]
        self.assertEqual((starter["method"], starter["min_level"]), ("gift", 5))
        self.assertIsNone(evaluate_condition(starter["prerequisites"], {}))

    def test_missing_encounters_do_not_mean_unavailable(self):
        result = self.query("gardevoir")
        self.assertEqual(
            {r["method"] for r in result["data"]["acquisition"]}, {"evolution"}
        )
        self.assertTrue(
            all(r["availability"] == "unknown" for r in result["data"]["acquisition"])
        )
        self.assertEqual(
            next(
                c["status"] for c in result["coverage"] if c["feature"] == "acquisition"
            ),
            "partial",
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM acquisitions WHERE availability='unavailable'"
            ).fetchone()[0],
            0,
        )

    def test_machine_relationships_and_level_filter(self):
        result = self.query(level=5)["data"]["learnset"]
        self.assertEqual(
            [r["move"] for r in result if r["method"] == "level-up"], ["growl"]
        )
        machines = [r for r in result if r["method"] == "machine"]
        self.assertTrue(machines)
        self.assertTrue(
            all(
                r["machine_item"] and r["machine_acquisition_coverage"] == "missing"
                for r in machines
            )
        )
        with self.assertRaises(ValueError):
            self.query(level=101)

    def test_item_effects_and_sourced_acquisition(self):
        r = self.db.execute(
            "SELECT effect FROM item_game_data WHERE game_id=9 AND item_id=135"
        ).fetchone()
        self.assertIn(
            "30 HP", r[0]
        )  # Gen III Sitrus effect, not modern quarter-max-HP.
        acquisitions = self.db.execute(
            "SELECT * FROM acquisitions WHERE game_id=9 AND item_id=132"
        ).fetchall()
        self.assertTrue(acquisitions)
        self.assertEqual({r["method"] for r in acquisitions}, {"capture-held-item"})
        self.assertEqual({r["chance_percent"] for r in acquisitions}, {5, 50})
        self.assertTrue(all(r["location_id"] is not None for r in acquisitions))
        self.assertEqual(
            self.db.execute(
                "SELECT status FROM coverage WHERE subject='item:17' AND feature='acquisition'"
            ).fetchone()[0],
            "missing",
        )

    def test_type_chart_and_natures(self):
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM type_effectiveness").fetchone()[0],
            289,
        )
        for attack in (8, 17):
            self.assertEqual(
                self.db.execute(
                    "SELECT damage_factor FROM type_effectiveness WHERE game_id=9 AND attack_type_id=? AND defense_type_id=9",
                    (attack,),
                ).fetchone()[0],
                50,
            )
        self.assertEqual(
            self.db.execute(
                "SELECT damage_factor FROM type_effectiveness WHERE game_id=9 AND attack_type_id=1 AND defense_type_id=8"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM natures").fetchone()[0], 25
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM natures WHERE increased_stat=decreased_stat"
            ).fetchone()[0],
            5,
        )

    def test_foreign_keys_and_constraints(self):
        evidence = self.db.execute("SELECT id FROM evidence LIMIT 1").fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO pokemon_types VALUES (280,7,1,14,?)", (evidence,)
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE evolution_rules SET to_form_id=999999 WHERE id=148")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "UPDATE acquisitions SET item_id=17 WHERE id='encounter:29603'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE pokemon_stats SET base_stat=-1 WHERE form_id=280")
        validate_database(self.db)

    def test_evidence_resolves_and_hashes_verify(self):
        result = self.query()
        self.assertTrue(result["evidence"])
        for evidence in result["evidence"]:
            self.assertTrue(evidence["sources"])
            for source in evidence["sources"]:
                self.assertEqual(len(source["sha256"]), 64)
                self.assertEqual(source["snapshot_id"], result["snapshot_id"])
                self.assertTrue(source["selector"])
        PokeAPICache(DEFAULT_CACHE)

    def test_conflicting_fact_rolls_back(self):
        self.db.execute(
            "UPDATE pokemon_stats SET base_stat=99 WHERE form_id=280 AND stat='hp'"
        )
        self.db.commit()
        before = "\n".join(self.db.iterdump())
        with self.assertRaisesRegex(ValueError, "Conflicting fact"):
            import_emerald(self.path)
        self.assertEqual(before, "\n".join(self.db.iterdump()))

    def test_different_pack_cannot_silently_replace_snapshot(self):
        pack = Path(self.tmp.name) / "pack.json"
        pack.write_text(DEFAULT_PACK.read_text() + "\n")
        before = table_counts(self.db)
        with self.assertRaisesRegex(ValueError, "Different source snapshot"):
            import_emerald(self.path, pack_path=pack)
        self.assertEqual(before, table_counts(self.db))

    def test_corrupt_cache_fails_before_database_creation(self):
        cache = Path(self.tmp.name) / "cache"
        shutil.copytree(DEFAULT_CACHE, cache)
        (cache / "versions.csv.gz").write_bytes(gzip.compress(b"corrupted"))
        destination = Path(self.tmp.name) / "corrupt.sqlite3"
        with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
            import_emerald(destination, cache_path=cache)
        self.assertFalse(destination.exists())

    def test_cli_commands_and_errors(self):
        for args in [
            ("check",),
            ("coverage",),
            ("query", "ralts", "--game", "emerald"),
        ]:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([*args, "--db", str(self.path)]), 0)
                self.assertIsNotNone(json.loads(output.getvalue()))
        absent = Path(self.tmp.name) / "absent.sqlite3"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                main(["query", "ralts", "--game", "emerald", "--db", str(absent)]), 1
            )
        self.assertFalse(absent.exists())


class ConditionsTests(unittest.TestCase):
    def test_three_valued_and_or(self):
        level = {"op": "level_at_least", "value": 20}
        unknown = {"op": "unknown", "reason": "unreviewed"}
        self.assertIsNone(
            evaluate_condition({"op": "and", "args": [level, unknown]}, {"level": 20})
        )
        self.assertFalse(
            evaluate_condition({"op": "and", "args": [level, unknown]}, {"level": 19})
        )
        self.assertTrue(
            evaluate_condition({"op": "or", "args": [level, unknown]}, {"level": 20})
        )
        self.assertIsNone(evaluate_condition(level, {}))

    def test_invalid_conditions_fail_closed(self):
        for value in (
            {"op": "and", "args": []},
            {"op": "arbitrary-script"},
            {"op": "level_at_least", "value": True},
            {"op": "always", "ignored": "x"},
        ):
            with self.assertRaises(ValueError):
                validate_condition(value)


if __name__ == "__main__":
    unittest.main()
