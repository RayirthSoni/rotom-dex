# Rotom Dex

An offline, evidence-backed **multi-game Pokémon data foundation and API**: exact game versions, version
groups and generations modelled separately; historical stats, typings, type charts, move values and
mechanics; learnsets, machines, evolution rules with typed conditions; encounters, gifts, trades, breeding
and held items; items, prices and effects; natures; curated progression; and explicit coverage and
provenance for every game and feature — with a React playthrough companion on top. It implements the
data layer and the web interface of [the product spec](docs/product-spec.md); chat is not included yet.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+ (uv will pick one up).

```sh
uv sync                                                     # runtime + dev dependencies into .venv
uv run rotom import --db data/build/rotom.sqlite3           # every main-series game (~2 min, ~200 MB)
uv run rotom import --db data/build/dev.sqlite3 --games emerald,red   # a small database in ~2 s
uv run rotom check --db data/build/rotom.sqlite3            # integrity + mechanics-aware invariants
uv run rotom coverage --db data/build/rotom.sqlite3 --format markdown   # per-game feature coverage
uv run rotom query ralts --game emerald --level 10 --db data/build/rotom.sqlite3
uv run rotom serve --db data/build/rotom.sqlite3            # FastAPI on http://127.0.0.1:8000 (/docs)
uv run pytest -q                                            # ~1 min: imports 7 games into a temp DB
```

## The web application

```sh
npm --prefix web install
npm --prefix web run build                                  # then `rotom serve` hosts it at /
uv run rotom serve --db data/build/rotom.sqlite3            # app and API on http://127.0.0.1:8000

npm --prefix web run dev                                    # development: Vite on :5173, proxying /api
npm --prefix web run test                                   # vitest
npm --prefix web run e2e                                    # playwright, desktop and mobile
```

A game-aware Pokédex, moves, items and reference tools; a team editor with defensive and offensive
analysis; saved playthroughs with a progress checklist, boss preparation and pinned plans; and
validated JSON export/import. Playthroughs live in the browser and never reach the server, which
stays read-only. In development the API is reached through Vite's proxy, so there is no cross-origin
request and no CORS configuration; `rotom serve --cors ORIGIN` is the escape hatch. See
[docs/web.md](docs/web.md), including what is honestly empty and why.

Imports and API requests are fully offline: the source is a hash-verified cache of 108 PokéAPI CSV files
pinned to one upstream commit (`data/sources/pokeapi/`). `uv run rotom fetch-sources` restores missing
cache files; `--add name…` extends the cache at the same pinned revision (network, changes the snapshot).

## What is imported

| Area | Stored as | Scope |
| --- | --- | --- |
| Games | 53 PokéAPI versions with support tiers: `validated` (Emerald, Red), `imported` (45 more main-series games incl. expansions, Let's Go, Legends), `catalog` (Japanese RGB), `excluded` (Colosseum, XD, Champions) | exact game |
| Mechanics | 12 reviewed flags per version group (abilities, natures, held items, breeding, damage split, TM reuse, …) with references | version group |
| Pokémon | 1025 species, 1351 forms, variants, egg groups, dex numbers; typings, base stats (Generation I `special`) and ability slots per generation; presence per version group | generation / version group |
| Moves | values rewound through the changelog per version group; type-based damage class before Generation IV; effects, in-game text, meta, flags | version group |
| Learnsets and machines | 778k learnset rows; TM/HM/TR ↔ item ↔ move links; reuse rules from mechanics | version group |
| Evolution | 576 rules as typed conditions (unsupported mechanics become `unknown` leaves); per-group applicability | version group |
| Acquisition | 137k rows: exact-version encounters incl. gifts, trades and static encounters; derived evolution and breeding routes; curated pack routes; held items; encounter rates | exact game |
| Items | presence per generation; per-version-group text and prices with provenance; effects; attributes; curated shops | version group / game |
| Natures, types, charts | global natures gated by mechanics; 15×15 / 17×17 / 18×18 charts | generation |
| Progression | curated milestones, trainer battles and parties (Emerald through the first Gym) | exact game |
| Ability type effects | reviewed type-based defensive modifiers (Levitate, Thick Fat, Filter, …) with the generation the modifier began; everything conditional on a move flag, weather, field or HP is recorded as a data issue instead | generation |
| Coverage | 27 features × game with `complete / partial / missing / disputed`; explicit `data_issues` | exact game |

See [docs/coverage.md](docs/coverage.md) for the generated report, [docs/sources.md](docs/sources.md)
for the source assessment and reuse review, [docs/data-model.md](docs/data-model.md) for the schema,
[docs/api.md](docs/api.md) for endpoints, [docs/web.md](docs/web.md) for the web application and
[docs/validation.md](docs/validation.md) for the record-level checks on Emerald and Red.

## Semantics that matter

- **`game` is always explicit.** Paired versions are separate games; version-group and generation data
  are resolved from the game, never the other way round.
- **Missing is not unavailable.** Absent encounters, unimported games and unknown mechanics produce
  `coverage_status: "missing"`, `data: null` or `unknown` leaves, never a claim that something cannot be
  obtained. No imported row is ever `availability='unavailable'`.
- **"Complete" is relative to the pinned source and reviewed packs**, not independent game testing.
- **Conditions are typed and three-valued.** Unknown context evaluates to unknown, so unreviewed
  prerequisites cannot make a route look reachable.
- **Everything is traceable.** `evidence_id` → sources (dataset rows, pack entries, reference pages read
  for verification, normalizer rules). Curated facts cite reference URLs; no prose is copied.
- **Imports are idempotent and refuse to overwrite.** Re-running produces the identical database;
  conflicting facts roll back; a changed source or pack means a new snapshot and a fresh database.

## Repository layout

```
rotom_dex/            Python package (uv-installable; `rotom` console script)
  db/                 connection, migration runner, migrations/0001_initial.sql
  domain/             immutable records, typed conditions
  ingestion/          cache reader, fetcher, registry, packs, writer, importers/, pipeline, coverage
  repositories/       read-side queries returning the response envelope
  calculators/        deterministic type matchups
  api/                FastAPI app, dependencies, routers
data/sources/pokeapi  pinned CSV cache + manifest + LICENSE
data/games            registry.json (support policy)
data/mechanics        version_groups.json (reviewed mechanics flags), ability_type_effects.json
data/game-packs       <game>/pack.json curated content
data/build            generated databases (gitignored)
docs/                 spec, sources, data model, API, validation, generated coverage
tests/                pytest suite (imports 7 games into a temporary database)
web/                  React + TypeScript application (Vite), vitest unit tests, playwright end-to-end
```

The earlier Emerald-only sample (ten forms, schema v1) was replaced by this multi-game schema; databases
built with it are detected and must be rebuilt.
