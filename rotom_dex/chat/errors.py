"""What can go wrong between the question and the answer, and how each failure should read.

The distinction that matters: a provider that is down is a 503 and the rest of the application
keeps working, while a model that answered badly is a 200 carrying an abstention. Confusing the
two would either hide an outage or turn "I don't know" into an error page.
"""

from __future__ import annotations


class ChatError(Exception):
    """Base for every failure inside the chat subsystem."""


class ProviderUnavailable(ChatError):
    """No credential, refused connection, or an upstream failure that retrying did not fix."""


class ProviderTimeout(ChatError):
    """The provider did not answer inside the configured deadline."""


class ProviderRefused(ChatError):
    """The provider declined to answer. Becomes an abstention, not an error."""


class ProviderProtocolError(ChatError):
    """The provider returned something that is not a usable answer."""


class BudgetExceeded(ChatError):
    """A configured bound was hit: tool rounds, tool calls, bytes or wall clock."""


class ResearchUnavailable(ChatError):
    """Optional web research failed. Never escapes the tool loop."""
