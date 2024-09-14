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

pokemon_stats_response = requests.get(POKEMON_STATS_URL)
pokemon_site_data = pokemon_stats_response.text

pokemon_stats_table = scraping_helpers.extract_table_data(
    data=pokemon_site_data, tag="table", id="pokedex"
)
