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

log_handler = logging.StreamHandler()
log_handler.setLevel(logging.INFO)  # You can set the desired log level for console output

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log_handler.setFormatter(log_formatter)

logger.addHandler(log_handler)