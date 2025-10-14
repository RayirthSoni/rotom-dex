"""Lightweight moderation filters used by the chatbot orchestrator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Pattern


class ModerationException(RuntimeError):
    """Raised when user input violates moderation policies."""


@dataclass
class BaseFilter:
    """Base moderation filter that blocks messages containing banned patterns."""

    patterns: Iterable[str]
    description: str

    def __post_init__(self) -> None:
        self._compiled: List[Pattern[str]] = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.patterns
        ]

    def validate(self, message: str) -> None:
        for regex in self._compiled:
            if regex.search(message):
                raise ModerationException(self.description)


class ToxicityFilter(BaseFilter):
    """Rejects messages that contain toxic or hateful vocabulary."""

    def __init__(self, extra_patterns: Iterable[str] | None = None):
        patterns = [
            r"\bhate\b",
            r"\bkys\b",
            r"\bidiot\b",
            r"\bviolent\b",
        ]
        if extra_patterns:
            patterns.extend(extra_patterns)
        super().__init__(patterns=patterns, description="Toxic language detected.")


class JailbreakFilter(BaseFilter):
    """Prevents prompt-injection and jailbreak attempts."""

    def __init__(self, extra_patterns: Iterable[str] | None = None):
        patterns = [
            r"ignore all (previous|prior) instructions",
            r"(?:pretend|role[- ]?play) you are an evil ai",
            r"(?:disable|turn off) safety",
            r"system override",
        ]
        if extra_patterns:
            patterns.extend(extra_patterns)
        super().__init__(
            patterns=patterns,
            description="Potential jailbreak attempt blocked.",
        )


class ModerationPipeline:
    """Executes a sequence of moderation filters before routing."""

    def __init__(self, filters: Iterable[BaseFilter]):
        self.filters = list(filters)

    def validate(self, message: str) -> None:
        for filter_ in self.filters:
            filter_.validate(message)
