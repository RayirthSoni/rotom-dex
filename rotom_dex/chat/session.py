"""Resolve a conversation's exact game without changing any saved playthrough."""

from __future__ import annotations

import re


def mentioned_games(db, message: str) -> list[str]:
    matches = []
    occupied = []
    for row in db.execute("SELECT name FROM items WHERE instr(name, ' ')>0"):
        for match in re.finditer(r"(?<!\w)" + re.escape(row[0]) + r"(?!\w)", message, re.I):
            occupied.append(match.span())
    games = db.execute("SELECT slug, name FROM game_versions WHERE is_main_series=1").fetchall()
    aliases = []
    for row in games:
        for alias in {row["slug"].replace("-", " "), row["name"]}:
            aliases.append((alias, row["slug"]))
    for alias, slug in sorted(aliases, key=lambda a: len(a[0]), reverse=True):
        for m in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", message, re.I):
            if any(m.start() < b and m.end() > a for a, b in occupied):
                continue
            occupied.append(m.span())
            matches.append((m.start(), slug))
    return list(dict.fromkeys(slug for _, slug in sorted(matches)))


DLC_BASES = {
    **{f"{dlc}-{base}": base for dlc in ("the-isle-of-armor", "the-crown-tundra") for base in ("sword", "shield")},
    **{f"{dlc}-{base}": base for dlc in ("the-teal-mask", "the-indigo-disk") for base in ("scarlet", "violet")},
    "mega-dimension": "legends-za",
}


def game_context(game: str, dlc_access=()):
    base = DLC_BASES.get(game, game)
    access = set(dlc_access) | ({game} if game in DLC_BASES else set())
    if any(DLC_BASES.get(dlc) != base for dlc in access):
        from rotom_dex.errors import SemanticError

        raise SemanticError("DLC access must belong to the selected base game and version.")
    return {"game": game, "base_game": base, "dlc_access": sorted(access)}
