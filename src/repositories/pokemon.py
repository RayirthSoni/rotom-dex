"""Exact-version read queries. Coverage travels with every result."""

import json


def rows(db, sql, params=()):
    result = [dict(r) for r in db.execute(sql, params)]
    for row in result:
        for field in ("prerequisites", "encounter_conditions", "conditions"):
            if field in row:
                row[field] = json.loads(row[field])
    return result


def lookup_pokemon(db, name, game, level=None):
    if level is not None and not 1 <= level <= 100:
        raise ValueError("Level must be between 1 and 100")
    version = db.execute(
        "SELECT * FROM game_versions WHERE slug=?", (game.lower(),)
    ).fetchone()
    if version is None:
        raise ValueError(
            f"Unknown game version: {game}; imported catalog: emerald, ruby"
        )
    pokemon = db.execute(
        "SELECT * FROM pokemon_forms WHERE slug=? OR CAST(id AS TEXT)=?",
        (name.lower(), name),
    ).fetchone()
    gid = version["id"]
    snapshot = db.execute("SELECT id FROM snapshots").fetchone()
    if snapshot is None:
        raise ValueError("Database has no published snapshot; run import first")
    result = {
        "game_version": version["slug"],
        "version_group": version["version_group"],
        "snapshot_id": snapshot[0],
        "coverage_status": "missing",
        "data": None,
        "coverage": [],
        "evidence": [],
        "assumptions": [],
    }
    if version["support_status"] == "unsupported":
        result["assumptions"] = [
            "This version is not covered. No facts from another version are substituted."
        ]
        result["coverage"] = rows(
            db,
            "SELECT * FROM coverage WHERE game_id=? ORDER BY subject,feature",
            (gid,),
        )
    elif (
        pokemon is None
        or not db.execute(
            "SELECT 1 FROM pokemon_game_data WHERE form_id=? AND game_id=?",
            (pokemon["id"], gid),
        ).fetchone()
    ):
        result["assumptions"] = [
            "Pokémon is outside the imported sample; this does not mean unavailable in the game."
        ]
    else:
        pid = pokemon["id"]
        params = (pid, gid)
        result["data"] = {
            "pokemon": dict(pokemon),
            "game_data": rows(
                db,
                "SELECT * FROM pokemon_game_data WHERE form_id=? AND game_id=?",
                params,
            )[0],
            "types": rows(
                db,
                "SELECT pt.*,t.slug AS type FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE form_id=? AND game_id=? ORDER BY slot",
                params,
            ),
            "stats": rows(
                db,
                "SELECT stat,base_stat,evidence_id FROM pokemon_stats WHERE form_id=? AND game_id=? ORDER BY stat",
                params,
            ),
            "abilities": rows(
                db,
                "SELECT pa.*,a.slug AS ability FROM pokemon_abilities pa JOIN abilities a ON a.id=pa.ability_id WHERE form_id=? AND game_id=? ORDER BY slot",
                params,
            ),
            "acquisition": rows(
                db,
                """SELECT a.*,l.slug AS location,l.area FROM acquisitions a
                LEFT JOIN locations l ON l.id=a.location_id AND l.game_id=a.game_id
                WHERE form_id=? AND a.game_id=? ORDER BY a.id""",
                params,
            ),
            "evolution": rows(
                db,
                """SELECT e.*,f.slug AS from_pokemon,t.slug AS to_pokemon
                FROM evolution_rules e JOIN pokemon_forms f ON f.id=e.from_form_id JOIN pokemon_forms t ON t.id=e.to_form_id
                WHERE e.game_id=? AND (from_form_id=? OR to_form_id=?) ORDER BY e.id""",
                (gid, pid, pid),
            ),
            "learnset": rows(
                db,
                """SELECT l.*,m.slug AS move,i.slug AS machine_item,
                mg.type_id,mg.damage_class,mg.power,mg.accuracy,mg.pp,mg.effect,mg.evidence_id AS move_evidence_id,
                c.status AS machine_acquisition_coverage FROM learnsets l JOIN moves m ON m.id=l.move_id
                JOIN move_game_data mg ON mg.move_id=l.move_id AND mg.game_id=l.game_id
                LEFT JOIN items i ON i.id=l.machine_item_id
                LEFT JOIN coverage c ON c.game_id=l.game_id AND c.subject='item:' || l.machine_item_id AND c.feature='acquisition'
                WHERE l.form_id=? AND l.game_id=? AND (? IS NULL OR l.method!='level-up' OR l.level<=?)
                ORDER BY l.method,l.level,m.slug""",
                (pid, gid, level, level),
            ),
        }
        result["coverage"] = rows(
            db,
            "SELECT * FROM coverage WHERE game_id=? AND subject IN (?,?) ORDER BY subject,feature",
            (gid, f"pokemon:{pid}", "*"),
        )
        result["coverage_status"] = "partial"
        result["assumptions"] = [
            "Acquisition availability is unknown without reviewed progression gates and playthrough context.",
            "Learnsets describe eligibility. Machine, tutor and breeding access are not established.",
            "Level filtering applies only to level-up moves; other learning methods remain visible.",
            "Evolution includes immediate incoming and outgoing rules, not a recursively expanded chain.",
            "Facts are source-derived. Complete coverage refers to this sample and source, not independent ROM validation.",
        ]
    ids = set()

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("evidence_id") and item:
                    ids.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(result)
    for eid in sorted(ids):
        result["evidence"].append(
            {
                "id": eid,
                "sources": rows(
                    db,
                    """SELECT s.*,em.selector FROM evidence_members em
            JOIN sources s ON s.id=em.source_id WHERE em.evidence_id=? ORDER BY s.id,em.selector""",
                    (eid,),
                ),
            }
        )
    return result
