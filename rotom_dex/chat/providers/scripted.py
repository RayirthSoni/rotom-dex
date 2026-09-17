"""A provider that replays a fixed script, and records exactly what it was shown.

This ships with the package rather than living in the tests, for two reasons. It makes the whole
stack runnable with no credential (`ROTOM_CHAT_PROVIDER=scripted`), and `calls` is the only place
that can prove a spoiler was never *shown* to a model, as opposed to a model being asked not to
repeat it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from rotom_dex.chat.errors import ChatError, ProviderProtocolError
from rotom_dex.chat.protocols import ProviderReply, ToolSpec, Turn


@dataclass
class ScriptedProvider:
    script: list[ProviderReply] = field(default_factory=list)
    name: str = "scripted"
    model: str = "scripted"
    calls: list[dict] = field(default_factory=list)

    def complete(self, *, system: str, turns: Sequence[Turn], tools: Sequence[ToolSpec], response_schema: dict | None, timeout_s: float) -> ProviderReply:
        self.calls.append({"system": system, "turns": list(turns), "tools": list(tools), "response_schema": response_schema, "timeout_s": timeout_s})
        if not self.script:
            raise ProviderProtocolError("scripted provider: script exhausted")
        return self.script.pop(0)


@dataclass
class FailingProvider:
    """Raises a chosen failure, for the outage paths."""

    error: ChatError
    name: str = "failing"
    model: str = "failing"
    calls: list[dict] = field(default_factory=list)

    def complete(self, **kwargs) -> ProviderReply:
        self.calls.append(kwargs)
        raise self.error
