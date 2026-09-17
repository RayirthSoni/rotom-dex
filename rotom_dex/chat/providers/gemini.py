"""Gemini, over the REST API with the standard library.

`urllib` rather than an SDK, matching `rotom_dex/ingestion/fetch.py`, so the project keeps its three
runtime dependencies and this adapter stays small enough to read in one sitting.

Two shape rules drive the code: Gemini will not accept a tool list and a response schema in the same
request, and its schema dialect is an OpenAPI subset that rejects `additionalProperties`. Both are
handled here so the rest of the subsystem can speak one vocabulary.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field

from rotom_dex.chat.errors import ProviderProtocolError, ProviderTimeout, ProviderUnavailable
from rotom_dex.chat.http import post_json
from rotom_dex.chat.protocols import ProviderReply, ToolCall, ToolSpec, Turn

# Keys the OpenAPI subset understands. Everything else is dropped rather than sent and rejected.
SCHEMA_KEYS = {"type", "format", "description", "nullable", "enum", "maxItems", "minItems", "properties", "required", "items"}


def to_gemini_schema(schema: dict) -> dict:
    out = {}
    for key, value in schema.items():
        if key not in SCHEMA_KEYS:
            continue
        if key == "properties":
            out[key] = {k: to_gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            out[key] = to_gemini_schema(value)
        else:
            out[key] = value
    return out


def _parts(turn: Turn) -> list[dict]:
    if turn.provider_parts:
        return list(turn.provider_parts)
    if turn.tool_calls:
        return [{"functionCall": {"name": c.name, "args": c.arguments or {}}} for c in turn.tool_calls]
    if turn.tool_results:
        return [
            {"functionResponse": {**({"id": r.call_id} if not r.call_id.startswith("rotom-generated-") else {}), "name": r.name, "response": {"content": r.content}}}
            for r in turn.tool_results
        ]
    return [{"text": turn.text}]


def _contents(turns: Sequence[Turn]) -> list[dict]:
    # Gemini has two roles. A tool result is sent back as a user turn carrying functionResponse parts.
    return [{"role": "model" if t.role == "model" else "user", "parts": _parts(t)} for t in turns]


@dataclass
class GeminiProvider:
    api_key: str = field(repr=False)
    model: str
    base_url: str
    name: str = "gemini"
    max_output_tokens: int = 2048
    opener: object = field(default=None, repr=False)

    def complete(self, *, system: str, turns: Sequence[Turn], tools: Sequence[ToolSpec], response_schema: dict | None, timeout_s: float) -> ProviderReply:
        if not self.api_key:
            raise ProviderUnavailable("no Gemini API key is configured")
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": _contents(turns),
            "generationConfig": {"maxOutputTokens": self.max_output_tokens, "temperature": 0.2},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [{"name": t.name, "description": t.description, "parameters": to_gemini_schema(t.parameters)} for t in tools]}]
        if response_schema is not None:
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseSchema"] = to_gemini_schema(response_schema)

        url = f"{self.base_url.rstrip('/')}/v1beta/models/{self.model}:generateContent"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            payload = post_json(request, timeout_s=timeout_s, opener=self.opener)
        except TimeoutError as exc:
            raise ProviderTimeout(f"Gemini did not respond within {timeout_s:.0f}s") from exc
        except urllib.error.HTTPError as exc:
            # Inspect only known machine-readable reasons; never expose provider bodies,
            # which can echo request data or credentials.
            reasons = set()
            try:
                error = json.loads(exc.read(65536)).get("error", {})
                reasons = {d.get("reason") for d in error.get("details", []) if isinstance(d, dict)}
            except (ValueError, AttributeError, TypeError):
                pass
            if reasons & {"API_KEY_INVALID", "API_KEY_EXPIRED"}:
                raise ProviderUnavailable("Google rejected this Gemini API key. Check or replace the key in Google AI Studio, then reconnect.") from None
            if exc.code in (401, 403):
                raise ProviderUnavailable("Google denied access. Check the key's API restrictions and Gemini API permissions in its Google Cloud project.") from None
            if exc.code == 404:
                raise ProviderUnavailable(f"The configured model ({self.model}) is not available to this key. Check model access or ROTOM_CHAT_MODEL on the server.") from None
            if exc.code == 429:
                raise ProviderUnavailable("Gemini quota or rate limit reached. Check this key's project quota and billing in Google AI Studio, or retry later.") from None
            if exc.code in {500, 502, 503, 504}:
                raise ProviderUnavailable(
                    f"Google's Gemini service is temporarily unavailable (HTTP {exc.code}) after bounded retries. This is not an invalid-key error. Please try again shortly."
                ) from None
            raise ProviderUnavailable(f"Gemini returned HTTP {exc.code}; check model access and request configuration") from None
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderUnavailable(f"Gemini could not be reached: {exc}") from exc
        except ValueError as exc:
            raise ProviderProtocolError(f"Gemini returned a body that is not JSON: {exc}") from exc
        try:
            return self._reply(payload)
        except (TypeError, AttributeError, KeyError) as exc:
            raise ProviderProtocolError("Gemini returned a malformed response") from exc

    def _reply(self, payload: dict) -> ProviderReply:
        candidates = payload.get("candidates") or []
        if not candidates:
            block = (payload.get("promptFeedback") or {}).get("blockReason")
            if block:
                return ProviderReply(finish_reason="safety", model=self.model)
            raise ProviderProtocolError("Gemini returned no candidates")
        candidate = candidates[0]
        reason = str(candidate.get("finishReason", "STOP")).upper()
        text, calls = "", []
        for index, part in enumerate((candidate.get("content") or {}).get("parts") or []):
            if "text" in part and not part.get("thought"):
                text += part["text"]
            call = part.get("functionCall")
            if call:
                calls.append(ToolCall(id=call.get("id") or f"rotom-generated-{index}", name=call.get("name", ""), arguments=call.get("args") or {}))
        finish = {"SAFETY": "safety", "MAX_TOKENS": "length", "RECITATION": "safety"}.get(reason, "tool_calls" if calls else "stop")
        usage = payload.get("usageMetadata") or {}
        return ProviderReply(
            text=text,
            tool_calls=tuple(calls),
            finish_reason=finish,
            usage={k: v for k, v in usage.items() if isinstance(v, int)},
            model=self.model,
            provider_parts=tuple((candidate.get("content") or {}).get("parts") or []),
        )
