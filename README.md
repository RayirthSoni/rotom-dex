# Rotom Dex

An offline Python/SQLite data foundation for **Pokémon Emerald**, implementing the first bounded slice of [the product spec](docs/product-spec.md). It contains ten default forms, their Emerald learnsets, evolution rules, encounters, related items, natures, and historical battle data. No frontend, API, chatbot, or LLM integration is included.

## Run

Python **3.10+**, with SQLite JSON functions available (standard recent Python builds). No third-party dependencies or API keys are required. Tested with Python 3.13.15. Run commands from the repository root:

```sh
python3 -m src.cli import --db data/rotom.sqlite3
python3 -m src.cli query ralts --game emerald --db data/rotom.sqlite3
python3 -m src.cli query treecko --game emerald --level 16 --db data/rotom.sqlite3
python3 -m src.cli coverage --db data/rotom.sqlite3
python3 -m src.cli check --db data/rotom.sqlite3
python3 -m unittest discover -s tests -v
```

Queries return JSON containing acquisition methods/locations/conditions, immediate incoming and outgoing evolution rules, learnsets, coverage, and resolvable evidence. Names are lowercase slugs or national Pokédex numbers. `--game` is mandatory. `--level` filters **only level-up moves**; machine, tutor, and egg entries remain visible and do not imply access to those methods. Redirect JSON to a file if desired.

The roster is Treecko, Grovyle, Sceptile, Zigzagoon, Linoone, Ralts, Kirlia, Gardevoir, Shroomish, and Breloom. Ruby has a catalog identity solely to exercise unsupported-version behavior. A Ruby query returns missing coverage and no substituted Emerald facts. An out-of-sample Pokémon likewise returns missing coverage, not “unavailable.”

## Reproducibility and evidence

The import is offline and idempotent: running it twice produces the same records and snapshot ID. The repository includes 35 gzip-compressed, unmodified PokéAPI CSV files (~3.6 MB) pinned to commit `39bc03a43df25a1898f5aa03cbc2a0abbeea30e8`, their original license, URL/retrieval-time/SHA-256 manifest, and an Emerald applicability pack. The raw files contain upstream catalog data beyond this sample; only the ten selected forms and related facts are normalized into SQLite.

Every source file is hash-checked before writing. Every fact has an evidence relationship, which resolves to source URLs, raw row selectors, retrieval times, hashes, and the snapshot ID. Changes to sources or pack metadata require a new database and review; conflicting existing facts abort the import. Identical rows are retained, not replaced. Import writes and validation run in one transaction. Schema v1 is initialized only on an empty database; other schema versions require a future migration or a fresh database.

To restore missing cache files from their pinned URLs (network required):

```sh
python3 scripts/fetch_sources.py
```

Existing files are verified and reused. The manifest keeps the initial snapshot's retrieval metadata; restore does not change the pin or provenance. Normal imports and queries never call the network. For an upstream upgrade, intentionally create and review a new manifest/pack rather than editing cached facts in place.

## Data semantics

- Exact game IDs scope all battle, acquisition, learnset, evolution, item-effect, nature, and effectiveness records. Source learnsets and item descriptions come from **Emerald version group 6**, encounters/held items from **version 9**, and historical battle data from **generation 3**. These concepts are not interchangeable.
- Species and forms have separate identities. Ability hidden status lives on the form/game/ability relationship. Height is in decimeters and weight in hectograms.
- Game availability `available` means at least one source-backed encounter or reviewed evolution ancestry exists. It does **not** mean the player can obtain it now. Acquisition status is separately `reachable`, `locked`, `unavailable`, or `unknown`; the imported routes are `unknown` pending progression/context review.
- Coverage is `complete`, `partial`, `missing`, or `disputed`. “Complete” is scoped to the selected forms and pinned source, not independently verified game completeness. Confirmed unavailability requires affirmative evidence; this sample makes **no** such claims. Empty records are never converted to unavailable.
- Conditions use validated typed AND/OR expressions. Unknown leaves carry reasons. Three-valued evaluation preserves uncertainty; arbitrary prose/scripts are rejected. The first pack supports level thresholds, owned Pokémon/items, encounter species, locations, milestones, and source encounter conditions. Other evolution mechanics require reviewed vocabulary extensions.
- Encounter percentages describe individual source slots; do not sum across different methods or conditions. Held-item percentages are conditional on encountering the named species, **not** the combined probability of finding that item. Source encounter conditions and unreviewed progression prerequisites are stored separately.
- Item effects are Emerald's short in-game descriptions, not a complete mechanical model. Move effects are explicitly NULL/missing. Nullable move power/accuracy preserve source semantics (for example variable power or moves without an accuracy check), rather than inventing values.
- Nature increase/decrease fields referring to the same stat mean neutral. The 17×17 chart includes immunities and Generation III Steel resistances; no Fairy type leaks into Emerald. No battle simulator is provided.

See [source assessment and coverage](docs/source-coverage.md) for counts, limitations, and reuse review.

## Structure

- `src/domain/`: immutable dataclasses and validated condition expressions.
- `src/database/`: constrained SQL schema and connection setup with foreign keys enabled.
- `src/ingestion/`: verified cache reading, historical normalization, transactional import and validation.
- `src/repositories/`: parameterized exact-version queries and evidence resolution.
- `src/cli.py`: import, query, coverage, and check commands.
- `data/game-packs/emerald/`: explicit roster, reviewed evolution applicability, and gap policy.
- `tests/`: offline integration and regression tests, including adversarial cross-version records.

The spec proposes SQLAlchemy/Alembic for the broader application. This first slice uses standard-library `sqlite3` and dataclasses to keep setup dependency-free; the explicit versioned SQL schema and existing package boundaries leave room for that later migration.
