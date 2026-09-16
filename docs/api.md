# HTTP API

Run `uv run rotom serve --db data/build/rotom.sqlite3` (default `http://127.0.0.1:8000`; interactive docs at
`/docs`). Every request reads the local SQLite snapshot; nothing calls the network. The database is opened
read-only per request.

## Conventions

- **`game` is required** on every game-scoped endpoint and must be an exact version slug (`emerald`, `red`,
  `omega-ruby`, …). Paired versions are separate games. Unknown slugs → `404` listing the known slugs.
- Games whose facts are not in the database (excluded spin-offs, catalog-only Japanese releases, or
  importable games not selected at import time) return `200` with `data: null`, `coverage_status:
  "missing"` and an assumption explaining why. Nothing is borrowed from a similar game.
- Entities that exist in the catalog but not in the requested game (e.g. Ralts in Red) return `data: null`
  with an assumption that this does **not** prove unobtainability.
- Pagination: `limit` 1–200 (default 50), `offset` ≥ 0; `pagination.total` is the full count. Out-of-range
  values → `422`.
- Search `q` matches slug or English name case-insensitively; identifiers accept slugs or numeric ids
  (national number for Pokémon).
- Every response uses the envelope below. `coverage` lists the features relevant to the endpoint for that
  game; `coverage_status` summarises them; `evidence` resolves every `evidence_id` present in `data`.

```json
{
  "game": {"id": 9, "slug": "emerald", "name": "Emerald", "version_group": "emerald", "generation": 3, "support_tier": "validated"},
  "snapshot_id": "…64 hex…",
  "coverage_status": "partial",
  "coverage": [{"feature": "encounters", "subject": "*", "status": "partial", "note": "…", "evidence_id": "…"}],
  "data": {},
  "assumptions": ["…"],
  "evidence": [{"id": "…", "sources": [{"source_id": "encounters", "kind": "dataset", "url": "…", "sha256": "…", "selector": "version_id=9; location_area_id=394"}]}],
  "pagination": {"limit": 50, "offset": 0, "total": 1}
}
```

## Endpoints

| Method and path | Parameters | Returns |
| --- | --- | --- |
| `GET /health` | | snapshot id and database path |
| `GET /api/games` | | every version with tier, generation and coverage counts |
| `GET /api/games/{game}` | | mechanics flags (with verification status), regions, issues |
| `GET /api/coverage` | `game` | coverage rows for the game |
| `GET /api/issues` | `game?` | explicit missing/disputed/unverified records |
| `GET /api/evidence/{id}` | | sources and selectors behind an evidence id |
| `GET /api/types` | `game` | types existing in the game's generation |
| `GET /api/type-effectiveness` | `game`, `attack`, `defense`, `defense2?` | multiplier and per-type factors from the generation chart |
| `GET /api/type-effectiveness/chart` | `game` | full chart |
| `GET /api/natures`, `/api/natures/{nature}` | `game` | natures with modifiers; `data: null` where the mechanic is absent/unverified |
| `GET /api/pokemon` | `game`, `q?`, `type?`, `limit`, `offset` | forms present in the game with generation typings |
| `GET /api/pokemon/{pokemon}` | `game` | form, species, generation types/stats/abilities, held items, dex numbers, variants |
| `GET /api/pokemon/{pokemon}/acquisition` | `game` | encounter/gift/trade/static/evolution/breeding/pack routes with typed prerequisites and encounter rates |
| `GET /api/pokemon/{pokemon}/evolution` | `game` | incoming/outgoing rules with typed conditions and per-game applicability |
| `GET /api/pokemon/{pokemon}/learnset` | `game`, `method?`, `max_level?` | eligibility rows with move values, machine item and reuse rules |
| `GET /api/moves` | `game`, `q?`, `type?`, `damage_class?`, paging | version-group values |
| `GET /api/moves/{move}` | `game` | values, effect (current wording), in-game text, meta, flags, machine |
| `GET /api/moves/{move}/learners` | `game`, paging | forms that learn the move in that version group |
| `GET /api/items` | `game`, `q?`, `category?`, paging | items indexed for the generation with prices and provenance |
| `GET /api/items/{item}` | `game` | effect, in-game text, attributes, machine link, acquisition routes, shops, wild holders |
| `GET /api/abilities`, `/api/abilities/{ability}` | `game`, `q?`, paging | abilities of the generation; detail lists holders, flavor text and changes |
| `GET /api/machines` | `game` | TM/HM/TR list with moves and reuse rules |
| `GET /api/locations` | `game`, `q?`, paging | locations with at least one route in the game |
| `GET /api/locations/{location}/encounters` | `game` | routes and encounter rates per area |
| `GET /api/milestones`, `/api/battles`, `/api/battles/{battle}` | `game` | curated progression and boss teams |

## Examples

```sh
curl 'http://127.0.0.1:8000/api/pokemon/ralts/acquisition?game=emerald'
curl 'http://127.0.0.1:8000/api/type-effectiveness?game=red&attack=ghost&defense=psychic'   # multiplier 0
curl 'http://127.0.0.1:8000/api/moves/bite?game=red'                                         # normal, physical
curl 'http://127.0.0.1:8000/api/pokemon/ralts?game=red'                                      # data null, coverage missing
curl 'http://127.0.0.1:8000/api/battles/roxanne?game=emerald'
```

## Errors

| Status | Cause |
| --- | --- |
| `400` | Semantic error inside the game (e.g. a type that does not exist in that generation) |
| `404` | Unknown game, Pokémon, move, item, ability, nature, location, battle or evidence id |
| `422` | Missing `game`, pagination or level out of range, bad enum value |
| `503` | Database file missing; run `rotom import` |
