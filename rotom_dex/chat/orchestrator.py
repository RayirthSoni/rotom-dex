"""The bounded tool loop.

Every limit here is enforced in code rather than requested of the model, because a bound the model
is merely asked to respect is not a bound. The loop ends with a separate, tools-less call that is
constrained to the answer schema: the provider will not accept a tool list and a response schema in
the same request, so the closing turn is structural, not stylistic.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence

from rotom_dex.chat import answer as answer_mod
from rotom_dex.chat import evidence as ev
from rotom_dex.chat import prompt as prompt_mod
from rotom_dex.chat import tools as tools_mod
from rotom_dex.chat.config import ChatConfig
from rotom_dex.chat.errors import (
    BudgetExceeded,
    ChatError,
    ProviderProtocolError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    ResearchUnavailable,
)
from rotom_dex.chat.protocols import ChatProvider, ResearchProvider, ToolResult, Turn
from rotom_dex.errors import NotFound, SemanticError
from rotom_dex.repositories.common import GameScope, snapshot_id
from rotom_dex.services import spoilers
from rotom_dex.services.context import PlaythroughContext


def _canonical(name: str, arguments: dict) -> str:
    return name + ":" + json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)


class _Budget:
    def __init__(self, config: ChatConfig):
        self.config = config
        self.deadline = time.monotonic() + config.deadline_s
        self.tool_calls = 0
        self.research_calls = 0
        self.total_bytes = 0
        self.per_tool: dict[str, int] = {}
        self.hit: list[str] = []

    def check_clock(self) -> None:
        if time.monotonic() > self.deadline:
            raise BudgetExceeded(f"the {self.config.deadline_s:.0f}s time budget for one answer")

    def allow(self, name: str) -> str | None:
        if self.tool_calls >= self.config.max_tool_calls:
            return f"the limit of {self.config.max_tool_calls} tool calls for one answer"
        used = self.per_tool.get(name, 0)
        if used >= self.config.max_calls_per_tool:
            return f"the limit of {self.config.max_calls_per_tool} calls to {name}"
        if name == "web_research" and self.research_calls >= self.config.max_research_calls:
            return f"the limit of {self.config.max_research_calls} web research calls"
        return None

    def spend(self, name: str, size: int) -> None:
        self.tool_calls += 1
        self.per_tool[name] = self.per_tool.get(name, 0) + 1
        if name == "web_research":
            self.research_calls += 1
        self.total_bytes += size


def _dispatch(db, scope: GameScope, ctx: PlaythroughContext, gate: spoilers.Gate, call, ledger: ev.EvidenceLedger, config: ChatConfig, snapshot: str) -> str:
    tool = tools_mod.REGISTRY.get(call.name)
    if tool is None:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="unknown_tool", detail=f"There is no tool called '{call.name}'.")
    try:
        payload = tool.handler(db, scope, ctx, call.arguments or {})
    except NotFound as exc:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="not_found", detail=str(exc))
    except SemanticError as exc:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="not_meaningful_in_this_game", detail=str(exc))

    filtered, removed = spoilers.apply(payload, gate)
    ledger.record_tool(filtered)
    # The resolved source records are for the player, not the model: they are most of the payload
    # and the model only ever needs the evidence ids, which stay on the rows themselves. The final
    # envelope resolves whatever the answer actually cites.
    if isinstance(filtered, dict) and filtered.get("evidence"):
        filtered = {**filtered, "evidence": f"{len(filtered['evidence'])} source record(s) omitted; cite the evidence_id on each row"}
    return ev.wrap_tool_result(
        tool=call.name,
        call_id=call.id,
        snapshot_id=snapshot,
        game=scope.slug,
        spoiler_level=gate.level,
        redactions=removed,
        payload=filtered,
        limit=config.max_tool_result_bytes,
    )


def _research(call, research: ResearchProvider | None, ledger: ev.EvidenceLedger, config: ChatConfig) -> str:
    query = str((call.arguments or {}).get("query", ""))[:200]
    if research is None:
        return ev.wrap_tool_error(tool="web_research", call_id=call.id, kind="research_disabled", detail="Web research is not enabled on this server.")
    try:
        result = research.search(query=query, timeout_s=config.research_timeout_s)
    except (ResearchUnavailable, ChatError) as exc:
        return ev.wrap_tool_error(tool="web_research", call_id=call.id, kind="research_unavailable", detail=str(exc) or "The research provider did not answer.")
    refs = [ledger.record_web(len(ledger.web_refs) + 1, c.url, c.title) for c in result.citations]
    listed = [ledger.web_refs[r] for r in refs]
    return ev.wrap_research(call_id=call.id, query=query, text=result.text, refs=listed, limit=config.max_research_chars)


def answer(
    db,
    scope: GameScope,
    ctx: PlaythroughContext,
    *,
    message: str,
    history: Sequence[dict] = (),
    provider: ChatProvider,
    research: ResearchProvider | None = None,
    config: ChatConfig,
) -> dict:
    """Run one grounded exchange and return the validated answer payload."""
    gate = spoilers.gate(db, scope, ctx)
    snapshot = snapshot_id(db)
    ledger = ev.EvidenceLedger()
    budget = _Budget(config)
    specs = tools_mod.specs(research_enabled=config.research_enabled and research is not None)

    turns: list[Turn] = []
    for entry in list(history)[-config.max_history_turns :]:
        role = "model" if entry.get("role") == "assistant" else "user"
        turns.append(Turn(role, text=str(entry.get("text", ""))[: config.max_message_chars]))
    turns.append(Turn("user", text=prompt_mod.context_block(scope, ctx, gate) + "\n\nQUESTION: " + message))

    seen: dict[str, str] = {}
    tools_used: list[dict] = []
    try:
        for _ in range(config.max_turns):
            budget.check_clock()
            reply = provider.complete(system=prompt_mod.SYSTEM, turns=turns, tools=specs, response_schema=None, timeout_s=config.provider_timeout_s)
            if reply.finish_reason == "safety":
                raise ProviderRefused("the provider declined to answer this question")
            if not reply.tool_calls:
                break
            results = []
            for call in reply.tool_calls:
                blocked = budget.allow(call.name)
                if blocked:
                    budget.hit.append(blocked)
                    results.append(ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="budget", detail=f"Not run: this request reached {blocked}."))
                    continue
                key = _canonical(call.name, call.arguments or {})
                if key in seen:
                    results.append(seen[key])
                    continue
                content = _research(call, research, ledger, config) if call.name == "web_research" else _dispatch(db, scope, ctx, gate, call, ledger, config, snapshot)
                budget.spend(call.name, len(content))
                seen[key] = content
                tools_used.append({"tool": call.name, "arguments": call.arguments or {}})
                results.append(content)
                if budget.total_bytes > config.max_total_tool_bytes:
                    budget.hit.append("the total size limit for tool results")
                    break
            turns.append(Turn("model", tool_calls=reply.tool_calls))
            paired = zip(reply.tool_calls, results, strict=False)
            turns.append(Turn("tool", tool_results=tuple(ToolResult(c.id, c.name, r) for c, r in paired)))
            if budget.hit:
                break

        budget.check_clock()
        closing = provider.complete(
            system=prompt_mod.SYSTEM,
            turns=[*turns, Turn("user", text=prompt_mod.CLOSING)],
            tools=[],
            response_schema=answer_mod.ANSWER_SCHEMA,
            timeout_s=config.provider_timeout_s,
        )
    except ProviderRefused:
        return _finish(answer_mod.abstention("Rotom could not answer that one. The Pokedex and team tools are unaffected."), gate, tools_used, budget, [])
    except BudgetExceeded as exc:
        return _finish(answer_mod.abstention(f"Rotom stopped before finishing: it reached {exc}."), gate, tools_used, budget, [str(exc)])
    except (ProviderUnavailable, ProviderTimeout):
        raise
    except ProviderProtocolError as exc:
        return _finish(answer_mod.abstention("Rotom's answer could not be read, so nothing is shown rather than a guess."), gate, tools_used, budget, [str(exc)])

    try:
        raw = json.loads(closing.text)
        if not isinstance(raw, dict):
            raise ValueError("answer was not an object")
    except (ValueError, TypeError) as exc:
        return _finish(answer_mod.abstention("Rotom's answer could not be read, so nothing is shown rather than a guess."), gate, tools_used, budget, [str(exc)])

    validated, notes = answer_mod.validate(db, raw, ledger, gate, max_prose=config.max_prose_chars)
    return _finish(validated, gate, tools_used, budget, notes)


def _finish(payload: dict, gate: spoilers.Gate, tools_used: list[dict], budget: _Budget, notes: list[str]) -> dict:
    return {
        **payload,
        "tools_used": tools_used,
        "spoiler_level": gate.level,
        "limits_reached": sorted(set(budget.hit)),
        "verification_notes": notes,
    }
