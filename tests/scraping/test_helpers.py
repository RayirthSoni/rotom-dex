from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scraping.helpers import (
    clean_name,
    scrape_pokemon_evolution_data,
    scrape_pokemon_metadata,
    scrape_pokemon_stats,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture_html(filename: str) -> BeautifulSoup:
    html = (FIXTURES / filename).read_text(encoding="utf-8")
    return BeautifulSoup(html, "lxml")


def test_clean_name_removes_duplicate_prefix():
    assert clean_name("Mr. Mime") == "Mr. Mime"
    assert clean_name("Ho-Oh") == "Ho-Oh"
    assert clean_name("Porygon Porygon") == "Porygon"


@pytest.mark.parametrize(
    "fixture_name,expected",
    [
        (
            "metadata.html",
            [
                {
                    "name": "Bulbasaur",
                    "types": ["Grass", "Poison"],
                    "image": "https://img.pokemondb.net/sprites/home/normal/2x/bulbasaur.jpg",
                    "generation": "Generation 1 Pokémon",
                },
                {
                    "name": "Charmander",
                    "types": ["Fire"],
                    "image": "https://img.pokemondb.net/sprites/home/normal/2x/charmander.jpg",
                    "generation": "Generation 1 Pokémon",
                },
                {
                    "name": "Chikorita",
                    "types": ["Grass"],
                    "image": "https://img.pokemondb.net/sprites/home/normal/2x/chikorita.jpg",
                    "generation": "Generation 2 Pokémon",
                },
            ],
        ),
    ],
)
def test_scrape_pokemon_metadata_parses_expected_rows(fixture_name, expected):
    soup = load_fixture_html(fixture_name)
    result = scrape_pokemon_metadata(
        soup=soup,
        generation_tag="h2",
        generation_data_tag="div",
        generation_data_class="infocard-list",
        pokemon_tag="div",
        pokemon_class="infocard",
        name_class="ent-name",
        type_class="itype",
        image_tag="img",
    )

    assert result == expected


def test_scrape_pokemon_stats_from_fixture():
    soup = load_fixture_html("stats.html")
    result = scrape_pokemon_stats(soup=soup, tag="td")

    assert result == [
        {
            "image": "bulbasaur.png",
            "name": "Bulbasaur",
            "types": "Grass / Poison",
            "total": 318,
            "hp": 45,
            "attack": 49,
            "defense": 49,
            "sp_atk": 65,
            "sp_def": 65,
            "speed": 45,
        },
        {
            "image": "charmander.png",
            "name": "Charmander",
            "types": "Fire",
            "total": 309,
            "hp": 39,
            "attack": 52,
            "defense": 43,
            "sp_atk": 60,
            "sp_def": 50,
            "speed": 65,
        },
    ]


def test_scrape_pokemon_evolution_data_handles_paths():
    soup = load_fixture_html("evolution.html")
    result = scrape_pokemon_evolution_data(
        soup=soup,
        section_class="infocard-list-evo",
        pokemon_class="infocard",
        image_class="img-fixed img-sprite",
        types_class="itype",
        evolution_level_class="infocard infocard-arrow",
        condition_class="infocard-arrow",
    )

    assert result == [
        {
            "name": "Bulbasaur",
            "img_url": "bulbasaur.png",
            "types": "Grass Poison",
            "level": "Level 16",
            "evolution_paths": [
                {"evolves_to": "Ivysaur", "condition": "Level 16"},
                {"evolves_to": "Venusaur", "condition": "Level 36"},
            ],
        },
        {
            "name": "Ivysaur",
            "img_url": "ivysaur.png",
            "types": "Grass Poison",
            "level": None,
            "evolution_paths": [
                {"evolves_to": "Venusaur", "condition": "Level 36"}
            ],
        },
        {
            "name": "Venusaur",
            "img_url": "venusaur.png",
            "types": "Grass Poison",
            "level": None,
            "evolution_paths": [],
        },
    ]
