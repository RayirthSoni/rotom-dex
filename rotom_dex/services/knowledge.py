"""Small original explanations, with inspectable source and applicability metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data/knowledge/glossary.json"


def search(query: str, game: str | None):
    data = json.loads(PATH.read_text())
    text = query.lower()
    result = []
    for entry in data["entries"]:
        if any(re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", text) for a in entry["aliases"]):
            result.append(
                {
                    **entry,
                    "game": game,
                    "url": data["source"] + "/blob/master/" + entry["source_path"],
                    "source_snapshot": data["source_snapshot"],
                    "reviewed_at": data["reviewed_at"],
                    "review_status": "reference-reviewed",
                }
            )
    return result[:5]
