# Current web experience

The home route is immediate chat with an optional game selector, conversation history, visitor Gemini connection, progress/cancel/retry/copy controls, and optional saved context. Reference routes remain available through Explore tools. `/competitive` provides format selection, Showdown import/export, team validation and damage ranges. `/g/:game` now redirects to Ask. Existing team/Journey deep links remain intact.

Conversations use versioned browser-local storage. API keys are in a separate memory-only store and disappear on reload. Playthrough save version 2 preserves version-1 teams, milestones and plans while allowing optional training/modifier fields. See [status](revamp-status.md) for remaining work.

The following original reference-screen documentation is retained for those deep links; old descriptions of primary navigation and chat setup are superseded.

---

# Web application

A React + TypeScript playthrough companion under [`web/`](../web), served by the same FastAPI process
that serves the API. It reads the published snapshot and stores nothing but your own progress, in
your own browser.

## Running it

```sh
uv run rotom import --db data/build/rotom.sqlite3     # once, ~2 min for every game
npm --prefix web install

# Development: two processes, one origin. Vite proxies /api and /health to the API, so the browser
# never makes a cross-origin request and no CORS configuration is involved.
uv run rotom serve --db data/build/rotom.sqlite3 --reload   # :8000
npm --prefix web run dev                                    # :5173

# Production: one process. The built bundle is mounted at / by the API itself.
npm --prefix web run build
uv run rotom serve --db data/build/rotom.sqlite3            # http://127.0.0.1:8000
```

`rotom serve --cors http://localhost:5173` is the escape hatch for a split-origin setup; CORS is off
by default and the mount is skipped when `web/dist` does not exist, so an API-only server still runs.
`--no-web` forces that.

## Architecture

```
web/src/
  api/         client.ts (one ApiError for every failure), endpoints.ts, types.ts, queries.ts,
               SnapshotProvider.tsx (snapshot id, backend reachability)
  state/       schema.ts (zod), playthroughs.ts (zustand + persist), transfer.ts (export/import)
  domain/      conditions.ts (phrasing for the typed prerequisite AST)
  components/  QueryBoundary, states, ConditionTree, Provenance, primitives
  features/    games/ pokedex/ moves/ items/ tools/ team/ journey/ playthroughs/
```

Four decisions carry most of the weight:

**Payload types are hand-written.** `Envelope.data` is `Any` in the OpenAPI document, so generated
types would be `unknown` exactly where types are worth having. `web/src/api/types.ts` mirrors the SQL
in `rotom_dex/repositories/`, and `tests/test_web_contract.py` fails if the backend stops matching it.

**The snapshot id is the whole cache story.** Changing a source, a pack or the normalizer produces a
new snapshot and a new database, so every query is cached indefinitely under
`[snapshot_id, …]`. `/health` is read once at boot; if the id differs from the one last seen, the
cache is dropped. That is the only invalidation that exists.

**`data: null` is a state, not an error.** `QueryBoundary` turns every query into one of six states —
`loading`, `offline`, `database_missing`, `error`, `no_claim`, `empty`, `ready` — and `no_claim`
renders the API's own `assumptions` verbatim. Because it is one component, "missing is not
unavailable" holds by construction rather than by reviewer discipline across a dozen screens.

**The browsed game and the played game are separate.** The URL owns the first (`/g/:game/…`), a
playthrough owns the second. Switching games changes a route param, so every query key changes and
React Query refetches under new keys; no invalidation is written anywhere, which is precisely why
browsing Red cannot write to an Emerald save. When the two differ the shell says so and offers to
switch or to start a second playthrough.

## Saved data

Everything lives in `localStorage` under `rotom-dex.playthroughs`. A playthrough holds its game,
current location, visited locations, completed milestones, bag, trade access, spoiler preference,
closed-world flags, up to six team members and pinned plans — references only, never Pokémon data.

Export writes `{schema: "rotom-dex/playthroughs", version, exportedAt, snapshotId, playthroughs,
activeId}`. Import validates the whole file with zod before applying anything: every problem is
reported with its field path, a file from a newer build is refused rather than coerced, and a file
exported against a different snapshot is imported with a warning so it degrades visibly instead of
disappearing. Nothing is ever partially applied.

## What is honestly empty, and why

The interface has a lot of "not recorded" in it. That is the data being truthful, not the interface
failing. From the current snapshot:

| Where | What you see | Why |
| --- | --- | --- |
| Journey, for 45 of 47 games | "No milestones reviewed for <game> yet" | Progression is curated per game with reference URLs. Emerald (49) and Red (31) have a connected chain to the Hall of Fame; nothing else has any. |
| Boss preparation, for 45 of 47 games | An explanation instead of a plan | `trainer_battles` holds 26 reviewed rosters, all of them Emerald's and Red's. |
| Acquisition, in 45 of 47 games | "Not determined" rather than a verdict | Without a reviewed location gate an encounter keeps `unknown("progression gates not reviewed")`, and no context can settle it. In Emerald and Red, reviewed gates mean recorded progress settles most encounters. |
| Acquisition, fishing everywhere | "Not determined" | Rod acquisition is not reviewed in any game, so a fishing slot stays unknown even in a reviewed location. |
| Ask Rotom, with no key configured | "Rotom is not available", and nothing else changes | Chat is the only feature that needs a credential. Every other screen is unaffected. |
| Tutor moves, every game | "Eligible — access unknown" | 50k learnset rows say a Pokémon can be taught a move by a tutor; the `tutors` table, which would say where the tutor stands, is empty. |
| Natures and Abilities in Generation I–II | The field is absent, with a sentence | `game_mechanics` records the mechanic as absent. A missing flag instead reads "unverified", which is a different claim. |
| Anywhere, offline | A type-coloured disc where a sprite would be | The pinned source carries no images. Sprites and artwork are hotlinked from the PokéAPI sprites repository, derived in the browser from form ids the API already returns (`web/src/domain/sprites.ts`), and credited under a chat answer's sources. It is the one runtime fetch the interface makes; when it fails the disc stays and nothing else changes. |

Ticking "my completed-milestone list is complete" is what turns *not determined* into a real verdict.
In Emerald and Red that now answers **what can I catch now**; everywhere else it still answers only
*what is blocking me*, and the interface says so where you tick it.

## Tests

```sh
npm --prefix web run test         # vitest: client, envelope states, condition phrasing, save files, store
npm --prefix web run e2e          # playwright, desktop + Pixel 5, against a real server and database
```

The end-to-end suite includes an accessibility pass: every screen is checked with axe in both
projects, and any serious or critical WCAG 2.1 AA violation fails the build.

Playwright builds its own two-game database (`data/build/e2e.sqlite3`, about two seconds) and serves
the built bundle through `rotom serve`, so the end-to-end suite exercises the production arrangement.
Emerald and Red are chosen deliberately: Emerald has the only reviewed progression and roster, Red
has neither and no Abilities, Natures, held items or breeding.
