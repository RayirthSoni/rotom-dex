"""Deterministic type matchups from the generation-scoped chart."""

from __future__ import annotations

import sqlite3


def type_id(db: sqlite3.Connection, slug: str, generation: int) -> int:
    row = db.execute("SELECT id FROM types WHERE slug=? AND generation_id<=?", (slug.lower(), generation)).fetchone()
    if row is None:
        raise ValueError(f"Type '{slug}' does not exist in generation {generation}")
    return row[0]


def factor(db: sqlite3.Connection, generation: int, attack: int, defenses: list[int]) -> dict:
    """Combined multiplier (as a float) and per-defense factors for one attacking type."""
    parts = []
    combined = 100
    for defense in defenses:
        row = db.execute(
            "SELECT damage_factor, evidence_id FROM type_effectiveness WHERE generation_id=? AND "
            "attack_type_id=? AND defense_type_id=?",
            (generation, attack, defense),
        ).fetchone()
        if row is None:
            raise ValueError("Type pair missing from the chart")
        parts.append({"defense_type_id": defense, "damage_factor": row[0], "evidence_id": row[1]})
        combined = combined * row[0] // 100
    return {"multiplier": combined / 100, "parts": parts}


def chart(db: sqlite3.Connection, generation: int) -> list[dict]:
    return [
        dict(r)
        for r in db.execute(
            """SELECT a.slug AS attack, d.slug AS defense, t.damage_factor, t.evidence_id
           FROM type_effectiveness t JOIN types a ON a.id=t.attack_type_id JOIN types d ON d.id=t.defense_type_id
           WHERE t.generation_id=? ORDER BY a.id, d.id""",
            (generation,),
        )
    ]
