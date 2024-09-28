"""
Script contains functions used in scraping
"""

# Ignore pylint warnings
# pylint: disable=line-too-long

import re
from bs4.element import Tag


def clean_name(text: str) -> str:
    """Cleans the name of a Pokémon by removing the first word if it is duplicated.

    Args:
        text (str): The original Pokémon name.

    Returns:
        str: The cleaned Pokémon name.
    """
    words = text.split()
    if len(words) < 2:
        return text

    first_word = words[0]
    return " ".join(words[1:]) if first_word in words[1:] else text


def scrape_pokemon_metadata(**kwargs) -> list:
    """Function is used to scrape pokémon data

    Returns:
        list: List of dictionaries containing pokémon data
    """
    soup = kwargs.get("soup")
    generation_tag = kwargs.get("generation_tag")
    generation_data_tag = kwargs.get("generation_data_tag")
    generation_data_class = kwargs.get("generation_data_class")
    pokemon_tag = kwargs.get("pokemon_tag")
    pokemon_class = kwargs.get("pokemon_class")
    name_class = kwargs.get("name_class")
    type_class = kwargs.get("type_class")
    image_tag = kwargs.get("image_tag")

    response = []
    for generation in soup.find_all(generation_tag):
        generation_data = generation.find_next_sibling(
            generation_data_tag, class_=generation_data_class
        )
        for pokemon in generation_data.find_all(pokemon_tag, class_=pokemon_class):
            name = pokemon.find("a", class_=name_class).text.strip()
            types = [
                type.text.strip() for type in pokemon.find_all("a", class_=type_class)
            ]
            image_url = pokemon.find(image_tag)["src"]
            response.append(
                {
                    "name": name,
                    "types": types,
                    "image": image_url,
                    "generation": generation.text.strip(),
                }
            )
    return response


def scrape_pokemon_stats(**kwargs) -> list:
    """Function is used to scrape pokémon stats from table

    Returns:
        list: List of dictionaries containing pokémon stats
    """
    soup = kwargs.get("soup")
    tag = kwargs.get("tag")

    response = []
    for idx, cell in enumerate(soup.find_all(tag)):
        if idx % 10 == 0:
            image = cell.find("img")["src"]
        elif idx % 10 == 1:
            name = clean_name(cell.text.strip())
        elif idx % 10 == 2:
            types = cell.text.strip()
        elif idx % 10 == 3:
            total = int(cell.text.strip())
        elif idx % 10 == 4:
            hp = int(cell.text.strip())
        elif idx % 10 == 5:
            attack = int(cell.text.strip())
        elif idx % 10 == 6:
            defense = int(cell.text.strip())
        elif idx % 10 == 7:
            sp_atk = int(cell.text.strip())
        elif idx % 10 == 8:
            sp_def = int(cell.text.strip())
        elif idx % 10 == 9:
            speed = int(cell.text.strip())
            response.append(
                {
                    "image": image,
                    "name": name,
                    "types": types,
                    "total": total,
                    "hp": hp,
                    "attack": attack,
                    "defense": defense,
                    "sp_atk": sp_atk,
                    "sp_def": sp_def,
                    "speed": speed,
                }
            )
    return response


def scrape_pokemon_evolution_data(**kwargs) -> list:
    """Function is used to scrape pokemon evolution data

    Returns:
        list: List of dictionaries containing pokémon evolution data
    """
    soup = kwargs.get("soup")
    section_class = kwargs.get("section_class")
    pokemon_class = kwargs.get("pokemon_class")
    image_class = kwargs.get("image_class")
    types_class = kwargs.get("types_class")
    level_class = kwargs.get("evolution_level_class")
    condition_class = kwargs.get("condition_class")

    response = []
    for section in soup.find_all("div", class_=section_class):
        cards = section.find_all("div", class_=pokemon_class)

        for i, card in enumerate(cards):
            pokemon_img = card.find("img", class_=image_class)
            img_url = pokemon_img.get("src")
            name = pokemon_img.get("alt").strip()
            types = " ".join([t.text for t in card.find_all("a", class_=types_class)])

            level_info = card.find_next_sibling("span", class_=level_class)
            level_text = level_info.text.strip() if level_info else None

            # Prepare data for the current Pokémon
            evolution_paths = []

            # Find next Pokémon cards in the same evolution section
            for next_card in section.find_all("div", class_="infocard")[i + 1 :]:
                next_pokemon_img = next_card.find("img", class_=image_class)
                if next_pokemon_img:
                    evolves_to = next_pokemon_img.get("alt").strip()
                    # Find the condition for the evolution
                    condition = next_card.find_previous_sibling(
                        "span", class_=condition_class
                    )
                    condition_text = condition.text.strip() if condition else None
                    evolution_paths.append(
                        {"evolves_to": evolves_to, "condition": condition_text}
                    )

            # Append the current Pokémon data to the result list
            response.append(
                {
                    "name": name,
                    "img_url": img_url,
                    "types": types,
                    "level": level_text,
                    "evolution_paths": evolution_paths,
                }
            )

    return response
