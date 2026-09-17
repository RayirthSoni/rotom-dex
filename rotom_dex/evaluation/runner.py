"""Grading the reviewed question set.

Two modes, and the distinction is the honest part. The deterministic mode needs no credential: it
runs the tools each question names and checks the ground truth a reviewer recorded, which is what
catches a wrong-game answer, an invented reachable route or a leaked spoiler. The live mode needs a
provider and additionally grades the model's own answer.

Without a credential the live half cannot run, and the report says so rather than scoring zero or
quietly passing.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rotom_dex.chat.tools import REGISTRY
from rotom_dex.errors import NotFound, SemanticError
from rotom_dex.evaluation import contexts
from rotom_dex.repositories.common import resolve_game
from rotom_dex.services import spoilers

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = ROOT / "data/eval/questions.jsonl"


@dataclass
class Result:
    case_id: str
    category: str
    game: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        by_category: dict[str, dict[str, int]] = {}
        for r in self.results:
            bucket = by_category.setdefault(r.category, {"passed": 0, "failed": 0})
            bucket["passed" if r.passed else "failed"] += 1
        failures = [{"id": r.case_id, "detail": r.detail} for r in self.results if not r.passed]
        return {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": len(failures),
            "by_category": dict(sorted(by_category.items())),
            "by_game": dict(sorted(Counter(r.game for r in self.results).items())),
            "failures": failures,
            "live_graded": False,
            "note": (
                "Deterministic grading only: every check runs the domain services directly. Model-written answers are graded only with `--live`, which needs a provider credential."
            ),
        }


def load(path: Path = DEFAULT_QUESTIONS) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _walk(node, key: str):
    """Every value stored under `key`, anywhere in the payload."""
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                found.append(v)
            found.extend(_walk(v, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk(item, key))
    return found


def _verdicts(payload) -> dict[str, str]:
    """Best verdict per subject, the same way the chat ledger reads them."""
    rank = {"locked": 0, "unknown": 1, "reachable": 2}
    out: dict[str, str] = {}

    def walk(node, subject):
        if isinstance(node, dict):
            here = node.get("pokemon") or node.get("item")
            subject = here.lower() if isinstance(here, str) else subject
            derived = node.get("derived")
            if isinstance(derived, dict) and subject:
                status = derived.get("status")
                if status in rank and (subject not in out or rank[status] > rank[out[subject]]):
                    out[subject] = status
            for value in node.values():
                walk(value, subject)
        elif isinstance(node, list):
            for item in node:
                walk(item, subject)

    walk(payload, None)
    return out


def _check(db, case: dict, scope, ctx) -> tuple[bool, str]:  # noqa: PLR0911, PLR0912
    check = case["check"]
    tool = REGISTRY[check["tool"]]
    want_error = check.get("expect_error")
    try:
        payload = tool.handler(db, scope, ctx, check.get("args", {}))
    except SemanticError as exc:
        return (want_error == "semantic", f"semantic error: {exc}" if want_error != "semantic" else "")
    except NotFound as exc:
        return (want_error == "not_found", f"not found: {exc}" if want_error != "not_found" else "")
    if want_error:
        return False, f"expected a {want_error} error, got an answer"

    filtered, _ = spoilers.apply(payload, spoilers.gate(db, scope, ctx))
    data = filtered.get("data") if isinstance(filtered, dict) else filtered
    text = json.dumps(filtered, default=str)

    if check.get("expect_no_claim"):
        return (data is None, "expected no claim, got data" if data is not None else "")
    if check.get("expect_claim"):
        return (data is not None, "expected an answer, got no claim" if data is None else "")
    if check.get("expect_empty_or_no_claim"):
        ok = data is None or (isinstance(data, list) and not data)
        return ok, "" if ok else "expected nothing curated"
    if data is None:
        return False, "no claim, but the case expects one"

    if "expect_types" in check:
        actual = [t["type"] if isinstance(t, dict) else t for t in (data.get("types") or [])]
        want = check["expect_types"]
        return actual == want, "" if actual == want else f"types {actual} != {want}"
    if "expect_multiplier" in check:
        actual = data.get("multiplier")
        want = check["expect_multiplier"]
        return actual == want, "" if actual == want else f"multiplier {actual} != {want}"
    if "expect_mechanic" in check:
        mechanics = data.get("mechanics") or {}
        for key, value in check["expect_mechanic"].items():
            if mechanics.get(key) != value:
                return False, f"mechanic {key} is {mechanics.get(key)}, expected {value}"
        return True, ""
    if "expect_verdict" in check:
        actual = _verdicts(filtered)
        for subject, want in check["expect_verdict"].items():
            if actual.get(subject) != want:
                return False, f"{subject} is {actual.get(subject)}, expected {want}"
        return True, ""
    if "expect_not_verdict" in check:
        actual = _verdicts(filtered)
        for subject, forbidden in check["expect_not_verdict"].items():
            if actual.get(subject) == forbidden:
                return False, f"{subject} must not be {forbidden}"
        return True, ""
    if check.get("expect_no_unavailable"):
        bad = [v for v in _walk(data, "status") if v == "unavailable"]
        return not bad, "" if not bad else "a derivation reported unavailable"
    if "expect_evolves_into" in check:
        targets = {r.get("to_pokemon") for r in (data.get("outgoing") or [])}
        want = check["expect_evolves_into"]
        return want in targets, "" if want in targets else f"{want} not among {sorted(t for t in targets if t)}"
    if "expect_not_evolves_into" in check:
        applicable = {r.get("to_pokemon") for r in (data.get("outgoing") or []) if (r.get("derived") or {}).get("status") != "not-applicable"}
        want = check["expect_not_evolves_into"]
        return want not in applicable, "" if want not in applicable else f"{want} should not apply in this game"
    if check.get("expect_access_separated"):
        rows = data.get("moves") or []
        ok = bool(rows) and all("eligible" in r and "access" in r for r in rows)
        return ok, "" if ok else "eligibility and access are not reported separately"
    if "expect_method_access" in check:
        for method, want in check["expect_method_access"].items():
            rows = [r for r in (data.get("moves") or []) if r.get("method") == method]
            if rows and not all((r.get("access") or {}).get("status") == want for r in rows):
                return False, f"{method} access is not always {want}"
        return True, ""
    if "expect_feature_status" in check:
        features = {f["feature"]: f["status"] for f in (data.get("features") or [])}
        for feature, want in check["expect_feature_status"].items():
            if features.get(feature) != want:
                return False, f"{feature} is {features.get(feature)}, expected {want}"
        return True, ""
    if "expect_hidden" in check:
        for slug in check["expect_hidden"]:
            if slug in text:
                return False, f"'{slug}' reached the payload despite the spoiler setting"
        return True, ""
    if "expect_visible" in check:
        for slug in check["expect_visible"]:
            if slug not in text:
                return False, f"'{slug}' should be visible at this spoiler level"
        return True, ""
    if "expect_game" in check:
        actual = (filtered.get("game") or {}).get("slug")
        want = check["expect_game"]
        return actual == want, "" if actual == want else f"answered as {actual}, expected {want}"
    if "expect_stat_present" in check:
        stats = {s.get("stat") for s in (data.get("stats") or [])}
        want = check["expect_stat_present"]
        return want in stats, "" if want in stats else f"{want} not among {sorted(s for s in stats if s)}"
    if check.get("expect_coverage_from_moves"):
        coverage = data.get("coverage") or {}
        return bool(coverage.get("attacking_moves")), "" if coverage.get("attacking_moves") else "no coverage from recorded moves"
    if check.get("expect_no_prediction"):
        banned = ("you will win", "you will lose", "guaranteed", "certain victory")
        lowered = text.lower()
        hit = [phrase for phrase in banned if phrase in lowered]
        return not hit, "" if not hit else f"payload predicts an outcome: {hit}"
    return False, "case has no recognised expectation"


def run(db, questions: list[dict] | None = None) -> Report:
    report = Report()
    cases = questions if questions is not None else load()
    scopes: dict[str, object] = {}
    for case in cases:
        game = case["game"]
        try:
            scope = scopes.get(game) or scopes.setdefault(game, resolve_game(db, game))
        except NotFound:
            report.skipped.append(f"{case['id']}: game '{game}' is not in this database")
            continue
        if not scope.imported:
            report.skipped.append(f"{case['id']}: '{game}' has no facts in this database")
            continue
        ctx = contexts.build(case.get("context", "none"), game, db, scope.id)
        try:
            passed, detail = _check(db, case, scope, ctx)
        except Exception as exc:  # a broken case must not stop the run
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        report.results.append(Result(case["id"], case["category"], game, passed, detail))
    return report
