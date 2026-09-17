"""The seam between this application and whichever model answers.

Synchronous, because everything else here is: the read path is `sqlite3` and the endpoints are
plain `def` running in the threadpool. A provider is one method, so replacing the vendor means
writing one class.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    content: str


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "model" | "tool"
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    provider_parts: tuple[dict, ...] = ()


@dataclass(frozen=True)
class ProviderReply:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str = "stop"  # stop | tool_calls | length | safety
    provider_parts: tuple[dict, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


class ChatProvider(Protocol):
    name: str
    model: str

    def complete(
        self,
        *,
        system: str,
        turns: Sequence[Turn],
        tools: Sequence[ToolSpec],
        response_schema: dict | None,
        timeout_s: float,
    ) -> ProviderReply: ...


@dataclass(frozen=True)
class ResearchCitation:
    url: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class ResearchResult:
    query: str
    text: str
    citations: tuple[ResearchCitation, ...] = ()
    provider: str = ""
    passages: tuple[dict, ...] = ()


class ResearchProvider(Protocol):
    name: str

    def search(self, *, query: str, timeout_s: float) -> ResearchResult: ...
