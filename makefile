.PHONY: local-pokemon

local-pokemon:
	python server.py

.PHONY: refresh-kb

refresh-kb:
	python -m scraping.cli --output-dir data/raw
	python data_pipeline/build_kb.py --raw-dir data/raw --metadata-dir data --output-dir data/processed
