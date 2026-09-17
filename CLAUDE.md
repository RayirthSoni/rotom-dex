# Rotom Dex

Offline, evidence-backed Pokémon data foundation (Python 3.11+, SQLite, FastAPI). No frontend or LLM code yet.

## Commands

```sh
uv sync                                                  # create .venv with runtime + dev deps
uv run rotom import --db data/build/rotom.sqlite3        # all main-series games (~2 min, ~200 MB)
uv run rotom import --db data/build/dev.sqlite3 --games emerald,red
uv run rotom check --db data/build/rotom.sqlite3
uv run rotom coverage --db data/build/rotom.sqlite3 --format markdown > docs/coverage.md
uv run rotom serve --db data/build/rotom.sqlite3
uv run pytest -q && uv run ruff check . && uv run ruff format --check .

npm --prefix web install                                 # React app under web/
npm --prefix web run build                               # then `rotom serve` hosts it at /
npm --prefix web run dev                                 # Vite on :5173, proxying /api to :8000
npm --prefix web run test && npm --prefix web run e2e    # vitest, then playwright (desktop + mobile)
```

## Rules of the data

- Every fact row has `evidence_id`; facts scoped at generation / version group / exact game (see docs/data-model.md).
- Never write `availability='unavailable'` from source data; missing rows are `unknown`/coverage `missing`.
- Curated facts live in `data/game-packs/<game>/pack.json` with reference URLs; never copy prose.
- Changing sources, packs or `NORMALIZER` changes the snapshot id; rebuild databases, don't patch them.
- Imports are idempotent; conflicting facts abort the transaction. Keep it that way.
- New API modules take `db` via `Depends(get_db)`. Never import `DEFAULT_DB`: it is bound at import
  time in three places, so a module that imports it reads the wrong database under pytest.
- Derivations never write `unavailable`, and never overwrite a stored `availability`. A verdict
  derived from a player's progress belongs under `derived`.
- Services live in `rotom_dex/services/`, take plain values, and import no web framework, so the CLI,
  the API and a future assistant call the same functions. Pydantic stays in `rotom_dex/api/`.
