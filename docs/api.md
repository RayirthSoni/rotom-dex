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
| `GET /api/coverage/matrix` | `notes?` | every game against every feature in one response |
| `GET /api/vocabulary` | `game` | filter vocabularies as they occur in that game, plus its mechanics flags |
| `GET /api/issues` | `game?` | explicit missing/disputed/unverified records |
| `GET /api/evidence/{id}` | | sources and selectors behind an evidence id |
| `GET /api/types` | `game` | types existing in the game's generation |
| `GET /api/type-effectiveness` | `game`, `attack`, `defense`, `defense2?` | multiplier and per-type factors from the generation chart |
| `GET /api/type-effectiveness/chart` | `game` | full chart |
| `GET /api/natures`, `/api/natures/{nature}` | `game` | natures with modifiers; `data: null` where the mechanic is absent/unverified |
| `GET /api/pokemon` | `game`, `q?`, `type?`, `limit`, `offset` | forms present in the game with generation typings |
| `GET /api/pokemon/{pokemon}` | `game`, `include?`, `max_level?` | form, species, generation types/stats/abilities, held items, dex numbers, variants. `include=acquisition,evolution,learnset` (or `all`) merges the sub-resources; the default `core` is the card alone |
| `GET /api/pokemon/{pokemon}/acquisition` | `game` | encounter/gift/trade/static/evolution/breeding/pack routes with typed prerequisites and encounter rates |
| `GET /api/pokemon/{pokemon}/evolution` | `game` | incoming/outgoing rules with typed conditions and per-game applicability |
| `GET /api/pokemon/{pokemon}/evolution-chain` | `game` | the whole family as nodes and edges, each edge carrying this group's applicability |
| `GET /api/pokemon/{pokemon}/learnset` | `game`, `method?`, `max_level?` | eligibility rows with move values, machine item and reuse rules |
| `GET /api/moves` | `game`, `q?`, `type?`, `damage_class?`, paging | version-group values |
| `GET /api/moves/{move}` | `game` | values, effect (current wording), in-game text, meta, flags, machine |
| `GET /api/moves/{move}/learners` | `game`, paging | forms that learn the move in that version group |
| `GET /api/items` | `game`, `q?`, `category?`, paging | items indexed for the generation with prices and provenance |
| `GET /api/items/{item}` | `game` | effect, in-game text, attributes, machine link, acquisition routes, shops, wild holders |
| `GET /api/abilities`, `/api/abilities/{ability}` | `game`, `q?`, paging | abilities of the generation; detail lists holders, flavor text and changes |
| `GET /api/machines` | `game` | TM/HM/TR list with moves and reuse rules |
| `GET /api/tutors` | `game` | tutor locations and costs. Empty for every game; see the note below |
| `GET /api/locations` | `game`, `q?`, paging | locations with at least one route in the game |
| `GET /api/locations/{location}/encounters` | `game` | routes and encounter rates per area |
| `GET /api/milestones`, `/api/battles`, `/api/battles/{battle}` | `game` | curated progression and boss teams |

`include` is explicit because the merged card is large: every learnset row carries its move's values
and every sub-resource contributes evidence, so `include=all` for a late-generation Pokémon runs to
hundreds of kilobytes. Ask for the panels you are about to render.

`GET /api/tutors` returns an empty list for every game, alongside the number of tutor-eligible
learnset rows. That is the point: the source establishes *eligibility* for tens of thousands of
move/Pokémon pairs and records no tutor locations at all, so tutor access is `unknown` everywhere and
never `unavailable`.

## Playthrough-aware services

These are `POST` because the body is a playthrough context held in the browser, not a resource
identifier. The context is validated against the requested game before anything is derived, and the
response is the same envelope, so coverage, assumptions and evidence travel with every answer.

| Method and path | Body | Returns |
| --- | --- | --- |
| `POST /api/team/analyze` | `{context}` | defensive profile per member and offensive coverage from the team's actual moves |
| `POST /api/boss/prepare` | `{context, battle}` | the reviewed roster, how the types line up, level deltas and reachable supplies |
| `POST /api/acquisition/reachability` | `{context, pokemon[], items[]}` | each route's prerequisites evaluated against recorded progress |
| `POST /api/pokemon/{pokemon}/move-access` | `{context, pokemon, member?}` | every eligible move, with access to its method reported separately |
| `POST /api/pokemon/{pokemon}/evolution-requirements` | `{context, pokemon, member?}` | evolution rules evaluated against one member |

The context, with every field optional except `game`:

```json
{
  "game": "emerald",
  "current_location": "rustboro-city",
  "visited_locations": ["littleroot-town"],
  "completed_milestones": ["littleroot-arrival"],
  "bag": ["oran-berry"],
  "trade_access": "none | local | any",
  "spoiler_level": "none | hint | full",
  "closed_world": ["milestones", "locations", "bag", "party", "trade"],
  "team": [{"pokemon": "ralts", "level": 12, "moves": ["confusion"], "nature": "modest", "ability": "synchronize", "held_item": null, "nickname": null}]
}
```

Unknown keys are rejected rather than ignored, a team is capped at six and a member at four moves,
and a nature, ability or held item is a `400` in a game whose `game_mechanics` say the mechanic is
absent. Unknown identifiers are `404`.

### `closed_world`, and why a verdict can differ

`evaluate_condition` is three-valued: an absent context key yields unknown, a present but unsatisfied
key yields false. So whether a prerequisite reads as *locked* or *unknown* depends on which keys are
populated, and that is a claim about what the player knows — not about the game. `closed_world` makes
the claim explicit, one leaf family at a time.

| Family | Leaves it populates | Effect when listed and unsatisfied |
| --- | --- | --- |
| `milestones` | `milestone` | `locked`, with the milestone named in `blocked_by` |
| `locations` | `at_location` | `locked` |
| `bag` | `has_item`, `use_item`, `held_item` | `locked` |
| `party` | `has_pokemon`, `party_has_pokemon` | `locked` |
| `trade` | `trade` | `locked` |

A family that is not listed is simply absent from the context, so its leaves stay unknown. Families
this product does not track at all — time of day, encounter conditions, friendship, beauty, affection,
weather, stat relations — are never populated, and say so in `unknown_because`. Every response lists
the assumption it applied.

Each route carries the stored `availability` untouched, plus a `derived` block:

```json
{"status": "locked", "evaluation": false,
 "blocked_by": [{"op": "milestone", "value": "stone-badge"}],
 "unknown_because": []}
```

`derived.status` is one of `reachable | locked | unknown`. **No derivation ever produces
`unavailable`**: that state is reserved for reviewed evidence that something cannot be obtained, which
no evaluation of a player's progress can establish.

## Examples

```sh
curl 'http://127.0.0.1:8000/api/pokemon/ralts/acquisition?game=emerald'
curl 'http://127.0.0.1:8000/api/type-effectiveness?game=red&attack=ghost&defense=psychic'   # multiplier 0
curl 'http://127.0.0.1:8000/api/moves/bite?game=red'                                         # normal, physical
curl 'http://127.0.0.1:8000/api/pokemon/ralts?game=red'                                      # data null, coverage missing
curl 'http://127.0.0.1:8000/api/battles/roxanne?game=emerald'
curl 'http://127.0.0.1:8000/api/pokemon/ralts?game=emerald&include=all&max_level=20'
curl -X POST 'http://127.0.0.1:8000/api/team/analyze' -H 'content-type: application/json' \
  -d '{"context":{"game":"emerald","team":[{"pokemon":"ralts","level":12,"moves":["confusion"]}]}}'
```

## Errors

| Status | Body | Cause |
| --- | --- | --- |
| `400` | `{"detail": string}` | Semantic error inside the game (e.g. a type that does not exist in that generation) |
| `404` | `{"detail": string}` | Unknown game, Pokémon, move, item, ability, nature, location, battle or evidence id |
| `422` | `{"detail": [{"loc": [...], "msg": string, "type": string}]}` | Parameter or body validation failed |
| `503` | `{"detail": string}` | Database file missing or behind the code's migrations; run `rotom import` |

Note the two different shapes: `422` comes from FastAPI's own validation and is a list, the rest are a
string. A client needs a branch for each. An unexpected exception is a `500`; only `SemanticError` is
mapped to `400`, so a bug in the service layer does not masquerade as a client error.
