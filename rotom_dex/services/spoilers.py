"""Server-side spoiler filtering.

`spoiler_level` has been carried on `PlaythroughContext` and validated at the API edge since the
first release, but nothing in Python ever read it: the only filter was in the browser, over the
milestone list alone. That is survivable when the client decides what to render. It is not
survivable once a model is involved, because a model cannot be un-told something.

So this runs on the way *out of* a tool and *into* the model. Content past the player's frontier is
removed before the provider ever sees it, and what was removed is reported as an assumption rather
than quietly dropped -- a player who asked for no spoilers should still learn that something exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rotom_dex.repositories.common import GameScope
from rotom_dex.services.context import PlaythroughContext

LEVELS = ("none", "hint", "full")

# How far past the player's furthest completed milestone each level is willing to show.
LOOKAHEAD = {"none": 0, "hint": 1}


@dataclass(frozen=True)
class Gate:
    level: str
    frontier_ord: int
    visible_milestones: frozenset[str] = frozenset()
    hidden_milestones: frozenset[str] = frozenset()
    hidden_battles: frozenset[str] = frozenset()
    forbidden_terms: tuple[str, ...] = ()
    hidden_tokens: tuple[str, ...] = ()
    hidden_count: int = 0
    _milestone_of_battle: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def filtering(self) -> bool:
        return self.level != "full" and self.hidden_count > 0

    def assumption(self) -> str:
        return f"{self.hidden_count} later story step(s) are hidden by your '{self.level}' spoiler preference. They exist; they were withheld, not searched for and missed."


def gate(db, scope: GameScope, ctx: PlaythroughContext) -> Gate:
    """What this player has asked not to be told yet."""
    level = ctx.spoiler_level if ctx.spoiler_level in LEVELS else "hint"
    rows = [
        {"slug": r[0], "ord": r[1], "name": r[2], "own": r[3]}
        for r in db.execute(
            "SELECT slug, ord, name, spoiler_level FROM milestones WHERE game_id=? ORDER BY ord",
            (scope.id,),
        )
    ]
    if level == "full" or not rows:
        return Gate(level=level, frontier_ord=0, visible_milestones=frozenset(r["slug"] for r in rows))

    completed = set(ctx.completed_milestones)
    frontier = max((r["ord"] for r in rows if r["slug"] in completed), default=0)
    horizon = frontier + LOOKAHEAD[level]

    visible, hidden, terms = set(), set(), []
    for row in rows:
        if row["slug"] in completed or row["ord"] <= horizon or row["own"] == "none":
            visible.add(row["slug"])
        else:
            hidden.add(row["slug"])
            terms.append(row["name"])

    battles = {r[0]: (r[1], r[2]) for r in db.execute("SELECT id, milestone_id, name FROM trainer_battles WHERE game_id=?", (scope.id,))}
    milestone_of_battle, hidden_battles = {}, set()
    for battle_id, (milestone_id, name) in battles.items():
        slug = milestone_id.split(":", 1)[1] if milestone_id else None
        milestone_of_battle[battle_id] = slug
        if slug in hidden:
            hidden_battles.add(battle_id)
            terms.append(name)
            # "Champion Wallace" also leaks as bare "Wallace".
            bare = name.rsplit(" ", 1)[-1]
            if len(bare) > 3:
                terms.append(bare)

    # Longest first, so "elite-four-drake" is masked before "elite-four" can match inside it.
    tokens = sorted({*hidden, *hidden_battles, *terms}, key=len, reverse=True)
    return Gate(
        level=level,
        frontier_ord=frontier,
        visible_milestones=frozenset(visible),
        hidden_milestones=frozenset(hidden),
        hidden_battles=frozenset(hidden_battles),
        forbidden_terms=tuple(sorted(set(terms))),
        hidden_tokens=tuple(tokens),
        hidden_count=len(hidden),
        _milestone_of_battle=milestone_of_battle,
    )


def _redacted(kind: str, level: str) -> dict:
    return {
        "redacted": True,
        "reason": "spoiler-filter",
        "kind": kind,
        "note": f"A later story step exists here and is hidden by your '{level}' spoiler preference.",
    }


def _is_hidden(node: dict, g: Gate) -> str | None:
    """Which kind of hidden row this is, if any."""
    slug = node.get("slug")
    if slug and "ord" in node and "kind" in node and slug in g.hidden_milestones:
        return "milestone"
    ident = node.get("id")
    if ident and ident in g.hidden_battles:
        return "battle"
    milestone_id = node.get("milestone_id")
    if milestone_id and isinstance(milestone_id, str):
        tail = milestone_id.split(":", 1)[1] if ":" in milestone_id else milestone_id
        if tail in g.hidden_milestones:
            return "battle"
    return None


MASK = "[hidden by spoiler preference]"


def _mask(text: str, g: Gate) -> str:
    """Hidden identifiers leak through free text too -- a coverage note naming the final milestone
    is as much of a spoiler as the milestone row itself."""
    for token in g.hidden_tokens:
        if token and token.lower() in text.lower():
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            text = pattern.sub(MASK, text)
    return text


def apply(value, g: Gate) -> tuple[object, int]:
    """Replace hidden rows with a stub and mask hidden names in free text.

    Verdicts are never touched. Hiding *where* something is must not read as a claim that it cannot
    be obtained, which is the one mistake this project refuses to make anywhere else either.
    """
    if g.level == "full":
        return value, 0
    removed = 0

    def walk(node):
        nonlocal removed
        if isinstance(node, dict):
            kind = _is_hidden(node, g)
            if kind:
                removed += 1
                return _redacted(kind, g.level)
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, str):
            return _mask(node, g)
        return node

    return walk(value), removed


def leaks(text: str, g: Gate) -> list[str]:
    """Hidden terms that appear in model-written prose. Non-empty means the answer must be refused."""
    if not g.forbidden_terms or not text:
        return []
    haystack = text.lower()
    return [term for term in g.forbidden_terms if term.lower() in haystack]
