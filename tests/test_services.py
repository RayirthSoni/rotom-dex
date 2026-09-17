"""Domain services: the honesty properties, not just the happy path."""

from __future__ import annotations

import itertools
import json
import random

import pytest

from rotom_dex.domain.conditions import evaluate_condition, explain_condition
from rotom_dex.repositories.common import resolve_game
from rotom_dex.services import boss, defense, move_access, offense, reachability
from rotom_dex.services.context import PlaythroughContext, TeamMember, classify, condition_context, validate

EMERALD_MILESTONES = ("littleroot-arrival", "starter-chosen", "pokedex-received", "rival-route-103", "petalburg-wally")


def ctx(game="emerald", **kwargs) -> PlaythroughContext:
    return PlaythroughContext(game=game, **kwargs)


# -- conditions -------------------------------------------------------------------------------


def test_explain_condition_agrees_with_evaluate_condition(db):
    """The explanation must never disagree with the verdict it explains."""
    stored = [json.loads(r[0]) for r in db.execute("SELECT conditions FROM evolution_rules")]
    stored += [json.loads(r[0]) for r in db.execute("SELECT prerequisites FROM acquisitions")]
    stored += [json.loads(r[0]) for r in db.execute("SELECT prerequisites FROM milestones")]
    random.seed(0)
    sample = random.sample(stored, min(1500, len(stored)))
    contexts = [
        {},
        {"level": 30, "milestone": {"stone-badge"}, "at_location": {"rustboro-city"}},
        {"level": 5, "milestone": set(), "at_location": set(), "has_pokemon": {"ralts"}, "trade": True},
        {"milestone": set(EMERALD_MILESTONES), "has_item": {"sun-stone"}, "level": 100},
    ]
    for condition, context in itertools.product(sample, contexts):
        assert evaluate_condition(condition, context) is explain_condition(condition, context)["result"]


def test_explanations_name_the_blocking_leaf():
    condition = {"op": "and", "args": [{"op": "milestone", "value": "stone-badge"}, {"op": "unknown", "reason": "not reviewed"}]}
    verdict = classify(condition, {"milestone": set()})
    assert verdict["status"] == "locked"
    assert verdict["blocked_by"] == [{"op": "milestone", "value": "stone-badge"}]

    # Same route, milestone satisfied: the unreviewed gate now decides, and it decides nothing.
    verdict = classify(condition, {"milestone": {"stone-badge"}})
    assert verdict["status"] == "unknown"
    assert verdict["unknown_because"] == [{"op": "unknown", "reason": "not reviewed"}]


def test_a_satisfied_or_branch_blames_nobody():
    condition = {"op": "or", "args": [{"op": "milestone", "value": "a"}, {"op": "milestone", "value": "b"}]}
    assert classify(condition, {"milestone": {"b"}}) == {"status": "reachable", "evaluation": True, "blocked_by": [], "unknown_because": []}
    assert [b["value"] for b in classify(condition, {"milestone": set()})["blocked_by"]] == ["a", "b"]


# -- closed world -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "closed_world, milestones, expected",
    [
        (frozenset(), ("stone-badge",), "unknown"),  # vouched for nothing: absence proves nothing
        (frozenset({"milestones"}), (), "locked"),  # vouched for the list: the badge is genuinely missing
        (frozenset({"milestones"}), ("stone-badge",), "reachable"),
    ],
)
def test_closed_world_decides_locked_versus_unknown(db, closed_world, milestones, expected):
    """The only lever between 'locked' and 'unknown' is what the player vouched for."""
    scope = resolve_game(db, "emerald")
    context, _ = condition_context(ctx(closed_world=closed_world, completed_milestones=milestones))
    result = reachability.for_item(db, scope, ctx(closed_world=closed_world, completed_milestones=milestones), "tm39")
    tm39 = next(r for r in result["routes"] if r["id"] == "pack:9:tm39-roxanne")
    assert tm39["derived"]["status"] == expected
    assert classify({"op": "milestone", "value": "stone-badge"}, context)["status"] == expected


def test_a_reviewed_location_gate_is_settled_by_milestones_alone(db):
    """A reviewed gate is a claim about story access, so vouching for milestones settles it.

    This is the point of curating gates: before any existed, every encounter stayed unknown for
    every player forever. `at_location` is deliberately *not* what resolves here -- the gate is,
    which is why the player never has to vouch for a complete visited-location list.
    """
    scope = resolve_game(db, "emerald")
    playthrough = ctx(closed_world=frozenset({"milestones"}), completed_milestones=EMERALD_MILESTONES)
    result = reachability.for_pokemon(db, scope, playthrough, "zigzagoon")
    walk = [r for r in result["routes"] if r["id"].startswith("encounter:") and r["method"] == "walk"]
    assert walk, "Zigzagoon has recorded walking encounters in Emerald"
    assert "reachable" in {r["derived"]["status"] for r in walk}
    assert "at_location" not in json.dumps([r["derived"] for r in walk])


def test_a_method_a_player_cannot_use_yet_is_never_reachable(db):
    """Reaching the place is not working the slot: Surf slots stay locked until Surf is available."""
    scope = resolve_game(db, "emerald")
    playthrough = ctx(closed_world=frozenset({"milestones"}), completed_milestones=EMERALD_MILESTONES)
    result = reachability.for_pokemon(db, scope, playthrough, "tentacool")
    surf = [r for r in result["routes"] if r["id"].startswith("encounter:") and r["method"] == "surf"]
    assert surf, "Tentacool is a Surf encounter in Emerald"
    assert "reachable" not in {r["derived"]["status"] for r in surf}


def test_no_derivation_ever_reports_unavailable(db):
    """`unavailable` is reserved for reviewed evidence; nothing derived may claim it."""
    scope = resolve_game(db, "emerald")
    playthrough = ctx(closed_world=frozenset(dict.fromkeys(["milestones", "locations", "bag", "party", "trade"])))
    for slug in ("ralts", "zigzagoon", "treecko", "shroomish"):
        result = reachability.for_pokemon(db, scope, playthrough, slug)
        for route in result["routes"]:
            assert route["derived"]["status"] in ("reachable", "locked", "unknown")
            assert route["availability"] == "unknown", "the stored fact must be echoed untouched"


def test_an_unreviewed_gate_can_never_make_a_route_reachable(db):
    """An *ungated* encounter keeps its unknown leaf, so no amount of vouching can promote it.

    Curating gates for some locations must not leak a verdict into the ones nobody has reviewed.
    """
    scope = resolve_game(db, "emerald")
    gated = {
        r[0]
        for r in db.execute(
            """SELECT DISTINCT l.slug FROM acquisitions a JOIN locations l ON l.id=a.location_id
           WHERE a.game_id=? AND a.prerequisites NOT LIKE '%"unknown"%'""",
            (scope.id,),
        )
    }
    everything = ctx(
        closed_world=frozenset({"milestones", "locations", "bag", "party", "trade"}),
        completed_milestones=tuple(r[0] for r in db.execute("SELECT slug FROM milestones WHERE game_id=?", (scope.id,))),
        visited_locations=tuple(r[0] for r in db.execute("SELECT slug FROM locations")),
        bag=tuple(r[0] for r in db.execute("SELECT slug FROM items LIMIT 500")),
        trade_access="any",
    )
    placeholders = ",".join("?" * len(gated))
    ungated = db.execute(
        f"""SELECT f.slug FROM acquisitions a JOIN pokemon_forms f ON f.id=a.form_id
            JOIN locations l ON l.id=a.location_id WHERE a.game_id=? AND l.slug NOT IN ({placeholders})
            AND a.prerequisites LIKE '%Progression gates%' LIMIT 1""",
        (scope.id, *sorted(gated)),
    ).fetchone()
    assert ungated, "Emerald still has locations with no reviewed gate"
    result = reachability.for_pokemon(db, scope, everything, ungated[0])
    blanket = [r for r in result["routes"] if r["id"].startswith("encounter:") and "Progression gates" in json.dumps(r.get("prerequisites", {}))]
    assert blanket, "expected at least one route still behind the blanket unknown"
    assert all(r["derived"]["status"] == "unknown" for r in blanket)


# -- defence and offence ----------------------------------------------------------------------


def test_type_chart_is_generation_scoped(db):
    scope = resolve_game(db, "red")
    profile = defense.profile(db, scope, ["psychic"])
    by_type = {row["attack"]: row["multiplier"] for row in profile["basic"]["by_type"]}
    assert by_type["ghost"] == 0, "Generation I's Ghost/Psychic bug"
    assert "dark" not in by_type and "steel" not in by_type
    with pytest.raises(ValueError, match="does not exist in generation"):
        defense.profile(db, scope, ["fairy"])


def test_ability_layer_is_separate_and_generation_aware(db):
    emerald, platinum = resolve_game(db, "emerald"), resolve_game(db, "platinum")

    # Lightning Rod granted no immunity before Generation V, and the curated data says so.
    gen3 = defense.profile(db, emerald, ["ground"], "lightning-rod")
    assert gen3["basic"]["immunities"] == ["electric"]  # Ground is already immune
    assert gen3["ability"]["modifiers"] == []

    # Dry Skin in Generation IV: Water becomes an immunity, Fire hits harder.
    gen4 = defense.profile(db, platinum, ["fire"], "dry-skin")
    assert "water" in gen4["basic"]["weaknesses"]
    assert "water" in gen4["ability"]["immunities"]
    assert gen4["basic"] != gen4["ability"], "the two layers are reported separately"


def test_abilities_are_not_applied_where_the_mechanic_is_absent(db):
    scope = resolve_game(db, "red")
    profile = defense.profile(db, scope, ["ground", "flying"], "levitate")
    assert profile["ability"]["modifiers"] == []
    assert "no Abilities" in profile["ability"]["note"]


def test_offensive_coverage_uses_only_damaging_moves(db):
    scope = resolve_game(db, "emerald")
    team = [{"pokemon": "ralts", "moves": ["growl", "confusion"]}]
    result = offense.coverage(db, scope, team)
    assert [m["move"] for m in result["attacking_moves"]] == ["confusion"]
    excluded = {m["move"]: m["reason"] for m in result["excluded_moves"]}
    assert "growl" in excluded and "no damage" in excluded["growl"]
    assert "psychic" in result["resisted_against"] or "psychic" in result["no_effect_against"]


# -- eligibility versus access ------------------------------------------------------------------


def test_tutor_eligibility_never_implies_tutor_access(db):
    """The source has no tutor locations, so access must be unknown wherever eligibility exists."""
    scope = resolve_game(db, "emerald")
    result = move_access.eligibility(db, scope, ctx(), "ralts", TeamMember("ralts", level=20))
    tutor_rows = [m for m in result["moves"] if m["method"] == "tutor"]
    assert tutor_rows, "Ralts is tutor-eligible for several moves in Emerald"
    assert db.execute("SELECT count(*) FROM tutors").fetchone()[0] == 0
    for row in tutor_rows:
        assert row["eligible"] is True
        assert row["access"]["status"] == "unknown"
        assert "tutor" in row["access"]["reason"].lower()


def test_level_up_access_follows_the_member_level(db):
    scope = resolve_game(db, "emerald")
    known = move_access.eligibility(db, scope, ctx(), "ralts", TeamMember("ralts", level=6))
    levels = {m["move"]: (m["level"], m["access"]["status"]) for m in known["moves"] if m["method"] == "level-up"}
    assert all(status == "reachable" for level, status in levels.values() if level <= 6)
    assert all(status == "locked" for level, status in levels.values() if level > 6)

    # No level recorded means unknown, never "not yet".
    unknown = move_access.eligibility(db, scope, ctx(), "ralts", TeamMember("ralts"))
    assert {m["access"]["status"] for m in unknown["moves"] if m["method"] == "level-up"} == {"unknown"}


def test_egg_moves_are_locked_only_where_breeding_is_absent(db):
    red, emerald = resolve_game(db, "red"), resolve_game(db, "emerald")
    assert red.mechanics["breeding"] == 0 and emerald.mechanics["breeding"] == 1
    assert not [m for m in move_access.eligibility(db, red, ctx("red"), "pikachu")["moves"] if m["method"] == "egg"]
    egg = [m for m in move_access.eligibility(db, emerald, ctx(), "ralts")["moves"] if m["method"] == "egg"]
    assert egg and {m["access"]["status"] for m in egg} == {"unknown"}


# -- boss preparation ---------------------------------------------------------------------------


def test_boss_preparation_abstains_where_no_roster_was_reviewed(db):
    # Emerald and Red are the two reviewed games, so the abstention subjects are games whose packs
    # hold nothing. Adding a pack for one of these later should break this test on purpose.
    for game in ("ruby", "platinum", "scarlet"):
        scope = resolve_game(db, game)
        result = boss.prepare(db, scope, ctx(game), "roxanne")
        assert result["data"] is None
        assert "No boss rosters have been reviewed" in result["assumptions"][0]


def test_boss_preparation_reads_the_reviewed_roster(db):
    scope = resolve_game(db, "emerald")
    playthrough = ctx(team=(TeamMember("marshtomp", level=16, moves=("water-gun",)),))
    result = boss.prepare(db, scope, playthrough, "roxanne")
    assert [t["pokemon"] for t in result["threats"]] == ["geodude", "geodude", "nosepass"]
    geodude = result["threats"][0]
    assert geodude["our_best_move"] == {"pokemon": "marshtomp", "move": "water-gun", "multiplier": 4.0}
    assert result["levels"] == {**result["levels"], "their_highest": 15, "your_lowest": 16}


def test_boss_preparation_never_states_an_outcome(db):
    """Nothing in the payload may read as a prediction."""
    scope = resolve_game(db, "emerald")
    result = boss.prepare(db, scope, ctx(team=(TeamMember("marshtomp", level=16, moves=("water-gun",)),)), "roxanne")
    blob = json.dumps(result).lower()
    for word in ("will win", "you win", "guaranteed", "victory", "win probability", "you should win"):
        assert word not in blob
    assert any("not a prediction" in a for a in boss.ASSUMPTIONS)


# -- validation ---------------------------------------------------------------------------------


def test_validation_rejects_mechanics_the_game_does_not_have(db):
    red = resolve_game(db, "red")
    with pytest.raises(ValueError, match="no Natures"):
        validate(db, red, ctx("red", team=(TeamMember("pikachu", nature="modest"),)))
    with pytest.raises(ValueError, match="no Abilities"):
        validate(db, red, ctx("red", team=(TeamMember("pikachu", ability="static"),)))
    with pytest.raises(ValueError, match="does not exist in this game"):
        validate(db, red, ctx("red", team=(TeamMember("pikachu", moves=("rock-tomb",)),)))


def test_validation_warns_rather_than_drops_a_pokemon_absent_from_the_game(db):
    red = resolve_game(db, "red")
    warnings = validate(db, red, ctx("red", team=(TeamMember("ralts"),)))
    assert warnings and "no data for red" in warnings[0]
