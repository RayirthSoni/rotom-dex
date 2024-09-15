"""
Script contains functions used in scraping
"""

# Ignore pylint warnings
# pylint: disable=line-too-long

from bs4.element import Tag


def extract_table_data(**kwargs) -> Tag:
    """Function is used to extract html table content

    Returns:
        bs4.element.Tag: The first matching tag found or None if no match found
    """
    soup = kwargs.get("soup")
    tag = kwargs.get("tag")
    id = kwargs.get("  id")

    return soup.find(tag, id=id)


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


def extract_pokemon_stats(**kwargs) -> list:
    """Function is used to extract pokemon stats from table

    Returns:
        list: List of dictionaries containing pokemon stats
    """
    soup = kwargs.get("soup")
    tag = kwargs.get("tag")
    target_cell_classes = kwargs.get("target_cell_classes")

    response = []
    pokemon_data = {}
    for num, cell in enumerate(soup.find_all(tag)):
        if cell.get("class") in target_cell_classes:
            if num % 10 == 1:
                pokemon_data['name'] = clean_name(cell.text.strip())
            elif num % 10 == 2:
                pokemon_data['type'] = cell.text.strip()
            elif num % 10 == 3:
                pokemon_data['total'] = int(cell.text.strip())
            elif num % 10 == 4:
                pokemon_data['hp'] = int(cell.text.strip())
            elif num % 10 == 5:
                pokemon_data['attack'] = int(cell.text.strip())
            elif num % 10 == 6:
                pokemon_data['defense'] = int(cell.text.strip())
            elif num % 10 == 7:
                pokemon_data['sp_attack'] = int(cell.text.strip())
            elif num % 10 == 8:
                pokemon_data['sp_defense'] = int(cell.text.strip())
            elif num % 10 == 9:
                pokemon_data['speed'] = int(cell.text.strip())
                response.append(pokemon_data)
                pokemon_data = {}
    return response
