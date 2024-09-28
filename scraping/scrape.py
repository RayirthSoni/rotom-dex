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
POKEMONS_LIST_URL = Constants.POKEMONS_LIST_URL


# TODO: ADD PARALLEL PROCESSING FOR SCRAPING FOR FASTER SCRAPING


def get_pokemons() -> list:
    website = requests.get(POKEMONS_LIST_URL)
    pokemon_data = website.text
    soup = BeautifulSoup(pokemon_data, "lxml")
    response = scraping_helpers.scrape_pokemons(
        soup=soup,
        generation_tag="h2",
        generation_data_tag="div",
        generation_data_class="infocard-list",
        pokemon_tag="div",
        pokemon_class="infocard",
        name_class="ent-name",
        types_class="itype",
        image_tag="img",
    )
    return response


def get_pokemon_stats() -> list:
    """Function to get pokemon stats from pokemondb.net

    Returns:
        list: List of dictionaries containing pokemon stats
    """
    website = requests.get(POKEMON_STATS_URL)
    pokemon_stats_data = website.text
    soup = BeautifulSoup(pokemon_stats_data, "lxml")
    response = scraping_helpers.scrape_pokemon_stats(
        soup=soup,
        tag="td"
    )
    return response


def get_pokemon_evolution_data():
    """Function to get pokemon evolution data from pokemondb.net

    Returns:
        list: List of dictionaries containing pokemon evolution data
    """
    pokemon_evolution = requests.get(POKEMON_EVOLUTION_URL)
    pokemon_evolution_data = pokemon_evolution.text
    soup = BeautifulSoup(pokemon_evolution_data, "lxml")
    response = scraping_helpers.scrape_pokemon_evolution_data(
        soup=soup,
        section_class="infocard-list-evo",
        pokemon_class="infocard",
        image_class="img-fixed img-sprite",
        types_class="itype",
        level_class="infocard infocard-arrow",
        condition_class="infocard-arrow",
    )
    return response


def get_pokemon_location(**kwargs):
    pass


# def get_pokemon_location_
