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


def scrape_pokemon_stats() -> list:
    """Function to scrape pokemon stats from pokemondb.net

    Args:
        None

    Returns:
        list: List of dictionaries containing pokemon stats
    """
    pokemon_stats_response = requests.get(POKEMON_STATS_URL)
    pokemon_site_data = pokemon_stats_response.text
    soup = BeautifulSoup(pokemon_site_data, "lxml")
    response = scraping_helpers.extract_pokemon_stats(
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
