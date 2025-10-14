"""Command line helpers to download raw Pokémon game data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Dict

from . import (
    get_encounter_data,
    get_item_data,
    get_move_tutor_data,
    get_pokemon_evolution_data,
    get_pokemon_metadata,
    get_pokemon_stats,
    get_tm_hm_data,
    get_trainer_rosters,
)

SCRAPERS: Dict[str, Callable[[], list]] = {
    "pokemon_metadata": get_pokemon_metadata,
    "pokemon_stats": get_pokemon_stats,
    "pokemon_evolution": get_pokemon_evolution_data,
    "move_tutors": get_move_tutor_data,
    "machines": get_tm_hm_data,
    "encounters": get_encounter_data,
    "trainer_rosters": get_trainer_rosters,
    "items": get_item_data,
}


def _write_json(path: Path, payload: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def run_scrapers(output_dir: Path, datasets: list[str] | None = None) -> None:
    selected = datasets or list(SCRAPERS.keys())
    for name in selected:
        if name not in SCRAPERS:
            raise KeyError(f"Unknown dataset '{name}'")
        scraper = SCRAPERS[name]
        payload = scraper()
        _write_json(output_dir / f"{name}.json", payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory where JSON payloads will be written.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        help=(
            "Optional dataset name. Repeat the flag to request multiple datasets. "
            "Defaults to downloading every supported dataset."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_scrapers(args.output_dir, args.dataset)


if __name__ == "__main__":
    main()
