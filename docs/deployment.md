# Deployment

The server is read-only. It opens one SQLite connection per request against a published snapshot and
calls nothing over the network, except the optional chat provider. There is no application database
to migrate at runtime, no write path, and no user data on the server at all.

## What is deployed

One process serving two things on one origin:

- `GET /api/…` — the read API and the playthrough-aware services.
- `/` — the built single-page application, mounted only when `web/dist` exists.

Because both come from the same origin there is no CORS configuration in the normal arrangement.
`ROTOM_CORS_ORIGINS` exists only for a split-origin setup.

## Build and run

```sh
uv sync
npm --prefix web ci && npm --prefix web run build
uv run rotom import --db data/build/rotom.sqlite3     # ~2 min, ~185 MB, all 47 importable games
uv run rotom check   --db data/build/rotom.sqlite3     # integrity and mechanics-aware invariants
uv run rotom eval    --db data/build/rotom.sqlite3     # the reviewed question set
uv run rotom serve   --db data/build/rotom.sqlite3 --host 0.0.0.0 --port 8000
```

`--games emerald,red` builds a 14 MB database in about two seconds and covers both reviewed games.

### Container

```sh
docker compose build                # ROTOM_GAMES=emerald,red for a small image
docker compose up -d
curl -fs localhost:8000/health
```

The snapshot is built **during the image build** and the build fails if `rotom check` fails, so a
container that starts is a container whose data passed its invariants. The image needs no volume and
no network at runtime.

## The snapshot rule

Everything hangs off one identifier. `snapshot_id` is
`sha256(source manifest + reviewed packs + NORMALIZER)`, so changing a source file, a game pack or a
normalisation rule produces a different id.

- **Rebuild, never patch.** Importing into a database that already holds a different snapshot aborts
  with *"Different source snapshot; import into a new database and review the changes"*. Delete the
  file and import again; do not try to migrate it.
- Imports are idempotent: re-running with the same inputs produces the same rows. A conflicting fact
  rolls the whole transaction back.
- The browser caches everything under the snapshot id, so a new snapshot invalidates client caches
  by itself. There is nothing to purge.
- Regenerate `docs/coverage.md` after any pack change:
  `uv run rotom coverage --db … --format markdown > docs/coverage.md`.

Schema changes are separate and are numbered SQL files under `rotom_dex/db/migrations/`. They are
applied automatically by `rotom import`, and every request checks that the database is not behind the
code — a database that is returns `503` rather than answering from a stale schema.

## Configuration

See `.env.example` for the full list. Nothing is loaded from a file automatically; export these in
your process manager or container runtime.

| Variable | Purpose |
| --- | --- |
| `ROTOM_DB` | The snapshot to read |
| `ROTOM_WEB_DIST` / `ROTOM_SERVE_WEB` | Where the bundle is, and whether to mount it |
| `ROTOM_CORS_ORIGINS` | Only for a split-origin deployment |
| `ROTOM_CHAT_PROVIDER` / `ROTOM_CHAT_MODEL` | Which model answers, if any |
| `ROTOM_GEMINI_API_KEY` | Local CLI evaluation only; ignored by public chat |
| `ROTOM_CHAT_*` bounds | Tool rounds, timeouts, message size, rate limit |
| `ROTOM_CHAT_RESEARCH` | CLI research default; public visitors choose research per request |

### Secrets

Public chat requires each visitor's `X-Rotom-Gemini-Key` header. No environment-key fallback exists. The same visitor key is used for grounded research. It is held in tab memory and request-scoped server objects, never in browser persistence or server storage. Require HTTPS outside localhost; redact this header in reverse proxies, access logs and APM. Never log chat bodies or provider request objects.

Install Node 22+ and run `npm ci --prefix battle` alongside `uv sync`. The container installs the pinned battle packages in a separate build stage. Per-process concurrency/rate limits need additional shared enforcement before a multi-worker public deployment.

## Backups

There is no server-side user data to back up. Playthroughs live in the player's browser under the
`localStorage` key `rotom-dex.playthroughs`, and are not persisted by the server. Selected context is sent to the API and model as needed. Conversations use `rotom-dex.conversations`; credentials are excluded.

- **For players:** the Playthroughs screen exports a validated JSON document containing every
  playthrough and the snapshot id it was made against. Import refuses a file from a newer save
  version rather than coercing it, and reports every invalid field by path instead of partially
  applying. That export *is* the backup.
- **For operators:** back up nothing but the repository. The database is a build artifact —
  reproducible byte-for-byte from the pinned source cache and the reviewed packs, which is why
  `data/build/` is not tracked.
- **If you add hosted accounts later**, that is the first thing in this project that will need a real
  backup policy, and the first thing that will need a write path.

## Operational notes

- `GET /health` returns the snapshot id and the database path. Use it as the readiness probe; it is
  what the compose health check and CI use.
- Latency: the read endpoints are local SQLite queries. Chat is bounded by
  `ROTOM_CHAT_DEADLINE` (45 s by default) and answers a `504` if the provider exceeds its timeout.
- Rate limiting on `/api/chat` is in-process and therefore per worker. It is enough to stop one
  browser looping; it is not a distributed quota, and it deliberately does not apply to the read
  endpoints.
- Scale by running more processes against the same read-only file. There is no shared mutable state.
