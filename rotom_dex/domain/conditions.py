"""Typed, fail-closed condition vocabulary with three-valued evaluation.

Conditions describe evolution requirements and acquisition prerequisites. They
are validated structurally on write and on read. `unknown` leaves carry a reason
and never evaluate to true; absent context means unknown, not false.
"""

from __future__ import annotations

# op -> ("none" | "identifier" | "int" | "choice", allowed choices)
_LEAVES: dict[str, tuple[str, tuple[str, ...]]] = {
    "always": ("none", ()),
    "trade": ("none", ()),
    "overworld_rain": ("none", ()),
    "device_upside_down": ("none", ()),
    "level_at_least": ("int", ()),
    "happiness_at_least": ("int", ()),
    "beauty_at_least": ("int", ()),
    "affection_at_least": ("int", ()),
    "has_pokemon": ("identifier", ()),
    "has_item": ("identifier", ()),
    "use_item": ("identifier", ()),
    "held_item": ("identifier", ()),
    "knows_move": ("identifier", ()),
    "knows_move_type": ("identifier", ()),
    "party_has_pokemon": ("identifier", ()),
    "party_has_type": ("identifier", ()),
    "trade_for_pokemon": ("identifier", ()),
    "at_location": ("identifier", ()),
    "in_region": ("identifier", ()),
    "milestone": ("identifier", ()),
    "encounter_condition": ("identifier", ()),
    "encounter_pokemon": ("identifier", ()),
    "time_of_day": ("identifier", ()),
    "gender": ("choice", ("male", "female")),
    "stat_relation": ("choice", ("attack>defense", "attack<defense", "attack=defense")),
}

# Context keys used by numeric leaves.
_NUMERIC_CONTEXT = {
    "level_at_least": "level",
    "happiness_at_least": "happiness",
    "beauty_at_least": "beauty",
    "affection_at_least": "affection",
}
_INT_RANGES = {
    "level_at_least": (1, 100),
    "happiness_at_least": (1, 255),
    "beauty_at_least": (1, 255),
    "affection_at_least": (1, 255),
}

SUPPORTED_OPS = frozenset({"and", "or", "unknown", *_LEAVES})


def validate_condition(value: object) -> None:
    if not isinstance(value, dict) or "op" not in value:
        raise ValueError("Condition must be an object with op")
    op = value["op"]
    if op in {"and", "or"}:
        args = value.get("args")
        if set(value) != {"op", "args"} or not isinstance(args, list) or not args:
            raise ValueError("and/or require nonempty args")
        for arg in args:
            validate_condition(arg)
        return
    if op == "unknown":
        reason = value.get("reason")
        if set(value) != {"op", "reason"} or not isinstance(reason, str) or not reason:
            raise ValueError("Unknown conditions require a reason")
        return
    if op not in _LEAVES:
        raise ValueError(f"Unsupported condition: {op}")
    kind, choices = _LEAVES[op]
    if kind == "none":
        if set(value) != {"op"}:
            raise ValueError(f"{op} takes no arguments")
        return
    if set(value) != {"op", "value"}:
        raise ValueError(f"{op} requires exactly one value")
    arg = value["value"]
    if kind == "int":
        low, high = _INT_RANGES[op]
        if type(arg) is not int or not low <= arg <= high:
            raise ValueError(f"Invalid {op} value: {arg!r}")
    elif kind == "identifier":
        if not isinstance(arg, str) or not arg:
            raise ValueError(f"{op} requires a nonempty identifier")
    elif kind == "choice" and arg not in choices:
        raise ValueError(f"{op} must be one of {choices}")


def evaluate_condition(value: dict, context: dict) -> bool | None:
    """Three-valued evaluation against a playthrough context.

    Context keys: numeric (`level`, `happiness`, ...) and collections keyed by
    the leaf op (for example `has_pokemon: {"ralts"}`). `trade`, `overworld_rain`
    and `device_upside_down` read boolean context keys of the same name.
    """
    validate_condition(value)
    op = value["op"]
    if op == "unknown":
        return None
    if op == "always":
        return True
    if op in {"and", "or"}:
        results = [evaluate_condition(arg, context) for arg in value["args"]]
        decisive = op == "or"
        if decisive in results:
            return decisive
        return None if None in results else not decisive
    if op in _NUMERIC_CONTEXT:
        key = _NUMERIC_CONTEXT[op]
        return None if key not in context else context[key] >= value["value"]
    if op not in context:
        return None
    if _LEAVES[op][0] == "none":
        return bool(context[op])
    return value["value"] in context[op]


def unknown(reason: str) -> dict:
    return {"op": "unknown", "reason": reason}


def all_of(*args: dict) -> dict:
    flat = [a for a in args if a != {"op": "always"}]
    if not flat:
        return {"op": "always"}
    return flat[0] if len(flat) == 1 else {"op": "and", "args": flat}
