"""
Script contains functions used to scrape pokemon data
"""

# Ignore pylint warnigns
# pylint: disable=line-too-long
# pylint: disable=missing-timeout


import requests
import scraping.helpers as scraping_helpers

from bs4 import BeautifulSoup

from configs.constants import Constants

POKEMONDB_URL = Constants.POKEMON_DB_URL
POKEMON_DATA = Constants.POKEMON_DATA
POKEMON_STATS_URL = Constants.POKEMON_STATS_URL
POKEMON_EVOLUTION_URL = Constants.POKEMON_EVOLUTION_URL


def get_pokemon_stats() -> list:
    """Function to get pokemon stats from pokemondb.net

    Returns:
        list: List of dictionaries containing pokemon stats
    """
    pokemon_stats_response = requests.get(POKEMON_STATS_URL)
    pokemon_site_data = pokemon_stats_response.text
    soup = BeautifulSoup(pokemon_site_data, "lxml")
    response = scraping_helpers.scrape_pokemon_stats(
        soup=soup,
        tag="td",
        target_cell_classes=[
            ["cell-name"],
            ["cell-icon"],
            ["cell-num", "cell-total"],
            ["cell-num"],
        ],
    )
    return response


def get_pokemon_evolution_data():
    """Function to get pokemon evolution data from pokemondb.net

    Returns:
        list: List of dictionaries containing pokemon evolution data
    """
    pokemon_evolution_response = requests.get(POKEMON_EVOLUTION_URL)
    pokemon_site_data = pokemon_evolution_response.text
    response = soup = BeautifulSoup(pokemon_site_data, "lxml")
    scraping_helpers.scrape_pokemon_evolution_data(
        soup=soup,
        section_class="infocard-list-evo",
        pokemon_class="infocard",
        image_class="img-fixed img-sprite",
        types_class="itype",
        level_class="infocard infocard-arrow",
        condition_class="infocard-arrow",
    )
    return response
