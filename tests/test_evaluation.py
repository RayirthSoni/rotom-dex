"""The reviewed question set, graded against the domain services.

This is the deterministic half of the evaluation: no model, no network. It is what catches a
wrong-game answer, a route that claims to be reachable when the prerequisites say otherwise, a
derivation that invents unavailability, and a spoiler that reaches the payload. The model's own
wording is graded separately, and only when a provider credential exists.
"""

from __future__ import annotations

import pytest

from rotom_dex.evaluation import runner

CASES = runner.load()
CATEGORIES = sorted({c["category"] for c in CASES})


def test_the_question_set_meets_its_stated_size_and_spread():
    """The release gate asks for at least 100 reviewed questions across several kinds of failure."""
    assert len(CASES) >= 100
    assert len({c["id"] for c in CASES}) == len(CASES), "case ids must be unique"
    assert {"factual", "acquisition", "missing-data", "unavailable-resource", "spoiler", "follow-up"} <= set(CATEGORIES)
    assert len({c["game"] for c in CASES}) >= 3, "questions must span more than the two reviewed games"
    for case in CASES:
        assert case["check"].get("tool") in {*runner.REGISTRY, None}, case["id"]


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_question_in_the_category_passes(db, category):
    report = runner.run(db, [c for c in CASES if c["category"] == category])
    failures = [f"{r.case_id}: {r.detail}" for r in report.results if not r.passed]
    assert not failures, "\n".join(failures)
    assert report.results, f"no cases ran for {category}"


def test_the_summary_reports_that_live_grading_did_not_run(db):
    """Silence about the untested half would be the dishonest outcome."""
    summary = runner.run(db, CASES[:5]).summary()
    assert summary["live_graded"] is False
    assert "credential" in summary["note"]
