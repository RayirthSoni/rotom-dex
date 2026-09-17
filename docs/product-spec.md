# Current product direction

The approved chat-first revamp supersedes the original tracker-first design below. See [implementation status](revamp-status.md) and [the v2 contract](chat.md). Target: immediate game-aware chat, optional team/progress, all main-series games and DLC, visitor-owned tab-memory Gemini keys, grounded research, story advice and explicit competitive formats. Deep support is a reviewed-content gate, not a selector label.

The remainder is retained as historical design context; conflicting credential, navigation, coverage and completion claims are superseded.

---

# Rotom Dex — product and implementation spec

Status: proposed direction, prepared 2026-09-16. This is a specification, not an implemented application.

## Product decision

Build a responsive Pokémon playthrough companion: a game-aware Pokédex, a saved team, a progress checklist, and a conversational guide called Rotom.

The promise: **“Tell Rotom which game you're playing and where you are. Get advice you can actually use now.”**

| Approach | Strength | Limitation | Decision |
| --- | --- | --- | --- |
| Chatbot alone | Natural follow-up questions and explanations | Facts, comparisons, and plans get buried in conversations | Use chat as one interface |
| Pokédex/reference site | Fast lookup and easy browsing | Limited help deciding what to do with the information | Make this the factual foundation |
| Playthrough companion | Combines facts with your team, progress, and constraints | Requires reliable progression and availability data | Recommended product |

Initial audience: people playing or replaying the main story. Competitive players, speedrunners, and challenge runs require additional rules and datasets and come later.

## First release scope

Use Pokémon Emerald as a provisional first game: one exact version and one main-story progression path keep the initial scope bounded. This is a planning default, not a user-selected requirement. Validate its source coverage before committing to the release. The same architecture can support a different first game.

Launch with one game supported thoroughly through the Champion. Build an early internal slice through the first gym. General catalog entries may exist for other Pokémon, but the UI must distinguish catalog coverage from supported game advice.

| Feature | First-release behavior |
| --- | --- |
| Game profile | Exact version, current location, completed milestones, trade access, spoiler preference |
| Pokédex | Search by name/type; game-specific stats, types, abilities, evolution, moves, and acquisition |
| Acquisition guide | Wild encounters plus gifts, trades, breeding, and evolution where verified; prerequisites and availability status |
| My team | Up to six members with levels, moves, and optional ability/item; saved locally |
| Team analysis | Defensive weaknesses and offensive coverage from actual moves, with assumptions shown |
| Ask Rotom | Answers grounded in database results, with evidence links and follow-up actions |
| Boss preparation | Reviewed boss roster, useful existing team members, obtainable improvements, and a short plan |
| Journey | Manually checked milestones and pinned plans; no automatic game/save integration |

Defer: every generation, ROM hacks, competitive rankings, complete battle simulation, automatic save imports, voice, social features, and accounts. Add account sync after the core experience proves useful.

## Experience

Mobile navigation: **Journey · Dex · Team · Ask Rotom**. Desktop keeps the active game and team visible beside the working area. Favor readable cards, short explanations, a restrained Rotom personality, and optional playful interactions. The personality must not obscure instructions.

First use asks for a game and progress; team entry is optional. Default spoilers to hints and let the user reveal full answers deliberately.

Example flow:

1. User chooses Emerald and records their location and completed milestones.
2. User adds their starter, level, and moves.
3. User asks “Who can I catch before the next gym to help my team?”
4. Rotom resolves the next boss from progress, finds reachable acquisition options, and checks team coverage.
5. The response offers a few supported options: why each helps, how to obtain it, prerequisites, and relevant moves available by that point.
6. User opens a Pokémon card or pins a preparation checklist. Adding a recommendation to the team requires an explicit user action.

Response pattern: direct answer, game/context label, structured cards, source links, and actions such as “Compare,” “Pin plan,” or “View evolution.” Keep facts distinct from recommendations. Chat history supplements the saved profile; it is not the authoritative progress record.

For unknown game versions, ask before giving version-sensitive advice. For unknown progress, show conditional prerequisites. Unsupported games receive an explicit coverage message, not an answer borrowed from a similar game.

## Data strategy

PokéAPI is the starting source for structured catalog data, version-group learnsets, evolution information, and version-specific encounters. Cache imported responses locally as requested by its fair-use policy. Its documented resources do not constitute a complete walkthrough or progression dataset. [PokéAPI documentation](https://pokeapi.co/docs/v2)

Maintain curated game packs for progression gates, item/TM acquisition, gifts and trades, boss rosters, strategy notes, and verified corrections. Check actual records for the selected game; endpoint availability does not establish dataset completeness. Missing encounters mean “coverage unknown” until acquisition coverage is verified, not “unobtainable.”

Pokémon Showdown is a possible later source for battle mechanics and simulation. Keep competitive-format validity distinct from availability during a story playthrough. It is not the initial walkthrough source. [Pokémon Showdown repository](https://github.com/smogon/pokemon-showdown)

Do not make broad website scraping a prerequisite. The existing `pokemondb.py` placeholder should remain unused until the source's access and reuse conditions are checked. Store original strategy notes and source references instead of copying walkthrough prose. Track dataset and asset provenance separately.

Import pipeline:

1. Fetch and cache raw responses with URL, retrieval time, and content hash.
2. Normalize identifiers and game/version mappings.
3. Apply explicit game-pack overrides with supporting sources and reasons.
4. Validate references, ranges, duplicates, and version consistency.
5. Produce a coverage report for each feature and game.
6. Publish a versioned database snapshot only after validation passes.

Never silently overwrite conflicting facts. Prefer reviewed game-specific evidence according to an explicit source policy; otherwise mark the record disputed and withhold definitive advice. Normal queries use the published snapshot and do not depend on a live upstream call.

## Domain model

| Entity | Important fields |
| --- | --- |
| GameVersion | slug, version group, generation/ruleset, support status |
| Species / PokemonForm | stable IDs, relationship, names, form identity |
| PokemonGameData | form, game/ruleset, types, base stats, ability slots |
| Move / MoveGameData | identity, game/ruleset, type, category, power, accuracy, effect |
| LearnsetEntry | form, version group, move, method, level, machine/tutor reference |
| EvolutionRule | source/target form, applicable versions, trigger, typed conditions |
| Acquisition | Pokémon/item, game, location, method, encounter conditions, prerequisite expression |
| Milestone / Location | game, identifiers, prerequisites, spoiler metadata |
| TrainerBattle | game, milestone, roster, levels, moves, abilities/items when verified |
| StrategyNote | game, boss/topic, prerequisites, original content, evidence |
| Playthrough / TeamMember | profile state, constraints, member levels/moves/items |
| SourceRecord | URL, retrieval/review date, raw hash, snapshot ID, support/review status |

Represent conditions as typed, validated expressions supporting AND/OR, rather than arbitrary strings. Examples: level threshold AND known move; reachable location AND required travel ability. Preserve exceptional rules in reviewed game data and abstain when the rule is unsupported.

Distinguish generation, version group, and exact game. Encounters can differ between paired games; learnsets may be grouped. Store historical type, stat, ability, move, and battle-rule differences explicitly. Do not use current values blindly for older games. Acquisition status is one of reachable, locked, unavailable, or unknown.

Evidence references attach to individual facts/rules so the application can show which source supports a claim.

## Architecture and stack

Use the repository's Python direction: **FastAPI + Pydantic + SQLAlchemy/Alembic + SQLite initially**, with **React/TypeScript and Vite** under `web/`. These are proposed choices; no dependencies are currently configured. Move to PostgreSQL when hosted accounts or concurrent writes justify it.

Flow: web interface → FastAPI → domain services → repositories/calculators → published game database.

Chat calls those same services through a small allowlist of typed tools. The model interprets questions and explains evidence; ordinary lookup, legality checks, availability, and arithmetic happen in code. Keep the model provider behind an adapter and choose a model using the evaluation set. No fine-tuning is needed for the initial product.

Structured facts use SQL. Curated strategy notes start with full-text search and mandatory game/progress filters. Add embedding retrieval only if measured search failures justify it. A vector database is not needed for the first release.

Proposed assistant tools:

- `get_pokemon(pokemon_id, game_version)`
- `get_acquisition(entity_id, playthrough_id)`
- `get_learnset(pokemon_id, game_version, level)`
- `get_evolution(pokemon_id, playthrough_id)`
- `analyze_team(playthrough_id)`
- `get_boss_preparation(battle_id, playthrough_id)`
- `search_strategy_notes(query, game_version, allowed_milestones)`

Common result envelope: `data`, `evidence_ids`, `game_version`, `snapshot_id`, `coverage_status`, `assumptions`. Responses include structured cards and factual claims with evidence IDs. Validate referenced evidence IDs before rendering; regression evaluation must also check that the evidence actually supports the claim.

Filter future-story notes before they reach the model. Treat retrieved text as evidence, never as instructions. Restrict tool access to validated read operations; handle profile edits through explicit UI actions. Bound tool rounds, output length, request size, and per-session usage. Public visitors supply their own keys in a sensitive header; keys remain in browser tab memory and request-scoped server memory only. If the model is unavailable, the Dex, team tools, and saved plans still work.

Proposed HTTP surface:

- `GET /api/games` — feature coverage per supported game.
- `GET /api/pokemon?game=...&q=...` — searchable catalog.
- `GET /api/pokemon/{id}?game=...` — details and evidence.
- `GET /api/pokemon/{id}/acquisition?game=...` — methods and prerequisites.
- `POST /api/team/analyze` — team plus game/progress context.
- `POST /api/boss/prepare` — battle plus team/progress context.
- `POST /api/chat` — message and explicit playthrough context; text/cards/evidence response.

Local-first persistence stores profiles in the browser with JSON export/import. Server endpoints validate supplied context. Hosted account persistence is a later feature.

## Recommendation rules

First filter by game validity, acquisition prerequisites, user constraints, and verified coverage. Then rank useful options by matchup, available moves, training effort, and required consumables. Explain the tradeoffs and favor improvements to the user's existing team.

Type coverage is a helpful signal, not a battle guarantee. Use actual move types for offense, game-specific typing and relevant abilities for defense, and generation-appropriate mechanics. Unknown abilities or moves produce explicit assumptions. Without a battle simulator, offer preparation advice rather than win probabilities or guaranteed outcomes.

## Fit with the current repository

Status update 2026-09-17 (second revision): milestones 1 through 4 are met and milestone 6 is met for
Red. Emerald and Red each have a connected chain of reviewed milestones to the Hall of Fame and a
reviewed roster for every badge, Elite Four and Champion battle, so `progression` and `boss-teams`
read `complete` for both — earned by an invariant the importer checks, not by a pack asserting it.
Reviewed `location_gates` and `method_gates` replace the blanket `unknown` that used to sit on every
encounter, so recorded progress now settles most acquisition questions in those two games; that was
the single change that made "who can I catch before the next gym?" answerable at all.

Milestone 3 (chat) is implemented: `POST /api/chat` runs a bounded loop over seventeen typed tools
backed by the same services, filters spoilers server-side before the model sees anything, and
verifies every answer before returning it. **No provider credential exists in this environment, so
no live model call has ever been made**; the loop is exercised deterministically and live behaviour,
latency, cost and answer quality are unmeasured. Milestone 5 is partly met: 128 reviewed evaluation
questions are graded in code, accessibility is checked with axe on every screen in both viewports,
and the production build and container are verified — but the five-player usability study and the
cost and latency instrumentation have not been done.

The remaining 45 games are imported from the pinned source and carry no reviewed progression,
rosters, gates or shops. `docs/backlog.md` is generated from the database and says exactly what each
one still needs. The package is
`rotom_dex/` (uv project): `db/` (migrations), `domain/` (records, typed conditions), `ingestion/`
(pinned cache, registry, packs, importers, coverage), `repositories/`, `calculators/`, `services/` (playthrough-aware analysis), `api/`. Curated
content lives in `data/game-packs/<game>/pack.json`; mechanics flags in `data/mechanics/`; the support
policy in `data/games/registry.json`. The web layer is `web/` (Vite, React, TypeScript) and calls the API, never SQL. `rotom_dex/chat/` holds the provider adapters,
the tool allowlist, the bounded loop and the answer checks; it is a sibling of `services/` rather than
a subpackage because `services/` is guaranteed network-free. The tool allowlist calls
`rotom_dex/services/`, which is why those services take plain values and a context dataclass rather
than a request object.

The implementation keeps standard-library `sqlite3` with a constrained SQL schema and a numbered
migration runner instead of SQLAlchemy/Alembic: the evidence model and composite foreign keys are
expressed directly in SQL and the read side is a thin query layer. Revisit if PostgreSQL becomes necessary.

## Delivery plan and completion criteria

| Milestone | Deliverable | Completion gate |
| --- | --- | --- |
| 1. Data feasibility | Game coverage report, curated gap inventory, schemas, raw cache, representative imports | Verify evidence for encounters, moves, evolution, items, and first boss; choose first game based on results |
| 2. First-gym vertical slice | Dex, team editor, progress state, acquisition and preparation cards | A user can build and prepare a team through the first gym without chat |
| 3. Rotom chat | Typed tool calls, evidence cards, follow-ups, abstention | Chat answers agree with domain service results; handles unknown data and model outages |
| 4. Complete one game | Reviewed main-story locations, gates, bosses, notes, and acquisition coverage | Main story through Champion works within the published support scope |
| 5. Beta quality | Mobile refinement, spoiler checks, feedback, cost/latency instrumentation | Evaluation and usability gates below pass |
| 6. Second game | Separate game pack and version comparison cases | New data fits shared services; regression suite catches cross-game contamination |

Do not schedule full all-game support before measuring the cost of reviewing the first game pack. Data research and verification are the main uncertainty, not the chat UI.

Release gates. Measured results are marked; everything else remains a target.

- **Met (deterministic half).** 128 reviewed questions across 12 categories and 7 games, in `data/eval/questions.jsonl`; `rotom eval` grades them against the services and all 128 pass. Two reviewer errors were found and corrected this way. The model's own wording is graded only with `--live`, which needs a credential and has never run.
- **Met.** 226 Python tests cover dual types, immunities, historical rules, AND/OR conditions, version differences and incomplete data, none of which involve the model.
- **Met.** `move_access.eligibility` reports eligibility and access separately, and the evaluation set asserts it.
- **Met.** A fact whose evidence did not come from a tool in that request is demoted; a game with no reviewed rosters abstains.
- **Met.** Spoiler tests assert on what the provider was shown, and a leak in the model's prose discards the whole answer.
- **Not done.** The five-player usability study has not been run.
- **Not done.** Latency and cost per answer are unmeasured, because no live model call has been made. Chat is bounded at 45 s by configuration, not by observation.

The first implementation task is the data feasibility slice: one game, a small representative roster, verified acquisition/learnset/evolution facts, and first-boss preparation served as structured results.
