"""
Script contains logger for Pokemon Chatbot
"""

import logging

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] - %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(name="pokelogger")
