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


def preprocess_text(text):
    """Preprocess and clean text by removing unnecessary characters.

    Args:
        text (str): The raw text to be cleaned.

    Returns:
        str: The cleaned text.
    """
    cleaned_text = re.sub(r"[()\.,]", "", text)

    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    return cleaned_text


def scrape_table_data(**kwargs) -> Tag:
    """Function is used to scrape html table content

    Returns:
        bs4.element.Tag: The first matching tag found or None if no match found
    """
    soup = kwargs.get("soup")
    tag = kwargs.get("tag")
    data_id = kwargs.get("data_id")

    return soup.find(tag, id=data_id)


def scrape_pokemon_stats(**kwargs) -> list:
    """Function is used to scrape pokémon stats from table

    Returns:
        list: List of dictionaries containing pokémon stats
    """
    soup = kwargs.get("soup")
    tag = kwargs.get("tag")
    target_cell_classes = kwargs.get("target_cell_classes")

    response = []
    pokemon_data = {}
    for num, cell in enumerate(soup.find_all(tag)):
        img_tag = cell.find("img")
        if img_tag:
            pokemon_data["image_url"] = img_tag.get("src")
        if cell.get("class") in target_cell_classes:
            if num % 10 == 1:
                pokemon_data["name"] = clean_name(cell.text.strip())
            elif num % 10 == 2:
                pokemon_data["type"] = cell.text.strip()
            elif num % 10 == 3:
                pokemon_data["total"] = int(cell.text.strip())
            elif num % 10 == 4:
                pokemon_data["hp"] = int(cell.text.strip())
            elif num % 10 == 5:
                pokemon_data["attack"] = int(cell.text.strip())
            elif num % 10 == 6:
                pokemon_data["defense"] = int(cell.text.strip())
            elif num % 10 == 7:
                pokemon_data["sp_attack"] = int(cell.text.strip())
            elif num % 10 == 8:
                pokemon_data["sp_defense"] = int(cell.text.strip())
            elif num % 10 == 9:
                pokemon_data["speed"] = int(cell.text.strip())
                response.append(pokemon_data)
                pokemon_data = {}
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
