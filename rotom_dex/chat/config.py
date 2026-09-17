"""Chat configuration, read per request.

`settings.py` binds its values at import time, which is why `tests/conftest.py` has to rebind
`DEFAULT_DB` in three separate modules. Nothing here repeats that: `from_env` reads the environment
inside its body and the API constructs a config per request, so a test sets an environment variable
or overrides a dependency and is done. No chat setting may ever be added to `settings.py`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


def _int(env: Mapping[str, str], key: str, fallback: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def _float(env: Mapping[str, str], key: str, fallback: float) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback


@dataclass(frozen=True)
class ChatConfig:
    provider: str = "gemini"
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL

    research_enabled: bool = False
    research_model: str | None = None

    # Bounds. Every one is enforced in code; none is merely requested of the model.
    max_turns: int = 4
    max_tool_calls: int = 8
    max_calls_per_tool: int = 3
    max_research_calls: int = 2
    provider_timeout_s: float = 20.0
    research_timeout_s: float = 15.0
    deadline_s: float = 45.0
    max_tool_result_bytes: int = 24_000
    max_total_tool_bytes: int = 120_000
    max_research_chars: int = 4_000
    max_message_chars: int = 2_000
    max_history_turns: int = 12
    max_prose_chars: int = 1_200
    max_output_tokens: int = 2_048

    # Requests per window, per client, on the chat endpoint alone.
    rate_limit: int = 20
    rate_window_s: float = 60.0

    scripted_replies: tuple = field(default=(), compare=False, repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ChatConfig:
        env = os.environ if env is None else env
        research_calls = _int(env, "ROTOM_CHAT_MAX_RESEARCH_CALLS", 2)
        enabled = env.get("ROTOM_CHAT_RESEARCH", "0") == "1"
        return cls(
            provider=env.get("ROTOM_CHAT_PROVIDER", "gemini"),
            model=env.get("ROTOM_CHAT_MODEL", DEFAULT_MODEL),
            api_key=env.get("ROTOM_GEMINI_API_KEY") or None,
            base_url=env.get("ROTOM_GEMINI_BASE_URL", DEFAULT_BASE_URL),
            research_enabled=enabled,
            research_model=env.get("ROTOM_RESEARCH_MODEL") or None,
            max_turns=_int(env, "ROTOM_CHAT_MAX_TURNS", 4),
            max_tool_calls=_int(env, "ROTOM_CHAT_MAX_TOOL_CALLS", 8),
            max_calls_per_tool=_int(env, "ROTOM_CHAT_MAX_CALLS_PER_TOOL", 3),
            max_research_calls=research_calls if enabled else 0,
            provider_timeout_s=_float(env, "ROTOM_CHAT_PROVIDER_TIMEOUT", 20.0),
            research_timeout_s=_float(env, "ROTOM_CHAT_RESEARCH_TIMEOUT", 15.0),
            deadline_s=_float(env, "ROTOM_CHAT_DEADLINE", 45.0),
            max_message_chars=_int(env, "ROTOM_CHAT_MAX_MESSAGE_CHARS", 2_000),
            max_history_turns=_int(env, "ROTOM_CHAT_MAX_HISTORY", 12),
            rate_limit=_int(env, "ROTOM_CHAT_RATE_LIMIT", 20),
            rate_window_s=_float(env, "ROTOM_CHAT_RATE_WINDOW", 60.0),
        )

    @property
    def enabled(self) -> bool:
        """Whether a request could reach a model at all."""
        if self.provider == "scripted":
            return True
        return bool(self.api_key)

    @property
    def unavailable_reason(self) -> str:
        if self.enabled:
            return ""
        return (
            f"No credential is configured for the '{self.provider}' chat provider, so Rotom cannot answer. "
            "The Pokedex, team analysis and boss preparation do not use the model and are unaffected."
        )

    def status(self) -> dict:
        """What the web application needs to decide whether to offer the Ask tab."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model if self.enabled else None,
            "research_enabled": self.research_enabled,
            "reason": self.unavailable_reason,
            "limits": {
                "max_message_chars": self.max_message_chars,
                "max_history_turns": self.max_history_turns,
                "max_tool_calls": self.max_tool_calls,
                "deadline_s": self.deadline_s,
            },
        }
