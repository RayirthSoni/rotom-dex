# Pokemon-Games-Chatbot

Your ultimate Pokémon gaming companion! Get tips, strategies, and trivia in this GitHub-hosted chatbot. Explore the Pokémon world like never before!

## Project overview

The repository now bundles a full knowledge-ingestion pipeline that scrapes canonical game data, normalises schemas across generations, and indexes the resulting documents into a semantic vector store. The new dataset covers move tutors, TM/HM machines, encounter tables, trainer rosters, item information, and existing Pokémon metadata.

## Requirements

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

The heavier optional dependencies (`chromadb`, `sentence-transformers`, `rank-bm25`, `sqlalchemy`) are included in the requirements file so that the knowledge base can be embedded and written to SQLite/Postgres out of the box.

## Data acquisition

Scrapers and API clients live under `scraping/`. Run all available scrapers and persist the raw JSON payloads into `data/raw/` with:

```bash
python -m scraping.cli --output-dir data/raw
```

You can scope the run to a subset of datasets by repeating the `--dataset` flag (e.g. `--dataset move_tutors --dataset items`). The scraper will fall back to bundled sample data when network access is unavailable, which keeps local development deterministic.

## Building the knowledge base

The data pipeline harmonises schemas, produces structured tables, creates a textual document corpus, and indexes embeddings into a persistent Chroma vector database. Execute the full build with:

```bash
python data_pipeline/build_kb.py \
  --raw-dir data/raw \
  --metadata-dir data \
  --output-dir data/processed
```

Key artefacts produced in `data/processed/`:

* `pokemon_kb.sqlite` – a SQLite database with tables for move tutors, machines, encounters, trainer rosters, items, and Pokémon summaries (optionally mirrored into Postgres via `--postgres-url`).
* `documents.jsonl` – the cleaned and chunked knowledge corpus.
* `vector_store/` – a Chroma persistent client populated with `all-MiniLM-L6-v2` embeddings (omit with `--skip-embeddings`).

Useful optional flags:

* `--chunk-size` / `--chunk-overlap` to control document chunking.
* `--model-name` to pick a different sentence-transformer model.
* `--skip-embeddings` to build the structured artefacts without touching the vector store.

## Retrieval helpers

The chatbot can query the knowledge base via `chatbot/retrieval.py`:

```python
from pathlib import Path
from chatbot.retrieval import KnowledgeBaseRetriever

retriever = KnowledgeBaseRetriever(
    vector_store_path=Path("data/processed/vector_store"),
    documents_path=Path("data/processed/documents.jsonl"),
)

# Pure semantic search
results = retriever.semantic_search("Where can I find Pikachu in Kanto?", limit=3)

# Faceted hybrid search (semantic + BM25)
filters = {"generation": "generation-i", "entity_type": "encounter"}
hybrid = retriever.hybrid_search("Pikachu encounter", limit=5, filters=filters, alpha=0.7)

# Metadata analytics
facets = retriever.facet_counts("generation_label", filters={"entity_type": "item"})
```

Results expose the chunk `id`, the source `text`, an aggregated `score`, and the original metadata (including generation, region, entity type, etc.).

## Automation

The Makefile provides a convenience target to refresh everything in one go:

```bash
make refresh-kb
```

This target runs the scrapers and then rebuilds the knowledge base, producing fresh JSON, SQLite tables, and embeddings.

## Repository layout

```
chatbot/            # Retrieval helpers and hybrid search utilities
configs/            # Global constants (PokeAPI, generation metadata)
data/               # Existing scraped Pokémon metadata/stats/evolutions
data/raw/           # Raw JSON for move tutors, machines, encounters, etc.
data/processed/     # Structured outputs, documents corpus, vector DB (generated)
data_pipeline/      # build_kb.py ingestion pipeline
scraping/           # HTML/API scrapers plus sample fallback datasets
```

## Notes

* Bundled sample JSON ensures the pipeline has deterministic seed data even without network access.
* The knowledge base scripts favour SQLite by default and only attempt Postgres writes when a DSN is supplied via `--postgres-url`.
* Hybrid retrieval requires the optional `rank-bm25` dependency; the module falls back to semantic-only search if it is missing.
