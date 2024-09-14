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
    id = kwargs.get("id")

    return soup.find(tag=tag, id=id)


