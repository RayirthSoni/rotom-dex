"""
Constants
"""

# Ignore pylint warnings
# pylint: disable = line-too-long

import os


class Constants:
    """
    Constants configurations
    """

    POKEMON_DB_URL = "https://pokemondb.net/"
    POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"
    POKEAPI_CSV_BASE_URL = (
        "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
    )
    POKEMON_DATA = {
        "pokedex": "pokedex",
        "moves": "move",
        "types": "type",
        "abilities": "ability",
        "items": "item",
        "evolution": "evolution",
        "pokemon_locations": "location",
        "sprite_gallery": "sprites",
    }
    POKEMON_STATS_URL = os.path.join(POKEMON_DB_URL, POKEMON_DATA.get("pokedex"), "all")
    POKEMON_EVOLUTION_URL = os.path.join(POKEMON_DB_URL, POKEMON_DATA.get("evolution"))
    POKEMONS_LIST_URL = os.path.join(POKEMON_DB_URL, POKEMON_DATA.get("pokedex"), "national")

    GENERATION_CONFIG = {
        "generation-i": {
            "label": "Generation I",
            "regions": ["kanto"],
            "version_groups": ["red-blue", "yellow"],
        },
        "generation-ii": {
            "label": "Generation II",
            "regions": ["johto"],
            "version_groups": ["gold-silver", "crystal"],
        },
        "generation-iii": {
            "label": "Generation III",
            "regions": ["hoenn", "kanto"],
            "version_groups": ["ruby-sapphire", "emerald", "firered-leafgreen"],
        },
        "generation-iv": {
            "label": "Generation IV",
            "regions": ["sinnoh", "johto"],
            "version_groups": ["diamond-pearl", "platinum", "heartgold-soulsilver"],
        },
        "generation-v": {
            "label": "Generation V",
            "regions": ["unova"],
            "version_groups": ["black-white", "black-2-white-2"],
        },
        "generation-vi": {
            "label": "Generation VI",
            "regions": ["kalos"],
            "version_groups": ["x-y", "omega-ruby-alpha-sapphire"],
        },
        "generation-vii": {
            "label": "Generation VII",
            "regions": ["alola"],
            "version_groups": ["sun-moon", "ultra-sun-ultra-moon", "lets-go-pikachu-lets-go-eevee"],
        },
        "generation-viii": {
            "label": "Generation VIII",
            "regions": ["galar", "hisui"],
            "version_groups": ["sword-shield", "the-isle-of-armor", "the-crown-tundra", "brilliant-diamond-shining-pearl", "legends-arceus"],
        },
        "generation-ix": {
            "label": "Generation IX",
            "regions": ["paldea"],
            "version_groups": ["scarlet-violet"],
        },
    }
