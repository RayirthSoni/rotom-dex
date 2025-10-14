from typing import List, Sequence

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pytest
from fastapi.testclient import TestClient

import service


class DummyLLM:
    def __init__(self, reply: str = "assistant reply") -> None:
        self.reply = reply
        self.prompts: List[str] = []

    def generate(self, prompt: str, *, stream: bool = False) -> str:
        self.prompts.append(prompt)
        return self.reply
def build_manager(reply: str = "assistant reply") -> service.ConversationManager:
    backend = DummyLLM(reply=reply)
    memory = service.ConversationMemory(max_messages=6)
    manager = service.ConversationManager(llm_backend=backend, memory=memory)

    def retrieval_tool(
        session_id: str, history: Sequence[service.MemoryMessage], message: str
    ) -> service.ToolResult:
        assert session_id
        assert isinstance(history, list)
        assert message
        return service.ToolResult(content="Context snippet", citations=["doc1", "doc2"])

    manager.register_tool("retrieval", retrieval_tool)
    return manager


def test_chat_endpoint_returns_mock_response(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = build_manager()
    service.app.state.conversation_manager = manager
    client = TestClient(service.app)

    response = client.post(
        "/chat", json={"session_id": "session-1", "message": "hello"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-1"
    assert payload["citations"] == ["doc1", "doc2"]
    assert payload["reply"].endswith("Sources: doc1, doc2")

    history = manager.memory.get("session-1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "hello"
    assert history[1].role == "assistant"
    assert history[1].citations == ["doc1", "doc2"]
    assert manager.llm_backend.prompts, "LLM was not invoked"
    assert "Context snippet" in manager.llm_backend.prompts[0]


def test_chat_endpoint_rejects_empty_message() -> None:
    manager = build_manager()
    service.app.state.conversation_manager = manager
    client = TestClient(service.app)

    response = client.post("/chat", json={"session_id": "s2", "message": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "message must not be empty"


def test_memory_trims_to_limit() -> None:
    backend = DummyLLM()
    memory = service.ConversationMemory(max_messages=3)
    manager = service.ConversationManager(llm_backend=backend, memory=memory)
    service.app.state.conversation_manager = manager
    client = TestClient(service.app)

    for idx in range(3):
        response = client.post(
            "/chat", json={"session_id": "trim", "message": f"m{idx}"}
        )
        assert response.status_code == 200

    history = manager.memory.get("trim")
    assert len(history) == 3
    contents = [item.content for item in history]
    assert "m0" not in contents
    assert history[-2].role == "user"
    assert history[-2].content == "m2"
    assert history[-1].role == "assistant"
