"""Acceptance regressions for the game-aware public assistant."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from starlette.requests import Request

from rotom_dex.api import deps
from rotom_dex.chat.answer import EMPTY, validate
from rotom_dex.chat.evidence import EvidenceLedger, wrap_tool_result
from rotom_dex.chat.orchestrator import compact
from rotom_dex.chat.protocols import ToolResult, Turn
from rotom_dex.chat.providers.gemini import GeminiProvider, _parts
from rotom_dex.chat.session import mentioned_games
from rotom_dex.chat.tools import REGISTRY
from rotom_dex.repositories.common import resolve_game
from rotom_dex.services import competitive, spoilers
from rotom_dex.services.context import PlaythroughContext, TeamMember
from rotom_dex.services.context import validate as validate_team


def request(key=None):
    return Request(
        {
            "type": "http",
            "headers": [(b"x-rotom-gemini-key", key.encode())] if key else [],
            "scheme": "https",
            "server": ("example.com", 443),
            "path": "/api/v2/chat",
            "query_string": b"",
        }
    )


def test_public_keys_do_not_fall_back_to_owner(monkeypatch):
    monkeypatch.setenv("ROTOM_GEMINI_API_KEY", "owner-secret")
    monkeypatch.setenv("ROTOM_CHAT_PROVIDER", "gemini")
    assert deps.get_chat_config(request()).api_key is None
    with ThreadPoolExecutor() as pool:
        configs = list(pool.map(lambda k: deps.get_chat_config(request(k)), ["visitor-one", "visitor-two"]))
    assert [c.api_key for c in configs] == ["visitor-one", "visitor-two"]
    assert all(c.api_key not in repr(c) for c in configs)


def test_request_scoped_clients_and_research(client, monkeypatch):
    from rotom_dex.api.routers import conversation

    seen = []

    def build(config):
        seen.append(config.api_key)
        return object()

    monkeypatch.setattr(conversation, "build_provider", build)
    monkeypatch.setattr(conversation, "build_research", build)
    monkeypatch.setattr(conversation.orchestrator, "answer", lambda *a, **k: dict(EMPTY))
    deps._HITS.clear()
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda key: client.post("/api/v2/chat", json={"message": "Where is Ralts in Emerald?"}, headers={"X-Rotom-Gemini-Key": key}), ["one", "two"]))
    assert [r.status_code for r in results] == [200, 200]
    assert sorted(seen) == ["one", "one", "two", "two"]
    assert client.post("/api/v2/chat", json={"message": "Where is Ralts in Emerald?"}).status_code == 401


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What about Diamond?", ["diamond"]),
        ("Compare Red and FireRed", ["red", "firered"]),
        ("Emerald vs Ruby", ["emerald", "ruby"]),
        ("Brilliant Diamond and Diamond", ["brilliant-diamond", "diamond"]),
    ],
)
def test_exact_game_mentions(db, question, expected):
    assert mentioned_games(db, question) == expected


def test_glossary_needs_no_game_or_key(client):
    deps._HITS.clear()
    r = client.post("/api/v2/chat", json={"message": "What is STAB?"})
    assert r.status_code == 200
    assert "matches its own type" in r.json()["data"]["prose"].lower()
    assert r.json()["data"]["games"] == []


def test_false_claim_with_real_evidence_is_removed(db):
    scope = resolve_game(db, "emerald")
    ctx = PlaythroughContext(game="emerald", spoiler_level="full")
    payload = REGISTRY["dex_lookup"].handler(db, scope, ctx, {"pokemon": "ralts"})
    ledger = EvidenceLedger()
    ledger.record_tool(payload)
    facts = ledger.bind(compact(payload), "dex_lookup", "emerald")
    stat = next(f for f in facts if f["label"] == "base attack")
    raw = {**EMPTY, "prose": "Ralts has 999 base Attack", "facts": [{"claim": "Ralts has 999 base Attack", "evidence_id": stat["evidence_id"], "tool": "dex_lookup"}]}
    result, _ = validate(db, raw, ledger, spoilers.gate(db, scope, ctx), max_prose=1200)
    assert "999" not in json.dumps(result)
    assert result["facts"] == []
    raw["facts"][0]["fact_id"] = stat["fact_id"]
    result, _ = validate(db, raw, ledger, spoilers.gate(db, scope, ctx), max_prose=1200)
    assert "999" not in json.dumps(result)
    assert result["facts"][0]["value"] == "25"


@pytest.mark.parametrize("bad", [None, [], {"facts": [None]}, {**EMPTY, "cards": [{"rows": None}]}])
def test_malformed_answers_are_recoverable(db, bad):
    result, notes = validate(db, bad, EvidenceLedger(), spoilers.Gate("full", 0), max_prose=1200)
    assert result["abstained"] and notes


def test_action_label_spoilers_are_blocked(db):
    gate = spoilers.Gate("none", 0, forbidden_terms=("Wallace",), hidden_count=1)
    result, _ = validate(
        db, {**EMPTY, "actions": [{"kind": "mark_milestone", "label": "Defeat Wallace", "payload": {"milestone": "stone-badge"}}]}, EvidenceLedger(), gate, max_prose=1200
    )
    assert result["abstained"] and not result["actions"]


def test_claims_cannot_escape_validation_through_advice_or_labels(db):
    raw = {
        **EMPTY,
        "prose": "Ralts has 999 base Attack",
        "recommendations": [{"subject": "ralts", "text": "Ralts has 999 base Attack", "rationale": "999 Attack guarantees a win", "status": "reachable"}],
        "assumptions": [{"text": "Assuming Ralts has 999 Attack", "because": "missing_data"}],
        "actions": [{"kind": "add_team_member", "label": "Add Ralts with 999 Attack", "payload": {"pokemon": "ralts"}}],
    }
    result, _ = validate(db, raw, EvidenceLedger(), spoilers.Gate("full", 0), max_prose=1200)
    assert "999" not in json.dumps(result)
    assert result["recommendations"][0]["status"] == "unknown"
    assert result["actions"][0]["label"] == "Add Ralts to team"


def test_provider_parts_and_ids_round_trip():
    p = GeminiProvider("test", "gemini-test", "https://example.invalid")
    parts = [{"functionCall": {"id": "call-abc", "name": "dex_lookup", "args": {"pokemon": "ralts"}}, "thoughtSignature": "opaque-signature"}]
    reply = p._reply({"candidates": [{"content": {"parts": parts}}]})
    assert _parts(Turn("model", tool_calls=reply.tool_calls, provider_parts=reply.provider_parts)) == parts
    assert _parts(Turn("tool", tool_results=(ToolResult("call-abc", "dex_lookup", "{}"),)))[0]["functionResponse"]["id"] == "call-abc"
    assert "test" not in repr(replace(p, model="model")) or "api_key=" not in repr(p)


def test_combined_results_keep_bound_facts(db):
    scope = resolve_game(db, "emerald")
    p = REGISTRY["dex_lookup"].handler(db, scope, PlaythroughContext(game="emerald"), {"pokemon": "ralts", "include": ["acquisition", "evolution", "learnset"]})
    p = compact(p)
    p["verified_facts"] = EvidenceLedger().bind(p, "dex_lookup", "emerald")
    result = json.loads(wrap_tool_result(tool="dex_lookup", call_id="a", snapshot_id="s", game="emerald", spoiler_level="full", redactions=0, payload=p, limit=8000))
    assert result["result"]["verified_facts"]


@pytest.mark.parametrize("game,move", [("red", "Mega Punch"), ("emerald", "Focus Punch")])
def test_tm01_effect_matches_exact_game(db, game, move):
    p = REGISTRY["item_lookup"].handler(db, resolve_game(db, game), PlaythroughContext(game=game), {"item": "tm01"})
    assert move in p["data"]["effect"]["effect"]
    assert "Hone Claws" not in json.dumps(p["data"])


@pytest.mark.parametrize("member", [TeamMember("ralts", ability="levitate"), TeamMember("ralts", moves=("surf",))])
def test_species_specific_team_combinations(db, member):
    with pytest.raises(ValueError, match="no recorded"):
        validate_team(db, resolve_game(db, "emerald"), PlaythroughContext(game="emerald", team=(member,)))


def test_competitive_illegality_and_damage():
    result = competitive.run("validate", format="gen3ou", team="Ralts\nAbility: Levitate\nEVs: 252 HP / 252 SpA / 4 SpD\n- Surf")
    assert not result["valid"]
    assert any("Levitate" in issue for issue in result["issues"])
    assert any("Surf" in issue for issue in result["issues"])
    result = competitive.run("damage", generation=3, attacker={"species": "Swampert", "level": 50}, defender={"species": "Tyranitar", "level": 50}, move="Earthquake")
    assert result["range"][1] >= result["range"][0] > 0


def test_item_names_do_not_switch_game(db):
    assert mentioned_games(db, "Where can I find a Red Shard in Emerald?") == ["emerald"]
    assert mentioned_games(db, "What does a Sun Stone do?") == []


def test_dlc_is_bound_to_base_version():
    from rotom_dex.chat.session import game_context

    assert game_context("the-teal-mask-scarlet")["base_game"] == "scarlet"
    with pytest.raises(ValueError, match="DLC access"):
        game_context("violet", ["the-teal-mask-scarlet"])


def test_reviewed_knowledge_keeps_remakes_separate(db, tmp_path):
    from rotom_dex.services import content

    diamond = content.search(resolve_game(db, "diamond"), "Where is exp share?")
    assert "35" in diamond[0]["claim"]
    assert content.search(resolve_game(db, "brilliant-diamond"), "Where is exp share?") == []
    assert content.search(resolve_game(db, "diamond"), "Where is exp share?", spoiler="none") == []
    report = content.audit(db)
    assert not report["errors"] and not report["conflicts"]
    assert all(not g["deep_support"] for g in report["games"])
    content.publish(db, tmp_path)
    with pytest.raises(ValueError, match="immutable"):
        content.publish(db, tmp_path)


def test_story_shortlist_has_moves_and_game_routes(db):
    from rotom_dex.services.story import recommend

    scope = resolve_game(db, "emerald")
    result = recommend(db, scope, PlaythroughContext(game="emerald", team=(TeamMember("treecko"),)), level=20)
    assert 0 < len(result["recommendations"]) <= 3
    for candidate in result["recommendations"]:
        assert candidate["pokemon"] != "treecko"
        assert candidate["routes"] and candidate["moves"]
        assert all(r["derived"]["status"] in {"reachable", "unknown"} for r in candidate["routes"])


def test_content_conflicts_fail_the_cli_gate(seed_db, monkeypatch, capsys):
    from rotom_dex.cli import main
    from rotom_dex.services import content

    monkeypatch.setattr(content, "audit", lambda db: {"errors": [], "conflicts": [["fact-a", "fact-b"]]})
    assert main(["content-audit", "--db", str(seed_db)]) == 1
    assert "fact-a" in capsys.readouterr().out


def test_concurrency_limit_releases_per_key():
    from rotom_dex.chat import limits

    a = limits.acquire("same")
    b = limits.acquire("same")
    try:
        with pytest.raises(Exception, match="simultaneous"):
            limits.acquire("same")
        c = limits.acquire("other")
        limits.release(c)
    finally:
        limits.release(a)
        limits.release(b)
    c = limits.acquire("same")
    limits.release(c)


def test_key_header_requires_https_outside_localhost():
    from fastapi import HTTPException

    req = Request(
        {
            "type": "http",
            "headers": [(b"x-rotom-gemini-key", b"not-real")],
            "scheme": "http",
            "server": ("example.com", 80),
            "path": "/api/chat",
            "query_string": b"",
            "client": ("203.0.113.1", 40000),
        }
    )
    with pytest.raises(HTTPException, match="HTTPS"):
        deps.get_chat_config(req)
