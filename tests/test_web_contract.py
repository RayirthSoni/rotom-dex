"""The contract the web client is written against.

`Envelope.data` is typed `Any`, so the payload shapes live in hand-written TypeScript
(`web/src/api/types.ts`) and nothing would notice if the backend stopped matching them. These tests
pin the keys the client actually reads, per endpoint, so a rename in a repository query fails here
rather than silently emptying a panel in the browser.

Keys listed are a required subset, not the whole payload: adding a field is fine, removing or
renaming one the client reads is not.
"""

from __future__ import annotations

import pytest

ENVELOPE_KEYS = {"game", "snapshot_id", "coverage_status", "coverage", "data", "assumptions", "evidence"}

GAME = "emerald"
CONTEXT = {
    "game": GAME,
    "completed_milestones": ["littleroot-arrival"],
    "closed_world": ["milestones"],
    "team": [{"pokemon": "ralts", "level": 12, "moves": ["confusion"], "ability": "synchronize", "nature": "modest"}],
}


def keys_of(value) -> set[str]:
    if isinstance(value, list):
        assert value, "the fixture must return at least one row for the contract to mean anything"
        return set(value[0])
    return set(value)


# (path, keys the client reads at the top of `data`)
GET_CONTRACT = [
    ("/api/games", {"slug", "name", "support_tier", "generation", "version_group", "coverage_status", "coverage_counts", "is_main_series"}),
    (f"/api/games/{GAME}", {"slug", "name", "generation", "version_group", "support_tier", "mechanics", "issues", "regions"}),
    ("/api/coverage/matrix", {"features", "games", "global_issues"}),
    (
        f"/api/vocabulary?game={GAME}",
        {"types", "stats", "damage_classes", "acquisition_methods", "learnset_methods", "item_categories", "item_pockets", "condition_ops", "mechanics"},
    ),
    (f"/api/types?game={GAME}", {"id", "slug", "name", "generation_id"}),
    (f"/api/type-effectiveness/chart?game={GAME}", {"generation", "pairs"}),
    (f"/api/type-effectiveness?game={GAME}&attack=water&defense=rock", {"generation", "attack", "defenses", "multiplier", "parts"}),
    (f"/api/natures?game={GAME}", {"id", "slug", "name", "increased_stat", "decreased_stat", "neutral"}),
    (f"/api/pokemon?game={GAME}&q=ralts", {"id", "slug", "name", "species_id", "presence", "types"}),
    (f"/api/pokemon/ralts?game={GAME}", {"form", "presence", "species", "types", "stats", "abilities", "egg_groups", "held_items", "dex_numbers", "other_forms"}),
    (f"/api/pokemon/ralts/evolution-chain?game={GAME}", {"chain_id", "form", "nodes", "edges", "applicability_counts"}),
    (f"/api/pokemon/ralts/learnset?game={GAME}", {"form", "moves", "method_counts", "machine_rules"}),
    (f"/api/pokemon/ralts/acquisition?game={GAME}", {"form", "routes", "route_counts"}),
    (f"/api/moves?game={GAME}&q=water-gun", {"id", "slug", "name", "type", "damage_class", "power", "accuracy", "pp", "priority"}),
    (f"/api/moves/water-gun?game={GAME}", {"slug", "name", "type", "damage_class", "power", "accuracy", "pp", "target", "short_effect", "flags", "learner_count"}),
    (f"/api/items?game={GAME}&q=potion", {"id", "slug", "name", "category", "pocket", "purchase_price", "price_provenance"}),
    (f"/api/items/tm39?game={GAME}", {"slug", "name", "category", "pocket", "attributes", "holdable", "machine", "acquisition", "shops", "held_by"}),
    (f"/api/abilities?game={GAME}", {"id", "slug", "name", "generation_id"}),
    (f"/api/tutors?game={GAME}", {"tutors", "eligible_learnset_rows"}),
    (f"/api/milestones?game={GAME}", {"id", "slug", "name", "ord", "kind", "location", "prerequisites", "spoiler_level"}),
    (f"/api/battles?game={GAME}", {"id", "name", "trainer_class", "location", "prize_money"}),
    (f"/api/battles/roxanne?game={GAME}", {"id", "name", "trainer_class", "party"}),
]


@pytest.mark.parametrize("path, top_keys", GET_CONTRACT)
def test_get_payloads_keep_the_keys_the_client_reads(client, path, top_keys):
    response = client.get(path)
    assert response.status_code == 200, response.text
    body = response.json()
    assert ENVELOPE_KEYS <= set(body)
    assert body["data"] is not None, f"{path} returned no data; the contract cannot be checked"
    missing = top_keys - keys_of(body["data"])
    assert not missing, f"{path} no longer returns {sorted(missing)}"


def test_nested_rows_the_client_renders(client):
    card = client.get(f"/api/pokemon/ralts?game={GAME}").json()["data"]
    assert {"slug", "name", "species_id", "species_name"} <= set(card["form"])
    assert {"stat", "base_stat", "effort"} <= set(card["stats"][0])
    assert {"slot", "type"} <= set(card["types"][0])
    assert {"slot", "ability", "name", "is_hidden"} <= set(card["abilities"][0])

    learnset = client.get(f"/api/pokemon/ralts/learnset?game={GAME}").json()["data"]
    assert {"method", "level", "move", "move_name", "type", "damage_class", "power", "accuracy", "pp"} <= set(learnset["moves"][0])

    acquisition = client.get(f"/api/pokemon/ralts/acquisition?game={GAME}").json()["data"]
    assert {"id", "method", "availability", "prerequisites", "verification_status", "location"} <= set(acquisition["routes"][0])

    chain = client.get(f"/api/pokemon/ralts/evolution-chain?game={GAME}").json()["data"]
    assert {"form_id", "slug", "name", "presence", "types"} <= set(chain["nodes"][0])
    assert {"id", "trigger", "conditions", "from_pokemon", "to_pokemon", "applicability"} <= set(chain["edges"][0])

    battle = client.get(f"/api/battles/roxanne?game={GAME}").json()["data"]
    assert {"slot", "pokemon", "name", "level", "ability", "held_item", "moves", "types"} <= set(battle["party"][0])

    matrix = client.get("/api/coverage/matrix").json()["data"]
    assert {"slug", "name", "support_tier", "generation", "has_facts", "features", "counts"} <= set(matrix["games"][0])


POST_CONTRACT = [
    ("/api/team/analyze", {"context": CONTEXT}, {"team", "coverage", "mechanics", "warnings"}),
    ("/api/boss/prepare", {"context": CONTEXT, "battle": "roxanne"}, {"battle", "threats", "team", "coverage", "levels", "resources"}),
    ("/api/acquisition/reachability", {"context": CONTEXT, "pokemon": ["ralts"], "items": ["tm39"]}, {"pokemon", "items", "closed_world"}),
    ("/api/pokemon/ralts/move-access", {"context": CONTEXT, "pokemon": "ralts", "member": 0}, {"pokemon", "moves", "method_counts", "access_counts", "machine_rules"}),
    ("/api/pokemon/kirlia/evolution-requirements", {"context": CONTEXT, "pokemon": "kirlia"}, {"pokemon", "outgoing", "incoming"}),
]


@pytest.mark.parametrize("path, body, top_keys", POST_CONTRACT)
def test_post_payloads_keep_the_keys_the_client_reads(client, path, body, top_keys):
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert ENVELOPE_KEYS <= set(payload)
    missing = top_keys - keys_of(payload["data"])
    assert not missing, f"{path} no longer returns {sorted(missing)}"


def test_derived_verdicts_keep_their_shape(client):
    """`derived` is what every verdict chip in the interface reads."""
    body = {"context": CONTEXT, "pokemon": ["ralts"], "items": ["tm39"]}
    data = client.post("/api/acquisition/reachability", json=body).json()["data"]
    route = data["items"][0]["routes"][0]
    assert {"status", "evaluation", "blocked_by", "unknown_because"} <= set(route["derived"])
    assert route["derived"]["status"] in ("reachable", "locked", "unknown")
    assert route["availability"] == "unknown", "the stored fact must never be rewritten by a derivation"

    access = client.post("/api/pokemon/ralts/move-access", json={"context": CONTEXT, "pokemon": "ralts", "member": 0}).json()["data"]
    row = access["moves"][0]
    assert row["eligible"] is True
    assert {"status"} <= set(row["access"])


def test_defence_layers_stay_separate(client):
    """The interface renders `basic` and `ability` as different claims; they must not be merged."""
    data = client.post("/api/team/analyze", json={"context": CONTEXT}).json()["data"]
    defence = data["team"][0]["defence"]
    assert {"generation", "types", "basic"} <= set(defence)
    assert {"by_type", "weaknesses", "resistances", "immunities"} <= set(defence["basic"])
    assert {"attack", "multiplier"} <= set(defence["basic"]["by_type"][0])
    coverage = data["coverage"]
    assert {"attacking_moves", "excluded_moves", "by_type", "super_effective_against", "no_effect_against"} <= set(coverage)


def test_the_error_shapes_the_client_normalises(client):
    """Two different bodies exist, and the client has a branch for each."""
    detail = client.get("/api/pokemon/ralts?game=nope").json()["detail"]
    assert isinstance(detail, str)

    validation = client.post("/api/team/analyze", json={"context": {"game": GAME, "team": [{"pokemon": "ralts"}] * 7}}).json()["detail"]
    assert isinstance(validation, list)
    assert {"loc", "msg", "type"} <= set(validation[0])
