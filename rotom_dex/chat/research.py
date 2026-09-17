"""Optional web research, behind its own replaceable interface.

The search runs as a *separate* call with no custom tools, and its answer comes back to this code
rather than straight into the main conversation. That is the whole point: retrieved text passes
through the sanitiser and is re-wrapped as untrusted evidence before it reaches the model, so a page
that says "ignore your instructions" is data, not a turn.

Nothing here is ever written to the database. A web citation is labelled `unreviewed` and can never
become the evidence behind a fact.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from rotom_dex.chat.errors import ResearchUnavailable
from rotom_dex.chat.http import post_json
from rotom_dex.chat.protocols import ResearchCitation, ResearchResult

INSTRUCTION = (
    "Answer the question factually and say which exact Pokemon game version each statement applies to. "
    "If a claim differs between versions, say so. If you are not sure, say you are not sure."
)


@dataclass
class NullResearch:
    """What is used when research is switched off. Present so the loop has no special case."""

    name: str = "disabled"

    def search(self, *, query: str, timeout_s: float) -> ResearchResult:
        raise ResearchUnavailable("web research is not enabled on this server")


@dataclass
class GeminiGroundedSearch:
    """Gemini's own search grounding, run tool-less so the result returns to us first."""

    api_key: str = field(repr=False)
    model: str
    base_url: str
    name: str = "gemini-google-search"
    opener: object = field(default=None, repr=False)

    def search(self, *, query: str, timeout_s: float) -> ResearchResult:
        if not self.api_key:
            raise ResearchUnavailable("no credential is configured for web research")
        body = {
            "systemInstruction": {"parts": [{"text": INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
        }
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
            raise ResearchUnavailable(f"web research timed out after {timeout_s:.0f}s") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ResearchUnavailable(f"web research failed: {exc}") from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            raise ResearchUnavailable("web research returned nothing")
        candidate = candidates[0]
        text = "".join(part.get("text", "") for part in (candidate.get("content") or {}).get("parts") or [])
        citations = []
        grounding = candidate.get("groundingMetadata") or {}
        for chunk in grounding.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            if web.get("uri"):
                citations.append(ResearchCitation(url=web["uri"], title=web.get("title", "")))
        passages = []
        for support in grounding.get("groundingSupports") or []:
            segment = (support.get("segment") or {}).get("text", "")
            indices = support.get("groundingChunkIndices") or []
            urls = []
            chunks = grounding.get("groundingChunks") or []
            for i in indices:
                if isinstance(i, int) and 0 <= i < len(chunks):
                    uri = (chunks[i].get("web") or {}).get("uri", "")
                    if uri.startswith("https://"):
                        urls.append(uri)
            if segment and urls:
                passages.append({"text": segment, "urls": urls})
        return ResearchResult(query=query, text=text, citations=tuple(citations), provider=self.name, passages=tuple(passages))
