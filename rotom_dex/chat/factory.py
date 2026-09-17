"""Building a provider from a configuration. Per request, never at import."""

from __future__ import annotations

from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.errors import ProviderUnavailable
from rotom_dex.chat.protocols import ChatProvider, ResearchProvider
from rotom_dex.chat.providers.gemini import GeminiProvider
from rotom_dex.chat.providers.scripted import ScriptedProvider
from rotom_dex.chat.research import GeminiGroundedSearch, NullResearch


def build_provider(config: ChatConfig) -> ChatProvider:
    if config.provider == "scripted":
        return ScriptedProvider(script=list(config.scripted_replies))
    if config.provider == "gemini":
        if not config.api_key:
            raise ProviderUnavailable(config.unavailable_reason)
        return GeminiProvider(api_key=config.api_key, model=config.model, base_url=config.base_url, max_output_tokens=config.max_output_tokens)
    raise ProviderUnavailable(f"Unknown chat provider '{config.provider}'.")


def build_research(config: ChatConfig) -> ResearchProvider | None:
    if not config.research_enabled:
        return None
    if config.provider == "gemini" and config.api_key:
        return GeminiGroundedSearch(api_key=config.api_key, model=config.research_model or config.model, base_url=config.base_url)
    return NullResearch()
