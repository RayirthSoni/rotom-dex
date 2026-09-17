"""BYOK conversations; credentials and provider clients exist only for one request."""

from __future__ import annotations

import json
import queue
import threading
import time
from contextlib import closing
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from rotom_dex.api.deps import get_chat_config, get_db, rate_limit
from rotom_dex.api.requests import ConversationIn
from rotom_dex.chat import limits, orchestrator
from rotom_dex.chat.answer import abstention
from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.factory import build_provider, build_research
from rotom_dex.chat.protocols import Turn
from rotom_dex.chat.session import game_context, mentioned_games
from rotom_dex.db.connection import connect
from rotom_dex.repositories.common import envelope, resolve_game
from rotom_dex.services.context import PlaythroughContext, validate

router = APIRouter()


def respond(db, body: ConversationIn, config: ChatConfig, progress=None, cancelled=None):
    games = mentioned_games(db, body.message) or ([body.game or (body.context.game if body.context else None)] if body.game or body.context else [])
    if len(games) > 3:
        raise HTTPException(400, "Compare up to three games at a time so each receives a separate evidence check.")
    if not games:
        from rotom_dex.services.knowledge import search

        found = search(body.message, None)
        if found:
            answer = abstention("\n\n".join(x["text"] for x in found[:2]))
            answer.update(
                abstained=False, references=[{"kind": "web", "id": x["id"], "url": x["url"], "title": x["title"], "review_status": "reference-reviewed"} for x in found[:2]]
            )
            return envelope(db, None, {**answer, "version": 2, "games": [], "follow_ups": ["How does this work in my game?"]}, coverage=[])
        answer = abstention("Which Pokémon game are you playing? Choose a game above, or include it in your question.")
        return envelope(db, None, {**answer, "version": 2, "games": [], "clarification": "game"}, coverage=[])
    if body.mode == "competitive" and not body.format:
        return envelope(
            db,
            resolve_game(db, games[0]),
            {
                **abstention("Which competitive format? Choose a generation and format, including the regulation for official play."),
                "version": 2,
                "games": games,
                "clarification": "format",
            },
            coverage=[],
        )
    if not config.api_key:
        raise HTTPException(401, "Connect your own Gemini key to ask Rotom.")
    config = replace(config, research_enabled=body.research, max_research_calls=2 if body.research else 0)
    if body.mode == "competitive":
        from rotom_dex.services.competitive import formats

        known = next((f for f in formats() if f["id"] == body.format), None)
        if not known:
            raise HTTPException(400, "Choose an exact format from the competitive workshop.")
        if any(resolve_game(db, g).generation_id != known["generation"] for g in games):
            raise HTTPException(400, "The competitive format generation must match the selected game. Story acquisition and competitive rules are separate.")
    provider, research = build_provider(config), build_research(config)
    results = []
    deadline = time.monotonic() + config.deadline_s
    used_calls = 0
    used_research = 0
    for game in games:
        scope = resolve_game(db, game)
        ctx = body.context.to_domain() if body.context and body.context.game == game else PlaythroughContext(game=game, spoiler_level=body.spoiler_level)
        resolved_context = game_context(game, body.dlc_access or ctx.dlc_access)
        ctx = replace(ctx, dlc_access=tuple(resolved_context["dlc_access"]))
        validate(db, scope, ctx)
        if progress:
            progress(f"Looking up {scope.name}…")
        question = body.message
        if body.mode == "competitive":
            question = f"Competitive format: {body.format}. Validate competitive legality separately from story acquisition. {question}"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append({**abstention("The comparison exceeded the time limit. Ask about each game separately."), "game": game})
            break
        request_config = replace(
            config, deadline_s=remaining, max_tool_calls=max(0, config.max_tool_calls - used_calls), max_research_calls=max(0, config.max_research_calls - used_research)
        )
        result = orchestrator.answer(
            db,
            scope,
            ctx,
            message=question,
            history=[t.model_dump() for t in body.history],
            provider=provider,
            research=research,
            config=request_config,
            on_progress=progress,
            cancelled=cancelled,
        )
        used_calls += result.get("usage", {}).get("tool_calls", 0)
        used_research += result.get("usage", {}).get("research_calls", 0)
        result.update(game=game, game_context=resolved_context)
        results.append(result)
    answer = dict(results[0])
    if len(results) > 1:
        answer["prose"] = "\n\n".join(f"{r['game'].replace('-', ' ').title()}\n{r['prose']}" for r in results)
        for field in ("facts", "cards", "references", "assumptions"):
            answer[field] = [x for r in results for x in r.get(field, [])]
        answer["recommendations"] = [{**x, "text": f"{r['game'].replace('-', ' ').title()}: {x['text']}"} for r in results for x in r.get("recommendations", [])]
        answer["actions"] = []
        answer["abstained"] = all(r["abstained"] for r in results)
    answer["usage"] = {"tool_calls": used_calls, "research_calls": used_research}
    answer["game_contexts"] = [r["game_context"] for r in results if "game_context" in r]
    answer.update(version=2, games=games, format=body.format, mode=body.mode, follow_ups=["How can I get it?", "What would fit my team?", "Explain the requirements"])
    return envelope(db, resolve_game(db, games[0]), answer, coverage=[])


@router.post("/v2/chat")
def chat(body: ConversationIn, request: Request, db=Depends(get_db), config=Depends(get_chat_config)):
    rate_limit(request, config)
    lease = limits.acquire(config.api_key)
    try:
        return respond(db, body, config)
    finally:
        limits.release(lease)


@router.post("/v2/chat/stream")
def stream(body: ConversationIn, request: Request, db=Depends(get_db), config=Depends(get_chat_config)):
    rate_limit(request, config)
    if not config.api_key:
        raise HTTPException(401, "Connect your own Gemini key to ask Rotom.")
    lease = limits.acquire(config.api_key)
    path = db.execute("PRAGMA database_list").fetchone()[2]
    events = queue.Queue()
    stopped = threading.Event()

    def work():
        try:
            with closing(connect(path, readonly=True)) as connection:
                result = respond(connection, body, config, lambda message: events.put(("progress", {"message": message})), stopped)
                events.put(("answer", result))
        except Exception as exc:
            # Only domain errors are public; never echo provider requests or credentials.
            from rotom_dex.chat.errors import ChatError
            from rotom_dex.errors import NotFound, SemanticError

            detail = (
                exc.detail
                if isinstance(exc, HTTPException)
                else str(exc)
                if isinstance(exc, (ChatError, SemanticError, NotFound))
                else "Rotom could not finish this request. Please try again."
            )
            events.put(("error", {"detail": detail}))
        finally:
            events.put(("done", {}))
            limits.release(lease)

    threading.Thread(target=work, daemon=True).start()

    def generate():
        try:
            while True:
                try:
                    event, data = events.get(timeout=1)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if event == "done":
                    break
        finally:
            stopped.set()

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/chat/connect")
def connection(request: Request, config: ChatConfig = Depends(get_chat_config)):
    rate_limit(request, config)
    if not config.api_key:
        raise HTTPException(401, "Enter your own Gemini key.")
    lease = limits.acquire(config.api_key)
    try:
        build_provider(config).complete(system="Reply with OK.", turns=[Turn("user", text="Connection test")], tools=[], response_schema=None, timeout_s=10)
    finally:
        limits.release(lease)
    return {"connected": True, "model": config.model, "key_storage": "current-tab-memory"}
