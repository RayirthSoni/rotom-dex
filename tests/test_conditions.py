"""Typed conditions and their translation from evolution data."""

import json

import pytest

from rotom_dex.domain.conditions import evaluate_condition, validate_condition


def test_three_valued_and_or():
    level = {"op": "level_at_least", "value": 20}
    unknown = {"op": "unknown", "reason": "unreviewed"}
    assert evaluate_condition({"op": "and", "args": [level, unknown]}, {"level": 20}) is None
    assert evaluate_condition({"op": "and", "args": [level, unknown]}, {"level": 19}) is False
    assert evaluate_condition({"op": "or", "args": [level, unknown]}, {"level": 20}) is True
    assert evaluate_condition(level, {}) is None
    assert evaluate_condition({"op": "trade"}, {"trade": True}) is True
    assert evaluate_condition({"op": "gender", "value": "male"}, {"gender": {"female"}}) is False
    assert evaluate_condition({"op": "happiness_at_least", "value": 220}, {"happiness": 255}) is True


@pytest.mark.parametrize(
    "value",
    [
        {"op": "and", "args": []},
        {"op": "arbitrary-script"},
        {"op": "level_at_least", "value": True},
        {"op": "always", "ignored": "x"},
        {"op": "gender", "value": "other"},
        {"op": "trade", "value": "x"},
        {"op": "unknown"},
        {"op": "use_item", "value": ""},
    ],
)
def test_invalid_conditions_fail_closed(value):
    with pytest.raises(ValueError):
        validate_condition(value)


def test_every_imported_condition_validates(db):
    for table, column in (
        ("evolution_rules", "conditions"),
        ("acquisitions", "prerequisites"),
        ("milestones", "prerequisites"),
        ("shop_items", "prerequisites"),
    ):
        for (raw,) in db.execute(f"SELECT {column} FROM {table}"):
            validate_condition(json.loads(raw))


def test_evolution_translation_examples(db):
    def conditions(rule_id):
        return json.loads(db.execute("SELECT conditions FROM evolution_rules WHERE id=?", (rule_id,)).fetchone()[0])

    assert conditions(243) == {
        "op": "and",
        "args": [{"op": "use_item", "value": "dawn-stone"}, {"op": "gender", "value": "male"}],
    }
    assert conditions(148) == {"op": "level_at_least", "value": 20}
    ops = {row[0] for row in db.execute("SELECT conditions FROM evolution_rules")}
    assert any('"at_location"' in c for c in ops)
    assert any('"trade"' in c for c in ops)
    assert any('"happiness_at_least"' in c for c in ops)
    assert any('"time_of_day"' in c for c in ops)
