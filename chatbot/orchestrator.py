"""Conversation orchestrator responsible for routing user requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from chatbot.filters import ModerationPipeline


Tool = Callable[[str], str]


@dataclass
class Orchestrator:
    """Routes natural language requests to specialised tools."""

    tools: Dict[str, Tool]
    moderation: Optional[ModerationPipeline] = None

    def route(self, message: str) -> str:
        """Return the name of the tool that should process ``message``."""
        normalized = message.lower()

        if self.moderation:
            self.moderation.validate(message)

        if any(keyword in normalized for keyword in ("gym", "battle strategy")):
            return "gym_strategy"
        if any(keyword in normalized for keyword in ("evolution", "evolve", "evolves")):
            return "evolution_lookup"
        if any(keyword in normalized for keyword in ("type", "weakness", "advantage")):
            return "metadata_lookup"
        return "general_search"

    def handle(self, message: str) -> str:
        """Route the message and execute the associated tool."""
        tool_name = self.route(message)
        tool = self.tools.get(tool_name)
        if tool is None:
            raise KeyError(f"No tool registered under '{tool_name}'")
        return tool(message)

    @classmethod
    def with_default_tools(
        cls, tools: Optional[Dict[str, Tool]] = None, filters: Optional[Iterable] = None
    ) -> "Orchestrator":
        """Create an orchestrator with simple default tool implementations."""

        def noop(_: str) -> str:
            return ""

        default_tools: Dict[str, Tool] = {
            "gym_strategy": noop,
            "evolution_lookup": noop,
            "metadata_lookup": noop,
            "general_search": noop,
        }
        if tools:
            default_tools.update(tools)

        moderation = ModerationPipeline(filters or []) if filters else None
        return cls(tools=default_tools, moderation=moderation)
