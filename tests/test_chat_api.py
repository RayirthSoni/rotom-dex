"""The chat endpoint at the HTTP boundary.

The load-bearing test here is the outage one: when the model is gone, `/api/chat` must say so and
every other endpoint must carry on. That is the difference between an optional feature and a
dependency.
"""

from __future__ import annotations

import json

import pytest

from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.errors import ProviderTimeout, ProviderUnavailable
from rotom_dex.chat.protocols import ProviderReply, ToolCall
from rotom_dex.chat.providers.scripted import FailingProvider, ScriptedProvider

BODY = {
    "context": {"game": "emerald", "completed_milestones": ["stone-badge"], "closed_world": ["milestones"]},
    "message": "Who can I catch right now?",
}


def answer_json(**overrides) -> str:
    payload = {"prose": "ok", "facts": [], "assumptions": [], "recommendations": [], "cards": [], "actions": [], "references": [], "abstained": False}
    return json.dumps({**payload, **overrides})


@pytest.fixture
def scripted(client):
    """Override the provider dependency, which is FastAPI's own seam for exactly this."""
    from rotom_dex.api import deps
    from rotom_dex.api.app import app

    holder: dict = {}

    def install(*replies, config: ChatConfig | None = None):
        provider = ScriptedProvider(script=list(replies))
        holder["provider"] = provider
        cfg = config or ChatConfig.from_env({"ROTOM_CHAT_PROVIDER": "scripted"})
        app.dependency_overrides[deps.get_chat_provider] = lambda: provider
        app.dependency_overrides[deps.get_chat_config] = lambda: cfg
        app.dependency_overrides[deps.get_research_provider] = lambda: None
        return provider

    yield install
    app.dependency_overrides.clear()


def test_status_reports_no_provider_without_a_credential(client):
    body = client.get("/api/chat/status").json()
    assert body["enabled"] is False
    assert "Pokedex" in body["reason"]
    assert body["limits"]["max_message_chars"] > 0


def test_chat_returns_the_usual_envelope(client, scripted):
    answer = answer_json(recommendations=[{"text": "Look around Route 102", "rationale": "it is open to you", "status": "unknown"}])
    scripted(ProviderReply(text=""), ProviderReply(text=answer))
    body = client.post("/api/chat", json=BODY).json()
    assert {"game", "snapshot_id", "coverage_status", "coverage", "data", "assumptions", "evidence"} <= set(body)
    assert body["game"]["slug"] == "emerald"
    assert body["data"]["abstained"] is True  # ungrounded route advice is no longer accepted
    assert body["data"]["tools_used"] == []


def test_an_answer_with_nothing_in_it_counts_as_an_abstention(client, scripted):
    scripted(ProviderReply(text=""), ProviderReply(text=answer_json(prose="I am not sure.")))
    assert client.post("/api/chat", json=BODY).json()["data"]["abstained"] is True


def test_a_provider_outage_is_a_503_and_nothing_else_breaks(client, scripted):
    """The explicit promise: the Dex and team tools do not depend on the model."""
    from rotom_dex.api import deps
    from rotom_dex.api.app import app

    scripted(ProviderReply(text=""))
    app.dependency_overrides[deps.get_chat_provider] = lambda: FailingProvider(error=ProviderUnavailable("provider is down"))

    assert client.post("/api/chat", json=BODY).status_code == 503
    assert client.get("/api/pokemon/ralts", params={"game": "emerald"}).status_code == 200
    assert client.post("/api/team/analyze", json={"context": {"game": "emerald", "team": [{"pokemon": "treecko"}]}}).status_code == 200
    assert client.post("/api/boss/prepare", json={"context": {"game": "emerald"}, "battle": "roxanne"}).status_code == 200
    assert client.get("/api/milestones", params={"game": "emerald"}).status_code == 200


def test_a_provider_timeout_is_a_504(client, scripted):
    from rotom_dex.api import deps
    from rotom_dex.api.app import app

    scripted(ProviderReply(text=""))
    app.dependency_overrides[deps.get_chat_provider] = lambda: FailingProvider(error=ProviderTimeout("too slow"))
    assert client.post("/api/chat", json=BODY).status_code == 504


def test_no_configured_provider_is_a_503_not_a_crash(client):
    assert client.post("/api/chat", json=BODY).status_code == 503


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "message": "x" * 3000},
        {**BODY, "message": ""},
        {**BODY, "history": [{"role": "nobody", "text": "hi"}]},
        {**BODY, "unexpected": 1},
        {"message": "no context"},
    ],
)
def test_malformed_bodies_are_422_before_anything_else(client, scripted, body):
    scripted(ProviderReply(text=""), ProviderReply(text=answer_json()))
    assert client.post("/api/chat", json=body).status_code == 422


def test_an_unimported_game_abstains_rather_than_erroring(client, scripted):
    scripted(ProviderReply(text=""), ProviderReply(text=answer_json()))
    response = client.post("/api/chat", json={**BODY, "context": {"game": "colosseum"}})
    assert response.status_code == 200
    assert response.json()["data"] is None


def test_the_answer_resolves_the_evidence_it_cites(client, scripted):
    """Facts carry a singular `evidence_id`, which is what lets the envelope resolve them."""
    from rotom_dex.api import deps
    from rotom_dex.api.app import app
    from rotom_dex.chat.tools import REGISTRY
    from rotom_dex.repositories.common import resolve_game
    from rotom_dex.services.context import PlaythroughContext

    session = deps.get_db()
    db = next(session)
    scope = resolve_game(db, "emerald")
    payload = REGISTRY["dex_lookup"].handler(db, scope, PlaythroughContext(game="emerald"), {"pokemon": "zigzagoon"})
    from rotom_dex.chat.evidence import EvidenceLedger
    from rotom_dex.chat.orchestrator import compact

    fact = next(f for f in EvidenceLedger().bind(compact(payload), "dex_lookup", "emerald") if f["label"] == "type")
    evidence_id = fact["evidence_id"]
    session.close()

    scripted(
        ProviderReply(tool_calls=(ToolCall("c1", "dex_lookup", {"pokemon": "zigzagoon"}),), finish_reason="tool_calls"),
        ProviderReply(text=""),
        ProviderReply(text=answer_json(facts=[{k: fact[k] for k in ("fact_id", "claim", "evidence_id", "tool")}])),
    )
    body = client.post("/api/chat", json=BODY).json()
    assert [f["evidence_id"] for f in body["data"]["facts"]] == [evidence_id]
    assert evidence_id in {e["id"] for e in body["evidence"]}
    assert body["evidence"][0]["sources"], "the cited evidence resolves to real sources"
    app.dependency_overrides.clear()


def test_rate_limiting_protects_only_the_chat_endpoint(client, scripted):
    config = ChatConfig.from_env({"ROTOM_CHAT_PROVIDER": "scripted", "ROTOM_CHAT_RATE_LIMIT": "3"})
    statuses = []
    for _ in range(5):
        scripted(ProviderReply(text=""), ProviderReply(text=answer_json()), config=config)
        statuses.append(client.post("/api/chat", json=BODY).status_code)
    assert 429 in statuses, f"expected a rate limit, saw {statuses}"
    assert client.get("/api/pokemon", params={"game": "emerald", "limit": 1}).status_code == 200
