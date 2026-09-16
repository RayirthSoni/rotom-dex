"""Resolve generation- and version-group-specific values from PokéAPI history tables."""

from __future__ import annotations

from collections import defaultdict

# Damage category before the Generation IV split is determined by the move's type.
TYPE_BASED_CLASS_MAX_GENERATION = 3


def historical(current: list[dict], past: list[dict], generation: int, keys: tuple[str, ...]):
    """Past rows are valid through their generation_id, inclusive; nearest wins per key.

    keys=() replaces the whole set (types); ("stat_id",) or ("slot",) replaces one entry.
    An empty ability_id in a past row explicitly removes a slot (callers skip it).
    """
    selected = defaultdict(list)
    for row in past:
        if int(row["generation_id"]) >= generation:
            selected[tuple(row[k] for k in keys)].append(row)
    result = {tuple(r[k] for k in keys): [r] for r in current} if keys else {(): list(current)}
    for key, rows in selected.items():
        end = min(int(r["generation_id"]) for r in rows)
        result[key] = [r for r in rows if int(r["generation_id"]) == end]
    return [r for group in result.values() for r in group]


def rewind_move(move: dict, changes: list[dict], group_order: dict[int, int], target_order: int):
    """Undo move_changelog entries made after the target version group, newest first."""
    row = dict(move)
    later = [c for c in changes if group_order[int(c["changed_in_version_group_id"])] > target_order]
    for change in sorted(later, key=lambda c: group_order[int(c["changed_in_version_group_id"])], reverse=True):
        for field in (
            "type_id",
            "power",
            "pp",
            "accuracy",
            "priority",
            "target_id",
            "effect_id",
            "effect_chance",
        ):
            if change[field] != "":
                row[field] = change[field]
    return row


def damage_class(generation: int, source_class: str, type_class: str | None) -> str:
    """Status stays status; damaging moves before Gen IV take their type's class."""
    if source_class == "status":
        return "status"
    if generation <= TYPE_BASED_CLASS_MAX_GENERATION:
        if type_class is None:
            raise ValueError("Type without a damage class used before Generation IV")
        return type_class
    return source_class
