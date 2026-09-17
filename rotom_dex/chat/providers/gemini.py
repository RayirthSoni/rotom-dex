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
    if turn.tool_calls:
        return [{"functionCall": {"name": c.name, "args": c.arguments or {}}} for c in turn.tool_calls]
    if turn.tool_results:
        return [{"functionResponse": {"name": r.name, "response": {"content": r.content}}} for r in turn.tool_results]
    return [{"text": turn.text}]


def _contents(turns: Sequence[Turn]) -> list[dict]:
    # Gemini has two roles. A tool result is sent back as a user turn carrying functionResponse parts.
    return [{"role": "model" if t.role == "model" else "user", "parts": _parts(t)} for t in turns]


@dataclass
class GeminiProvider:
    api_key: str
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
            opener = self.opener or urllib.request.urlopen
            with opener(request, timeout=timeout_s) as response:
                payload = json.loads(response.read().decode())
        except TimeoutError as exc:
            raise ProviderTimeout(f"Gemini did not respond within {timeout_s:.0f}s") from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200] if hasattr(exc, "read") else ""
            if exc.code in (401, 403):
                raise ProviderUnavailable("Gemini rejected the configured credential") from exc
            if exc.code == 429:
                raise ProviderUnavailable("Gemini rate limit reached") from exc
            raise ProviderUnavailable(f"Gemini returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderUnavailable(f"Gemini could not be reached: {exc}") from exc
        except ValueError as exc:
            raise ProviderProtocolError(f"Gemini returned a body that is not JSON: {exc}") from exc
        return self._reply(payload)

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
            if "text" in part:
                text += part["text"]
            call = part.get("functionCall")
            if call:
                calls.append(ToolCall(id=f"g{index}", name=call.get("name", ""), arguments=call.get("args") or {}))
        finish = {"SAFETY": "safety", "MAX_TOKENS": "length", "RECITATION": "safety"}.get(reason, "tool_calls" if calls else "stop")
        usage = payload.get("usageMetadata") or {}
        return ProviderReply(
            text=text,
            tool_calls=tuple(calls),
            finish_reason=finish,
            usage={k: v for k, v in usage.items() if isinstance(v, int)},
            model=self.model,
        )
