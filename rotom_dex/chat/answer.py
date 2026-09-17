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
                "properties": {"claim": {"type": "string", "maxLength": 300}, "evidence_id": {"type": "string", "maxLength": 64}, "tool": {"type": "string", "maxLength": 64}},
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
                "properties": {"kind": {"type": "string", "enum": ACTION_KINDS}, "label": {"type": "string", "maxLength": 120}, "payload": {"type": "object"}},
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


def validate(db, raw: dict, ledger: EvidenceLedger, gate: spoilers.Gate, *, max_prose: int) -> tuple[dict, list[str]]:
    """Return the answer that may be shown, and the notes explaining what was changed or dropped."""
    notes: list[str] = []
    answer = {**EMPTY, **{k: v for k, v in raw.items() if k in ANSWER_SCHEMA["properties"]}}

    # 1. A spoiler leak is fatal for the whole answer. Patching prose would leave paraphrases behind.
    prose_surfaces = [answer.get("prose", "")]
    prose_surfaces += [c.get("title", "") for c in answer.get("cards", [])]
    prose_surfaces += [r.get("value", "") for c in answer.get("cards", []) for r in c.get("rows", [])]
    prose_surfaces += [r.get("text", "") for r in answer.get("recommendations", [])]
    prose_surfaces += [a.get("text", "") for a in answer.get("assumptions", [])]
    leaked = sorted({term for surface in prose_surfaces for term in spoilers.leaks(surface, gate)})
    if leaked:
        reason = "That answer referred to a part of the story your spoiler setting hides, so it was withheld. Raise your spoiler preference if you want it."
        return abstention(reason), [f"withheld: answer referenced {len(leaked)} hidden term(s)"]

    # 2. Every fact must cite evidence this request actually produced, and it must resolve.
    kept_facts, demoted = [], []
    for fact in answer.get("facts", []):
        eid = fact.get("evidence_id", "")
        if eid in ledger.db_ids and _evidence_exists(db, eid):
            kept_facts.append(fact)
        else:
            demoted.append(fact)
    answer["facts"] = kept_facts
    if demoted:
        notes.append(f"{len(demoted)} claim(s) cited evidence that no tool returned; they were demoted to assumptions")
        answer["assumptions"] = list(answer.get("assumptions", [])) + [{"text": f["claim"], "because": "missing_data"} for f in demoted[:5]]

    # 3. Web references stay quarantined: they may be listed, never used as evidence for a fact.
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

    # 5. `unavailable` is never derived. It may only appear if a stored row actually said so.
    if not ledger.saw_stored_unavailable and "unavailable" in json.dumps(answer).lower():
        return abstention("That answer described something as unavailable, which this data can never establish. Missing evidence means unknown, not unobtainable."), [
            *notes,
            "withheld: answer asserted unavailability with no stored evidence",
        ]

    # 6. Proposed actions are inert, whatever the model said.
    actions = []
    for action in answer.get("actions", []):
        if action.get("kind") in ACTION_KINDS and isinstance(action.get("payload"), dict):
            actions.append({"kind": action["kind"], "label": action.get("label", ""), "payload": action["payload"], "applied": False})
    answer["actions"] = actions

    if len(answer.get("prose", "")) > max_prose:
        answer["prose"] = answer["prose"][:max_prose].rsplit(" ", 1)[0] + "…"

    if gate.filtering:
        answer["assumptions"] = list(answer.get("assumptions", [])) + [{"text": gate.assumption(), "because": "spoiler_filter"}]

    answer["abstained"] = bool(answer.get("abstained")) or (not answer["facts"] and not answer["cards"] and not answer["recommendations"])
    return answer, notes
