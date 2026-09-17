import io
import json
import urllib.error

import pytest

from rotom_dex.chat import http
from rotom_dex.chat.errors import ProviderUnavailable
from rotom_dex.chat.protocols import Turn
from rotom_dex.chat.providers.gemini import GeminiProvider


def error(code, body=None):
    return urllib.error.HTTPError("https://example.invalid", code, "upstream failure", {}, io.BytesIO(json.dumps(body or {}).encode()))


def invoke(opener, timeout=10):
    return GeminiProvider("test-secret", "gemini-test", "https://example.invalid", opener=opener).complete(
        system="Reply OK", turns=[Turn("user", text="Test")], tools=[], response_schema=None, timeout_s=timeout
    )


def test_temporary_failure_retries_inside_original_budget(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(http.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    monkeypatch.setattr(http.random, "uniform", lambda *a: 0)
    timeouts = []

    def opener(request, timeout):
        timeouts.append(timeout)
        if len(timeouts) < 3:
            raise error(503)
        return io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode())

    assert invoke(opener).text == "OK"
    assert timeouts == [10, 9, 7]


def test_persistent_outage_is_clear_and_never_echoes_response(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda delay: None)
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        raise error(503, {"error": {"message": "test-secret"}})

    with pytest.raises(ProviderUnavailable, match="temporarily unavailable") as caught:
        invoke(opener)
    assert len(calls) == 3 and "test-secret" not in str(caught.value)


def test_invalid_key_is_not_retried_and_has_specific_message():
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        raise error(400, {"error": {"message": "test-secret", "details": [{"reason": "API_KEY_INVALID"}]}})

    with pytest.raises(ProviderUnavailable, match="Google rejected this Gemini API key") as caught:
        invoke(opener)
    assert len(calls) == 1 and "test-secret" not in str(caught.value)
