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

from jsonschema import Draft202012Validator

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
        self.usage: dict[str, int] = {}

    def check_clock(self) -> None:
        if time.monotonic() > self.deadline:
            raise BudgetExceeded(f"the {self.config.deadline_s:.0f}s time budget for one answer")

    def timeout(self, limit: float) -> float:
        self.check_clock()
        return max(0.001, min(limit, self.deadline - time.monotonic()))

    def allow(self, name: str) -> str | None:
        if self.total_bytes >= self.config.max_total_tool_bytes:
            return "the total size limit for tool results"
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
    errors = list(Draft202012Validator(tool.spec.parameters).iter_errors(call.arguments or {}))
    if errors:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="invalid_arguments", detail="Arguments do not match the tool schema.")
    try:
        payload = tool.handler(db, scope, ctx, call.arguments or {})
    except NotFound as exc:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="not_found", detail=str(exc))
    except SemanticError as exc:
        return ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="not_meaningful_in_this_game", detail=str(exc))

    filtered, removed = spoilers.apply(payload, gate)
    # Bound lists before recording them, so omitted facts cannot be cited.
    filtered = compact(filtered)
    ledger.record_tool(filtered)
    verified = ledger.bind(filtered, call.name, scope.slug)
    if call.name == "explain_mechanic":
        for entry in filtered.get("data", []):
            reference = ledger.record_web(len(ledger.web_refs) + 1, entry["url"], entry["title"])
            ledger.web_refs[reference]["review_status"] = "reference-reviewed"
            fact = {
                "fact_id": f"glossary:{entry['id']}",
                "claim": entry["text"],
                "evidence_id": reference,
                "tool": call.name,
                "game": scope.slug,
                "subject": entry["title"],
                "label": "Explanation",
                "value": entry["text"],
                "source_kind": "reference",
            }
            ledger.facts[fact["fact_id"]] = fact
            verified.append(fact)
    if call.name in {"damage_calculation", "competitive_validate"}:
        record = filtered.get("data") or {}
        ref = ledger.record_web(len(ledger.web_refs) + 1, record["source"], f"Calculator snapshot {record['snapshot']}")
        ledger.web_refs[ref]["review_status"] = "calculated"
        if call.name == "damage_calculation":
            claim = record["description"] + ". " + record["assumptions"]
        else:
            claim = f"In {record['format']}: " + ("this team passes the pinned legality rules." if record["valid"] else "; ".join(record["issues"]))
        fact = {
            "fact_id": f"calculated:{len(ledger.facts)}",
            "claim": claim,
            "evidence_id": ref,
            "tool": call.name,
            "game": scope.slug,
            "subject": "Battle tools",
            "label": "Result",
            "value": claim,
            "source_kind": "calculated",
        }
        ledger.facts[fact["fact_id"]] = fact
        verified.append(fact)
    if call.name == "story_recommendations":
        for row in filtered.get("data", {}).get("recommendations", []):
            ledger.tool_verdicts[row["pokemon"]] = row["status"]
            reasons = []
            if row["resists_team_weaknesses"]:
                reasons.append("Resists team weaknesses to " + ", ".join(row["resists_team_weaknesses"]) + ".")
            if row["new_types"]:
                reasons.append("Adds " + "/".join(row["new_types"]) + " typing.")
            ledger.recommendations[row["pokemon"]] = {
                "subject": row["pokemon"],
                "text": f"Consider {row['name']}",
                "rationale": " ".join(reasons) + " " + row["tradeoff"],
                "status": row["status"],
            }
    if call.name == "knowledge_search":
        for entry in filtered.get("data", []):
            ref = ledger.record_web(len(ledger.web_refs) + 1, entry["sources"][0], entry["subject"])
            ledger.web_refs[ref]["review_status"] = entry["review_status"]
            fact = {
                "fact_id": entry["id"],
                "claim": f"In {scope.name}: {entry['claim']}",
                "evidence_id": ref,
                "tool": call.name,
                "game": scope.slug,
                "subject": entry["subject"],
                "label": "Where to obtain",
                "value": entry["claim"],
                "source_kind": "reference",
                "review_status": entry["review_status"],
                "snapshot": entry["snapshot"],
            }
            ledger.facts[fact["fact_id"]] = fact
            verified.append(fact)
    filtered["verified_facts"] = verified[:60]
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


def _research(call, research: ResearchProvider | None, ledger: ev.EvidenceLedger, config: ChatConfig, scope, gate, timeout_s) -> str:
    spec = next(t for t in tools_mod.specs(research_enabled=True) if t.name == "web_research")
    if list(Draft202012Validator(spec.parameters).iter_errors(call.arguments)):
        return ev.wrap_tool_error(tool="web_research", call_id=call.id, kind="invalid_arguments", detail="Research arguments must include a query and a reason.")
    query = f"Pokemon {scope.name} ({scope.version_group}, generation {scope.generation_id}): " + str((call.arguments or {}).get("query", ""))[:200]
    if gate.level != "full" and not gate.visible_milestones and not gate.hidden_count:
        return ev.wrap_tool_error(
            tool="web_research",
            call_id=call.id,
            kind="spoiler_coverage",
            detail="Spoiler-safe research is not established for this game's progress. Ask a general mechanics question or permit requested story details.",
        )
    if research is None:
        return ev.wrap_tool_error(tool="web_research", call_id=call.id, kind="research_disabled", detail="Web research is not enabled on this server.")
    try:
        result = research.search(query=query, timeout_s=timeout_s)
    except (ResearchUnavailable, ChatError) as exc:
        return ev.wrap_tool_error(tool="web_research", call_id=call.id, kind="research_unavailable", detail=str(exc) or "The research provider did not answer.")
    refs = [
        ledger.record_web(len(ledger.web_refs) + 1, c.url, c.title) for c in result.citations if c.url.startswith("https://") and not spoilers.leaks(c.title + " " + c.url, gate)
    ]
    listed = [ledger.web_refs[r] for r in refs]
    passages = []
    for i, passage in enumerate(result.passages):
        if spoilers.leaks(passage["text"], gate):
            continue
        text = ev.sanitise(passage["text"], 600)
        evidence = next((r["id"] for r in listed if r["url"] in passage["urls"]), None)
        if not evidence:
            continue
        fact = {
            "fact_id": f"research:{len(ledger.facts)}:{i}",
            "claim": text,
            "evidence_id": evidence,
            "tool": "web_research",
            "game": scope.slug,
            "subject": "Web research",
            "label": "Finding",
            "value": text,
            "source_kind": "web",
            "review_status": "unreviewed",
        }
        ledger.facts[fact["fact_id"]] = fact
        passages.append(fact)
    filtered_text, _ = spoilers.apply(result.text, gate)
    block = json.loads(ev.wrap_research(call_id=call.id, query=query, text=filtered_text, refs=listed, limit=config.max_research_chars))
    block["verified_facts"] = passages
    return json.dumps(block, ensure_ascii=False)


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
    on_progress=None,
    cancelled=None,
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
            if cancelled and cancelled.is_set():
                raise BudgetExceeded("cancelled request")
            reply = provider.complete(system=prompt_mod.SYSTEM, turns=turns, tools=specs, response_schema=None, timeout_s=budget.timeout(config.provider_timeout_s))
            for key, value in reply.usage.items():
                budget.usage[key] = budget.usage.get(key, 0) + value
            if reply.finish_reason == "safety":
                raise ProviderRefused("the provider declined to answer this question")
            if not reply.tool_calls:
                break
            results = []
            for call in reply.tool_calls:
                budget.check_clock()
                if cancelled and cancelled.is_set():
                    raise BudgetExceeded("cancelled request")
                if on_progress:
                    on_progress("Researching game-specific sources…" if call.name == "web_research" else "Checking game data…")
                blocked = budget.allow(call.name)
                if blocked:
                    budget.hit.append(blocked)
                    results.append(ev.wrap_tool_error(tool=call.name, call_id=call.id, kind="budget", detail=f"Not run: this request reached {blocked}."))
                    continue
                key = _canonical(call.name, call.arguments or {})
                if key in seen:
                    results.append(seen[key])
                    continue
                content = (
                    _research(call, research, ledger, config, scope, gate, budget.timeout(config.research_timeout_s))
                    if call.name == "web_research"
                    else _dispatch(db, scope, ctx, gate, call, ledger, config, snapshot)
                )
                budget.spend(call.name, len(content))
                seen[key] = content
                tools_used.append({"tool": call.name, "arguments": call.arguments or {}})
                results.append(content)
                if budget.total_bytes > config.max_total_tool_bytes:
                    budget.hit.append("the total size limit for tool results")
                    # Every issued function call still needs a response.
            turns.append(Turn("model", tool_calls=reply.tool_calls, provider_parts=reply.provider_parts))
            paired = zip(reply.tool_calls, results, strict=False)
            turns.append(Turn("tool", tool_results=tuple(ToolResult(c.id, c.name, r) for c, r in paired)))
            if budget.hit:
                break

        budget.check_clock()
        if cancelled and cancelled.is_set():
            raise BudgetExceeded("cancelled request")
        closing = provider.complete(
            system=prompt_mod.SYSTEM,
            turns=[*turns, Turn("user", text=prompt_mod.CLOSING)],
            tools=[],
            response_schema=answer_mod.ANSWER_SCHEMA,
            timeout_s=budget.timeout(config.provider_timeout_s),
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

    for key, value in closing.usage.items():
        budget.usage[key] = budget.usage.get(key, 0) + value
    if time.monotonic() > budget.deadline:
        return _finish(answer_mod.abstention("The answer exceeded the time limit. Please retry."), gate, tools_used, budget, [])
    validated, notes = answer_mod.validate(db, raw, ledger, gate, max_prose=config.max_prose_chars, scope=scope, ctx=ctx)
    return _finish(validated, gate, tools_used, budget, notes)


def _finish(payload: dict, gate: spoilers.Gate, tools_used: list[dict], budget: _Budget, notes: list[str]) -> dict:
    return {
        **payload,
        "tools_used": tools_used,
        "usage": {"provider": budget.usage, "tool_calls": budget.tool_calls, "research_calls": budget.research_calls},
        "spoiler_level": gate.level,
        "limits_reached": sorted(set(budget.hit)),
        "verification_notes": notes,
    }


def compact(value, limit=12):
    """Keep nested results usable; focused tools provide pagination for complete lists."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[k] = compact(v, limit)
            if isinstance(v, list) and len(v) > limit:
                out[f"{k}_omitted"] = len(v) - limit
        return out
    if isinstance(value, list):
        return [compact(v, limit) for v in value[:limit]]
    return value
