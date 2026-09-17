"""Request-scoped read-only database connections, chat configuration and common query parameters."""

from __future__ import annotations

import sqlite3
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import replace

from fastapi import Depends, HTTPException, Query, Request

from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.factory import build_provider, build_research
from rotom_dex.db.connection import connect
from rotom_dex.db.migrations import check_current
from rotom_dex.settings import DEFAULT_DB


def get_db() -> Iterator[sqlite3.Connection]:
    # One connection per request, and never shared between them. See `connect` for why the
    # same-thread guard has to be off here.
    db = connect(DEFAULT_DB, readonly=True, same_thread=False)
    try:
        check_current(db)
        yield db
    finally:
        db.close()


GameParam = Query(..., min_length=1, max_length=64, description="Exact game slug, e.g. emerald or red")
LimitParam = Query(50, ge=1, le=200)
OffsetParam = Query(0, ge=0)
QParam = Query(None, max_length=100, description="Case-insensitive substring of slug or name")


def get_chat_config(request: Request) -> ChatConfig:
    """Use only this visitor's sensitive header; never inherit an owner key."""
    config = ChatConfig.from_env()
    key = request.headers.get("x-rotom-gemini-key", "").strip()
    if len(key) > 256 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise HTTPException(400, "Invalid Gemini key format")
    if key and request.url.scheme != "https" and (not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}):
        raise HTTPException(400, "Gemini keys require HTTPS outside localhost.")
    # Public requests NEVER inherit a deployment credential or scripted provider.
    return replace(config, provider="gemini", api_key=key or None, research_enabled=True, max_research_calls=2)


def get_chat_provider(config: ChatConfig = Depends(get_chat_config)):
    """None rather than an exception when no provider is configured.

    Raising here would happen during dependency resolution, which runs alongside body validation, so
    a malformed request would report the outage instead of the malformed field. The route raises.
    """
    if not config.enabled:
        return None
    return build_provider(config)


def get_research_provider(config: ChatConfig = Depends(get_chat_config)):
    return build_research(config)


# Per-client request times, oldest first. In-process and therefore per-worker: enough to stop one
# browser looping on the chat endpoint, and honest about not being a distributed quota.
_HITS: dict[str, deque[float]] = {}


def rate_limit(request: Request, config: ChatConfig) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _HITS.setdefault(client, deque())
    while hits and now - hits[0] > config.rate_window_s:
        hits.popleft()
    if len(hits) >= config.rate_limit:
        retry = int(config.rate_window_s - (now - hits[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many chat requests; try again in {retry}s. The Pokedex and team tools are not rate limited.",
            headers={"Retry-After": str(retry)},
        )
    hits.append(now)
