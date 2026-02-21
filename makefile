# ============================================================
#  rotom-dex  —  Makefile
#  All commands delegate to cli.py for consistent argument
#  handling and logging.
# ============================================================

.PHONY: help scrape-pokeapi scrape-pokemondb scrape-all \
        build-docs embed refresh-kb \
        chat server dev-ui \
        debug-stats debug-search

# ---- default target: print help ----
help:
	@python cli.py --help

# ============================================================
#  Phase 1 — Scraping
# ============================================================

scrape-pokeapi:
	python cli.py scrape pokeapi

# scrape only Gen 1 (faster for testing):  make scrape-gen1
scrape-gen1:
	python cli.py scrape pokeapi --start 1 --end 151

scrape-pokemondb:
	python cli.py scrape pokemondb

scrape-all:
	python cli.py scrape all

# ============================================================
#  Phase 2-3 — Pipeline
# ============================================================

build-docs:
	python cli.py pipeline build-docs

embed:
	python cli.py pipeline embed

# Rebuild everything from raw JSON
refresh-kb:
	python cli.py pipeline refresh

# ============================================================
#  Run
# ============================================================

server:
	python cli.py chat --interactive

dev-ui:
	streamlit run ui/app.py

# ============================================================
#  Debug helpers
# ============================================================

debug-stats:
	python cli.py debug stats

# Usage:  make debug-search Q="haunter location platinum"
debug-search:
	python cli.py debug search "$(Q)" --game platinum

# ============================================================
#  Dev setup
# ============================================================

install:
	pip install -r requirements.txt
