"""The POST analysis surface: request validation, honest abstention, envelope shape."""

from __future__ import annotations

import pytest

EMERALD = {
    "game": "emerald",
    "current_location": "rustboro-city",
    "completed_milestones": ["littleroot-arrival", "starter-chosen", "pokedex-received", "rival-route-103", "petalburg-wally"],
    "closed_world": ["milestones"],
    "team": [
        {"pokemon": "ralts", "level": 12, "moves": ["growl", "confusion"], "nature": "modest", "ability": "synchronize"},
        {"pokemon": "torchic", "level": 14, "moves": ["ember"], "ability": "blaze"},
    ],
}

ENVELOPE_KEYS = ("game", "snapshot_id", "coverage_status", "coverage", "data", "assumptions", "evidence")

POSTS = [
    ("/api/team/analyze", {"context": EMERALD}),
    ("/api/boss/prepare", {"context": EMERALD, "battle": "roxanne"}),
    ("/api/acquisition/reachability", {"context": EMERALD, "pokemon": ["ralts"], "items": ["tm39"]}),
    ("/api/pokemon/ralts/move-access", {"context": EMERALD, "pokemon": "ralts", "member": 0}),
    ("/api/pokemon/kirlia/evolution-requirements", {"context": EMERALD, "pokemon": "kirlia"}),
]


@pytest.mark.parametrize("path, body", POSTS)
def test_every_service_returns_an_envelope(client, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    for key in ENVELOPE_KEYS:
        assert key in payload
    assert payload["game"]["slug"] == "emerald"
    assert payload["assumptions"], "a derived answer must always state its assumptions"


@pytest.mark.parametrize(
    "body, expected, fragment",
    [
        ({"context": {**EMERALD, "team": [{"pokemon": "ralts"}] * 7}}, 422, "team"),
        ({"context": {**EMERALD, "team": [{"pokemon": "ralts", "moves": ["a", "b", "c", "d", "e"]}]}}, 422, "moves"),
        ({"context": {**EMERALD, "team": [{"pokemon": "ralts", "level": 0}]}}, 422, "level"),
        ({"context": {**EMERALD, "team": [{"pokemon": "ralts", "level": 101}]}}, 422, "level"),
        ({"context": {**EMERALD, "closed_world": ["nonsense"]}}, 422, "closed_world"),
        ({"context": {**EMERALD, "surprise": True}}, 422, "surprise"),
        ({"context": {**EMERALD, "team": [{"pokemon": "ralts", "surprise": 1}]}}, 422, "surprise"),
    ],
)
def test_malformed_requests_are_rejected_with_a_field_path(client, body, expected, fragment):
    response = client.post("/api/team/analyze", json=body)
    assert response.status_code == expected
    assert fragment in str(response.json()["detail"])


@pytest.mark.parametrize(
    "body, expected, fragment",
    [
        ({"context": {"game": "nope"}}, 404, "Known games"),
        ({"context": {**EMERALD, "completed_milestones": ["not-a-milestone"]}}, 404, "not a recorded milestone"),
        ({"context": {**EMERALD, "visited_locations": ["nowhere"]}}, 404, "Unknown location"),
        ({"context": {"game": "emerald", "team": [{"pokemon": "missingno"}]}}, 404, "Unknown Pokemon"),
        ({"context": {"game": "red", "team": [{"pokemon": "pikachu", "nature": "modest"}]}}, 400, "no Natures"),
        ({"context": {"game": "red", "team": [{"pokemon": "pikachu", "ability": "static"}]}}, 400, "no Abilities"),
        ({"context": {"game": "red", "team": [{"pokemon": "pikachu", "moves": ["rock-tomb"]}]}}, 400, "does not exist in this game"),
    ],
)
def test_identifiers_are_resolved_against_the_requested_game(client, body, expected, fragment):
    response = client.post("/api/team/analyze", json=body)
    assert response.status_code == expected, response.text
    assert fragment in response.json()["detail"]


def test_an_unimported_game_is_not_an_error(client):
    """Excluded games return the same `data: null` envelope the read endpoints use."""
    response = client.post("/api/team/analyze", json={"context": {"game": "colosseum"}})
    assert response.status_code == 200
    body = response.json()
    assert body["data"] is None and body["coverage_status"] == "missing"
    assert any("colosseum" in a for a in body["assumptions"])


def test_boss_preparation_abstains_instead_of_blaming_the_question(client):
    """A game with no reviewed rosters explains the gap; an unknown battle in Emerald is a 404."""
    response = client.post("/api/boss/prepare", json={"context": {"game": "red"}, "battle": "roxanne"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"] is None and body["coverage_status"] == "missing"
    assert "No boss rosters have been reviewed for red" in body["assumptions"][0]

    assert client.post("/api/boss/prepare", json={"context": {"game": "emerald"}, "battle": "nope"}).status_code == 404


def test_closed_world_is_the_only_lever_between_locked_and_unknown(client):
    """The same request differs only by what the player vouched for."""

    def status(closed_world, milestones):
        body = {"context": {"game": "emerald", "closed_world": closed_world, "completed_milestones": milestones}, "items": ["tm39"]}
        payload = client.post("/api/acquisition/reachability", json=body).json()
        routes = payload["data"]["items"][0]["routes"]
        return next(r["derived"] for r in routes if r["id"] == "pack:9:tm39-roxanne")

    assert status([], ["stone-badge"])["status"] == "unknown"
    locked = status(["milestones"], [])
    assert locked["status"] == "locked"
    assert [b["value"] for b in locked["blocked_by"]] == ["stone-badge"]
    assert status(["milestones"], ["stone-badge"])["status"] == "reachable"


def test_reachability_requires_a_subject(client):
    response = client.post("/api/acquisition/reachability", json={"context": EMERALD})
    assert response.status_code == 400
    assert "at least one" in response.json()["detail"]


def test_move_access_reports_eligibility_and_access_separately(client):
    body = {"context": EMERALD, "pokemon": "ralts", "member": 0}
    data = client.post("/api/pokemon/ralts/move-access", json=body).json()["data"]
    assert all(row["eligible"] is True for row in data["moves"])
    statuses = {row["method"]: {r["access"]["status"] for r in data["moves"] if r["method"] == row["method"]} for row in data["moves"]}
    assert statuses["tutor"] == {"unknown"}
    assert "reachable" in statuses["level-up"] and "locked" in statuses["level-up"]


def test_team_analysis_keeps_the_ability_layer_separate(client):
    data = client.post("/api/team/analyze", json={"context": EMERALD}).json()["data"]
    ralts = next(m for m in data["team"] if m["pokemon"] == "ralts")
    assert "basic" in ralts["defence"]
    assert ralts["defence"]["basic"]["by_type"], "the type-only layer is always present"
    assert data["coverage"]["attacking_moves"] and data["coverage"]["excluded_moves"]


def test_a_team_member_absent_from_the_game_is_kept_and_explained(client):
    body = {"context": {"game": "red", "team": [{"pokemon": "ralts"}]}}
    payload = client.post("/api/team/analyze", json=body).json()
    member = payload["data"]["team"][0]
    assert member["types"] == [] and member["defence"] is None
    assert "not a claim it is unobtainable" in member["note"]
    assert any("no data for red" in a for a in payload["assumptions"])
