# Rotom Dex

Offline, evidence-backed Pokémon data foundation (Python 3.11+, SQLite, FastAPI), a React companion
under `web/`, and a grounded assistant that reaches the model only through typed tools.

## Commands

```sh
uv sync                                                  # create .venv with runtime + dev deps
uv run rotom import --db data/build/rotom.sqlite3        # all main-series games (~2 min, ~200 MB)
uv run rotom import --db data/build/dev.sqlite3 --games emerald,red
uv run rotom check --db data/build/rotom.sqlite3
uv run rotom coverage --db data/build/rotom.sqlite3 --format markdown > docs/coverage.md
uv run rotom eval --db data/build/rotom.sqlite3           # the reviewed question set, graded in code
uv run rotom coverage --db data/build/rotom.sqlite3 --format backlog > docs/backlog.md
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
  the API and the assistant call the same functions. Pydantic stays in `rotom_dex/api/`.
- `rotom_dex/services/` never touches the network. Provider adapters live in `rotom_dex/chat/`, which
  is why that package is a sibling and not a subpackage.
- Chat configuration is read per request through `ChatConfig.from_env()`. Never add a chat setting to
  `settings.py`: its values bind at import time, which is the hazard above. A test parses the syntax
  tree of `rotom_dex/chat/` to enforce this.
- The model never produces a fact. Lookup, arithmetic and availability happen in code; a chat tool is
  a thin wrapper that returns the ordinary envelope. A fact carries one `evidence_id`, never a list —
  `collect_evidence_ids` only matches string values, so a list is silently dropped.
- Spoiler filtering happens server-side, before a tool result reaches the model. Never rely on the
  browser for it.
- A reviewed `location_gates` entry replaces the blanket `unknown` on that location's encounters, and
  a `method_gates` entry adds what the method itself costs. A method with no reviewed gate keeps an
  explicit unknown rather than inheriting the location's verdict.
- `progression` and `boss-teams` reach `complete` only by passing an invariant the importer checks —
  a connected milestone chain to a declared `main_story_end`, and a roster on every badge, Elite Four
  and Champion milestone. A pack cannot simply assert completeness.
