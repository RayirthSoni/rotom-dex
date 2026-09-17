"""The chat endpoint.

POST because the body carries a playthrough held in the player's browser, not a resource identifier,
and the same envelope every other endpoint returns, so the client's existing handling applies with no
special case. Nothing here writes: proposed actions come back for the player to confirm.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from rotom_dex.api.deps import get_chat_config, get_chat_provider, get_db, get_research_provider, rate_limit
from rotom_dex.api.requests import ChatIn
from rotom_dex.api.schemas import ChatStatus, Envelope
from rotom_dex.chat import limits, orchestrator
from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.errors import ProviderUnavailable
from rotom_dex.repositories.common import envelope, resolve_game, unsupported
from rotom_dex.services.context import validate

router = APIRouter()

TOOL_FEATURES = ("progression", "boss-teams", "encounters", "location-gates", "evolution", "learnsets", "item-acquisition")


@router.get("/chat/status", response_model=ChatStatus)
def chat_status(config: ChatConfig = Depends(get_chat_config)):
    """Whether Rotom can answer at all. The rest of the application never depends on this."""
    return config.status()


@router.post("/chat", response_model=Envelope)
def chat(
    body: ChatIn,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    config: ChatConfig = Depends(get_chat_config),
    provider=Depends(get_chat_provider),
    research=Depends(get_research_provider),
):
    """One grounded exchange: typed tools over the reviewed database, then a validated answer."""
    if provider is None:
        raise ProviderUnavailable(config.unavailable_reason)
    rate_limit(request, config)
    scope = resolve_game(db, body.context.game)
    if not scope.imported:
        return unsupported(db, scope)
    ctx = body.context.to_domain()
    warnings = validate(db, scope, ctx)
    lease = limits.acquire(config.api_key)
    try:
        result = orchestrator.answer(
            db,
            scope,
            ctx,
            message=body.message,
            history=[turn.model_dump() for turn in body.history],
            provider=provider,
            research=research,
            config=config,
        )
    finally:
        limits.release(lease)
    assumptions = [a["text"] for a in result.get("assumptions", []) if isinstance(a, dict) and a.get("text")]
    return envelope(
        db,
        scope,
        result,
        features=TOOL_FEATURES,
        include_evidence=True,
        assumptions=[*assumptions, *warnings],
    )
