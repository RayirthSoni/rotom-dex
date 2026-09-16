"""HTTP surface: validation, pagination, envelopes, evidence."""

import pytest

ENDPOINTS = [
    "/api/games",
    "/api/games/emerald",
    "/api/coverage?game=emerald",
    "/api/issues?game=emerald",
    "/api/types?game=emerald",
    "/api/type-effectiveness?game=emerald&attack=ghost&defense=steel",
    "/api/type-effectiveness/chart?game=emerald",
    "/api/natures?game=emerald",
    "/api/natures/adamant?game=emerald",
    "/api/pokemon?game=emerald&q=ralts",
    "/api/pokemon/ralts?game=emerald",
    "/api/pokemon/ralts/acquisition?game=emerald",
    "/api/pokemon/ralts/evolution?game=emerald",
    "/api/pokemon/ralts/learnset?game=emerald&max_level=10",
    "/api/moves?game=emerald&q=leaf",
    "/api/moves/leaf-blade?game=emerald",
    "/api/moves/leaf-blade/learners?game=emerald",
    "/api/items?game=emerald&q=berry",
    "/api/items/sitrus-berry?game=emerald",
    "/api/abilities?game=emerald",
    "/api/abilities/effect-spore?game=emerald",
    "/api/machines?game=emerald",
    "/api/locations?game=emerald",
    "/api/locations/hoenn-route-102/encounters?game=emerald",
    "/api/milestones?game=emerald",
    "/api/battles?game=emerald",
    "/api/battles/roxanne?game=emerald",
]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_every_endpoint_returns_an_envelope(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("snapshot_id", "coverage_status", "coverage", "data", "assumptions", "evidence"):
        assert key in body
    assert body["game"] is None or body["game"]["slug"] == "emerald"


def test_game_parameter_is_required_and_validated(client):
    assert client.get("/api/pokemon/ralts").status_code == 422
    response = client.get("/api/pokemon/ralts?game=omega-red")
    assert response.status_code == 404 and "Known games" in response.json()["detail"]
    assert client.get("/api/pokemon?game=emerald&limit=0").status_code == 422
    assert client.get("/api/pokemon?game=emerald&limit=201").status_code == 422
    assert client.get("/api/pokemon?game=emerald&offset=-1").status_code == 422
    assert client.get("/api/pokemon/ralts/learnset?game=emerald&max_level=101").status_code == 422
    assert client.get("/api/moves?game=emerald&damage_class=fire").status_code == 422
    assert client.get("/api/pokemon/nope?game=emerald").status_code == 404
    assert client.get("/api/type-effectiveness?game=red&attack=fairy&defense=dragon").status_code == 400


def test_pagination_is_consistent(client):
    first = client.get("/api/pokemon?game=red&limit=10").json()
    assert first["pagination"] == {"limit": 10, "offset": 0, "total": 151}
    assert len(first["data"]) == 10
    tail = client.get("/api/pokemon?game=red&limit=10&offset=150").json()
    assert len(tail["data"]) == 1 and tail["pagination"]["total"] == 151
    beyond = client.get("/api/pokemon?game=red&limit=10&offset=1000").json()
    assert beyond["data"] == [] and beyond["pagination"]["total"] == 151


def test_evidence_resolves_to_sources(client):
    body = client.get("/api/pokemon/ralts?game=emerald").json()
    assert body["evidence"]
    for entry in body["evidence"]:
        assert entry["sources"]
        for source in entry["sources"]:
            assert source["kind"] in ("dataset", "game-pack", "reference", "code")
            assert source["sha256"] is None or len(source["sha256"]) == 64
            assert source["selector"]
    evidence_id = body["evidence"][0]["id"]
    assert client.get(f"/api/evidence/{evidence_id}").json()["data"]["id"] == evidence_id
    assert client.get("/api/evidence/nope").status_code == 404
    battle = client.get("/api/battles/roxanne?game=emerald").json()
    refs = {s["source_id"] for e in battle["evidence"] for s in e["sources"]}
    assert "ref:emerald:roxanne" in refs and "pack:emerald" in refs


def test_type_matchups_use_the_game_generation(client):
    assert client.get("/api/type-effectiveness?game=red&attack=ghost&defense=psychic").json()["data"]["multiplier"] == 0
    assert client.get("/api/type-effectiveness?game=emerald&attack=ghost&defense=psychic").json()["data"]["multiplier"] == 2
    dual = client.get("/api/type-effectiveness?game=emerald&attack=ghost&defense=steel&defense2=psychic").json()["data"]
    assert dual["multiplier"] == 1
    assert len(client.get("/api/types?game=red").json()["data"]) == 15
    assert len(client.get("/api/types?game=x").json()["data"]) == 18


def test_learnset_filters_and_machine_rules(client):
    body = client.get("/api/pokemon/ralts/learnset?game=emerald&max_level=5").json()["data"]
    assert [m["move"] for m in body["moves"] if m["method"] == "level-up"] == ["growl"]
    assert body["method_counts"]["machine"] > 0
    assert body["machine_rules"]["tm_reusable"] == 0
    machine = [m for m in body["moves"] if m["method"] == "machine"][0]
    assert machine["machine_item"].startswith(("tm", "hm"))
    later = client.get("/api/pokemon/ralts/learnset?game=x&method=machine").json()["data"]
    assert later["machine_rules"]["tm_reusable"] == 1


def test_health_reports_snapshot(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and len(body["snapshot_id"]) == 64
