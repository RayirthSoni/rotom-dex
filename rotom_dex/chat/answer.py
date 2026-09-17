"""The answer contract, and the pass that decides whether an answer may be returned at all.

Facts carry a *singular* `evidence_id`. That is load-bearing rather than stylistic: the envelope
builder collects evidence by walking for keys that end in `evidence_id` whose value is a string
(`repositories/common.py`), so a list would be silently ignored and the answer would ship with no
sources. Two sources means two facts.

Nothing the model asserts is taken on trust. An evidence id must have come back from a tool during
this request *and* resolve in the database; a recommendation may not be more optimistic than the
verdict the reachability tool actually returned; and a single spoiler leak discards the whole answer
rather than being patched out of the prose.
"""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from rotom_dex.chat.evidence import EvidenceLedger
from rotom_dex.services import spoilers

CARD_KINDS = ["pokemon", "move", "item", "ability", "nature", "matchup", "acquisition", "evolution", "boss", "team", "milestone", "note"]
ACTION_KINDS = ["pin_plan", "add_team_member", "set_member_level", "set_member_moves", "mark_milestone", "set_current_location"]
ASSUMPTION_REASONS = ["missing_data", "unrecorded_progress", "untracked_mechanic", "open_world", "spoiler_filter", "unreviewed_web"]
STATUSES = ["reachable", "locked", "unknown"]

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["prose", "facts", "assumptions", "recommendations", "cards", "actions", "references", "abstained"],
    "properties": {
        "prose": {"type": "string", "maxLength": 1200},
        "abstained": {"type": "boolean"},
        "abstain_reason": {"type": "string", "maxLength": 400},
        "facts": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "evidence_id", "tool"],
                "properties": {
                    "fact_id": {"type": "string", "maxLength": 64},
                    "claim": {"type": "string", "maxLength": 1000},
                    "evidence_id": {"type": "string", "maxLength": 64},
                    "tool": {"type": "string", "maxLength": 64},
                },
            },
        },
        "assumptions": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "because"],
                "properties": {"text": {"type": "string", "maxLength": 300}, "because": {"type": "string", "enum": ASSUMPTION_REASONS}},
            },
        },
        "recommendations": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "rationale", "status"],
                "properties": {
                    "text": {"type": "string", "maxLength": 300},
                    "rationale": {"type": "string", "maxLength": 300},
                    "status": {"type": "string", "enum": STATUSES},
                    "subject": {"type": "string", "maxLength": 64},
                },
            },
        },
        "cards": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "title", "rows", "tool"],
                "properties": {
                    "kind": {"type": "string", "enum": CARD_KINDS},
                    "title": {"type": "string", "maxLength": 120},
                    "subject": {"type": "string", "maxLength": 64},
                    "tool": {"type": "string", "maxLength": 64},
                    "rows": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["label", "value"],
                            "properties": {
                                "label": {"type": "string", "maxLength": 60},
                                "value": {"type": "string", "maxLength": 300},
                                "evidence_id": {"type": "string", "maxLength": 64},
                            },
                        },
                    },
                },
            },
        },
        "actions": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "label", "payload"],
                "properties": {
                    "kind": {"type": "string", "enum": ACTION_KINDS},
                    "label": {"type": "string", "maxLength": 120},
                    "payload": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "pokemon": {"type": "string", "maxLength": 64},
                            "member": {"type": "integer", "minimum": 0, "maximum": 5},
                            "level": {"type": "integer", "minimum": 1, "maximum": 100},
                            "moves": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": 64}},
                            "milestone": {"type": "string", "maxLength": 64},
                            "location": {"type": "string", "maxLength": 64},
                            "battle": {"type": "string", "maxLength": 96},
                        },
                    },
                },
            },
        },
        "references": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "id"],
                "properties": {
                    "kind": {"type": "string", "enum": ["evidence", "web"]},
                    "id": {"type": "string", "maxLength": 64},
                    "url": {"type": "string", "maxLength": 400},
                    "title": {"type": "string", "maxLength": 200},
                },
            },
        },
    },
}

EMPTY = {"prose": "", "facts": [], "assumptions": [], "recommendations": [], "cards": [], "actions": [], "references": [], "abstained": True}


def abstention(reason: str, assumptions: list[str] | None = None) -> dict:
    return {
        **EMPTY,
        "prose": reason,
        "abstained": True,
        "abstain_reason": reason,
        "assumptions": [{"text": a, "because": "missing_data"} for a in (assumptions or [])],
    }


def _evidence_exists(db, evidence_id: str) -> bool:
    return db.execute("SELECT 1 FROM evidence WHERE id=?", (evidence_id,)).fetchone() is not None


def validate(db, raw: dict, ledger: EvidenceLedger, gate: spoilers.Gate, *, max_prose: int, scope=None, ctx=None) -> tuple[dict, list[str]]:
    """Return the answer that may be shown, and the notes explaining what was changed or dropped."""
    notes: list[str] = []
    # Validate before traversing any model-controlled nested structure.
    errors = list(Draft202012Validator(ANSWER_SCHEMA).iter_errors(raw))
    if errors:
        return abstention("Rotom could not read this answer. Please try again."), ["invalid answer structure"]
    answer = {**EMPTY, **{k: v for k, v in raw.items() if k in ANSWER_SCHEMA["properties"]}}

    # 1. A spoiler leak is fatal for the whole answer. Patching prose would leave paraphrases behind.
    leaked = spoilers.leaks(json.dumps(answer, ensure_ascii=False), gate)
    if leaked:
        reason = "That answer referred to a part of the story your spoiler setting hides, so it was withheld. Raise your spoiler preference if you want it."
        return abstention(reason), [f"withheld: answer referenced {len(leaked)} hidden term(s)"]

    # 2. Every fact must cite evidence this request actually produced, and it must resolve.
    kept_facts = []
    for fact in answer.get("facts", []):
        known = ledger.facts.get(fact.get("fact_id", ""))
        if known is None:
            known = next((f for f in ledger.facts.values() if f["claim"] == fact.get("claim") and f["evidence_id"] == fact.get("evidence_id")), None)
        if known:
            kept_facts.append(dict(known))
        else:
            notes.append("Dropped a claim whose evidence did not bind to the asserted value.")
    answer["facts"] = kept_facts
    # Factual cards are projections of selected records, never arbitrary model-written values.
    groups = {}
    for fact in kept_facts:
        groups.setdefault((fact["subject"], fact["game"]), []).append(fact)
    answer["cards"] = [
        {
            "kind": "note",
            "title": f"{subject} · {game.replace(chr(45), chr(32)).title()}",
            "subject": subject,
            "tool": facts[0]["tool"],
            "sprite_url": facts[0].get("sprite_url"),
            "rows": [{"label": f["label"], "value": f["value"], "evidence_id": f["evidence_id"]} for f in facts[:12]],
        }
        for (subject, game), facts in list(groups.items())[:8]
    ]
    # Unsupported factual prose cannot survive after its claims are removed. Research passages
    # and numeric facts are rendered from their binding; advice remains separately labelled.
    if kept_facts:
        answer["prose"] = kept_facts[0]["claim"]
        if len(kept_facts) == 1:
            answer["cards"] = []
    elif answer.get("facts") or raw.get("facts") or raw.get("cards"):
        answer["prose"] = "I could not verify that answer against the retrieved evidence. Try a more specific question."
    elif answer.get("recommendations"):
        answer["prose"] = "Here are suggestions to consider. Availability is checked separately below."
    else:
        answer["prose"] = "I need more information or a more specific question to give a supported answer."

    # 3. References must have been retrieved during this request. Grounded passages retain
    # their unreviewed status; a URL alone cannot support an arbitrary model assertion.
    refs = []
    for ref in answer.get("references", []):
        if ref.get("kind") == "web":
            known = ledger.web_refs.get(ref.get("id", ""))
            if known:
                refs.append({**known, "kind": "web"})
            continue
        if ref.get("id") in ledger.db_ids and _evidence_exists(db, ref["id"]):
            refs.append({"kind": "evidence", "id": ref["id"], "review_status": "reference-reviewed"})
    for ref in ledger.web_refs.values():
        if not any(r.get("id") == ref["id"] for r in refs):
            refs.append({**ref, "kind": "web"})
    answer["references"] = refs
    if spoilers.leaks(json.dumps(answer, ensure_ascii=False), gate):
        return abstention("The retrieved sources could reveal later story details. Change your spoiler preference to see them."), ["withheld: source metadata"]

    # 4. A recommendation may never be more optimistic than the verdict a tool returned.
    rank = {"locked": 0, "unknown": 1, "reachable": 2}
    for rec in answer.get("recommendations", []):
        subject = (rec.get("subject") or "").lower()
        actual = ledger.tool_verdicts.get(subject)
        if actual is None:
            if rec.get("status") == "reachable":
                rec["status"] = "unknown"
                notes.append(f"recommendation for '{subject or 'an unnamed target'}' claimed reachable with no reachability check; downgraded to unknown")
            continue
        if rank.get(rec.get("status"), 1) > rank[actual]:
            notes.append(f"recommendation for '{subject}' claimed {rec['status']} but the check said {actual}; downgraded")
            rec["status"] = actual

    # Advice selects a subject; retrieved facts and deterministic rankings supply its rationale.
    # This closes the loophole where an invented number was simply moved into a recommendation.
    checked_recommendations = []
    for rec in answer["recommendations"]:
        subject = rec.get("subject", "").lower()
        if subject in ledger.recommendations:
            checked_recommendations.append(dict(ledger.recommendations[subject]))
            continue
        row = db.execute("SELECT name FROM pokemon_forms WHERE slug=? UNION SELECT name FROM items WHERE slug=?", (subject, subject)).fetchone()
        if not row:
            continue
        supporting = [f for f in ledger.facts.values() if f["subject"].lower().replace(" ", "-") == subject]
        rationale = (
            " ".join(f["claim"] for f in supporting[:2])
            if supporting
            else "This suggestion has not been supported with matching facts yet. Check its moves and acquisition before using it."
        )
        checked_recommendations.append({"subject": subject, "text": f"Consider {row[0]}", "rationale": rationale, "status": rec["status"]})
    answer["recommendations"] = checked_recommendations

    # 5. Proposed actions are inert, whatever the model said.
    actions = []
    for action in answer.get("actions", []):
        if valid_action(db, action, scope=scope, ctx=ctx):
            payload = action["payload"]
            labels = {
                "add_team_member": f"Add {payload.get('pokemon', '').replace('-', ' ').title()} to team",
                "set_member_level": f"Set member level to {payload.get('level')}",
                "set_member_moves": "Update this member's moves",
                "mark_milestone": f"Mark {payload.get('milestone', '').replace('-', ' ')} complete",
                "set_current_location": f"Set location to {payload.get('location', '').replace('-', ' ')}",
                "pin_plan": "Save this battle plan",
            }
            actions.append({"kind": action["kind"], "label": labels[action["kind"]], "payload": payload, "applied": False})
    answer["actions"] = actions

    if len(answer.get("prose", "")) > max_prose:
        answer["prose"] = answer["prose"][:max_prose].rsplit(" ", 1)[0] + "…"

    assumption_text = {
        "missing_data": "Some requested information is not present in the retrieved records.",
        "unrecorded_progress": "Your recorded progress does not establish every prerequisite.",
        "untracked_mechanic": "Some relevant mechanics are not modeled by these tools.",
        "open_world": "Unrecorded facts remain unknown rather than false.",
        "spoiler_filter": "Some information was withheld by your spoiler preference.",
        "unreviewed_web": "Externally researched findings have not received independent content review.",
    }
    answer["assumptions"] = [{"text": assumption_text[reason], "because": reason} for reason in dict.fromkeys(a["because"] for a in answer["assumptions"])]
    if not answer["facts"] and not answer["recommendations"]:
        answer["prose"] = "I could not establish a supported answer yet. Try specifying the Pokémon, item, or game, or enable research for missing information."
    if gate.filtering:
        answer["assumptions"] = list(answer.get("assumptions", [])) + [{"text": gate.assumption(), "because": "spoiler_filter"}]

    answer["abstained"] = bool(answer.get("abstained")) or (not answer["facts"] and not answer["cards"] and not answer["recommendations"])
    if answer["abstained"]:
        answer["abstain_reason"] = answer["prose"]
    return answer, notes


def valid_action(db, action: dict, *, scope=None, ctx=None) -> bool:
    payload = action.get("payload", {})
    kind = action.get("kind")
    if not isinstance(payload, dict):
        return False
    if scope is not None and kind in {"add_team_member", "set_member_level", "set_member_moves"}:
        from dataclasses import replace

        from rotom_dex.errors import NotFound, SemanticError
        from rotom_dex.services.context import PlaythroughContext, TeamMember, validate

        try:
            candidate = ctx or PlaythroughContext(game=scope.slug)
            if kind == "add_team_member":
                candidate = replace(candidate, team=(*candidate.team, TeamMember(pokemon=payload.get("pokemon", ""))))
            else:
                index = payload.get("member")
                if type(index) is not int or not 0 <= index < len(candidate.team):
                    return False
                members = list(candidate.team)
                members[index] = replace(members[index], **({"level": payload.get("level")} if kind == "set_member_level" else {"moves": tuple(payload.get("moves", []))}))
                candidate = replace(candidate, team=tuple(members))
            if len(candidate.team) > 6 or validate(db, scope, candidate):
                return False
        except (NotFound, SemanticError, TypeError, ValueError):
            return False
    if scope is not None and kind == "pin_plan":
        return isinstance(payload.get("battle"), str) and bool(db.execute("SELECT 1 FROM trainer_battles WHERE game_id=? AND id=?", (scope.id, payload["battle"])).fetchone())
    if scope is not None and kind == "set_current_location":
        return isinstance(payload.get("location"), str) and bool(
            db.execute("SELECT 1 FROM acquisitions a JOIN locations l ON l.id=a.location_id WHERE a.game_id=? AND l.slug=?", (scope.id, payload["location"])).fetchone()
        )
    if scope is not None and kind == "mark_milestone":
        return isinstance(payload.get("milestone"), str) and bool(db.execute("SELECT 1 FROM milestones WHERE game_id=? AND slug=?", (scope.id, payload["milestone"])).fetchone())
    if kind in {"set_member_level", "set_member_moves"}:
        index = payload.get("member")
        if type(index) is not int or not 0 <= index <= 5:
            return False
        if kind == "set_member_level":
            return type(payload.get("level")) is int and 1 <= payload["level"] <= 100
        return (
            isinstance(payload.get("moves"), list)
            and len(payload["moves"]) <= 4
            and all(isinstance(m, str) and db.execute("SELECT 1 FROM moves WHERE slug=?", (m,)).fetchone() for m in payload["moves"])
        )
    target = {
        "add_team_member": ("pokemon", "pokemon_forms", "slug"),
        "mark_milestone": ("milestone", "milestones", "slug"),
        "set_current_location": ("location", "locations", "slug"),
        "pin_plan": ("battle", "trainer_battles", "id"),
    }.get(kind)
    if not target:
        return False
    key, table, column = target
    value = payload.get(key)
    return isinstance(value, str) and bool(db.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (value,)).fetchone())
