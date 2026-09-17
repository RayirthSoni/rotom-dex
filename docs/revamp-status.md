# Game-aware assistant implementation status

Updated 2026-09-17. This is an implementation record, not a declaration of all-game deep support. No public deployment was performed. Existing game databases were not rewritten.

## Implemented

| Area | Result |
| --- | --- |
| Entry flow | `/` opens chat with a composer, examples and compact game selection. Playthroughs are optional. Reference pages retain their deep links under Explore tools. |
| Conversations | Browser-local, versioned history retains answer/game/source metadata independently of saved teams. New chat, history, copy, retry, stop and follow-ups are available. Existing playthroughs migrate to version 2 without dropping teams, milestones or plans. |
| Visitor credentials | The Gemini key lives in an unpersisted tab store and travels in `X-Rotom-Gemini-Key`. Chat, connection tests and research use request-scoped clients. Public endpoints do not inherit environment credentials. Non-local key-bearing HTTP requests are rejected. |
| Gemini continuation | Complete returned content parts, thought signatures and provider call IDs are retained. Provider errors are sanitized. Shared time/tool/research budgets and per-key/global concurrency limits bound work. |
| Answer validation | Runtime schemas validate tool arguments and final answers. The server projects bound record values into factual text and cards. A real citation attached to invented values does not validate them. Advice rationales and action labels cannot bypass this rule. Malformed answers are recoverable. |
| Version differences | Exact game mentions and switch follow-ups resolve server-side. Comparisons retrieve each game separately, with a three-game limit. TM01 uses the version-group move, removing conflicting generic effects. DLC access is checked against its base version. |
| Optional context | Known positive progress is honored without category-completeness checkboxes. Unknown progress stays unknown. Species–ability and species–move checks supplement context validation. Proposed actions have handlers and progress application is idempotent. |
| Research and knowledge | Game-scoped grounded research uses the visitor's key, preserves passage/source mapping and remains labelled unreviewed. Reviewed facts have applicability, source, review date and snapshot metadata. A ten-topic glossary, content auditing and immutable sidecar publication are available. |
| Story support | A bounded shortlist considers typing, shared weaknesses, favorites supplied to the tool, level, trading and recorded acquisition. It includes moves and acquisition records. |
| Competitive support | Pinned Pokémon Showdown 0.11.11 and `@smogon/calc` 0.11.0 run through a bounded internal Node adapter. Format lookup, validation, Showdown import/export and generation-aware damage calculation are available through APIs and the workshop. Chat requires an explicit matching format. |
| Evaluation | `rotom eval --live` now runs real provider/tool conversations and automated support/usefulness grading, with follow-up support. Deterministic evaluation remains separate. |

## Acceptance evidence

- 254 Python tests passed, including credential isolation, false-value rejection, malformed output, provider-part round trips, historical TM01, illegal combinations, known progress, DLC/base isolation and content publication/conflict gates.
- 70 frontend unit tests passed, including malformed nested-save rejection, save migration and separation of credentials from persisted conversations.
- 86 desktop/mobile browser tests passed, including light-theme accessibility and game selection without duplicate conversations. All 34 accessibility/responsive checks also passed after the final spacing adjustment.
- 128 deterministic evaluation cases passed. These exercise repositories/services, not live model quality.
- TypeScript/build, frontend lint and Ruff passed. Vite reports an advisory for the main bundle exceeding 500 kB before compression; route splitting remains an optimization opportunity.
- Content audit found no applicability errors or detected conflicts. All 50 audited main-series game identities remain explicitly **not deep-supported**.
- Manual preview checks covered chat in phone dark/light themes, illegal Ralts/Levitate/Surf rejection and a Generation III Swampert Earthquake damage result.
- Automated accessibility checks cover 12 screens at desktop and mobile sizes for serious/critical WCAG violations. Keyboard submission, multiline entry and status/error announcements have regression coverage. This is not full screen-reader or WCAG certification.
- The battle production dependency audit reported zero vulnerabilities after the pinned UUID override. The override is limited to a transitive dependency used by Showdown's unused server code.

## Still required by the approved plan

1. **All-game reviewed content.** The new prose sidecar contains four reviewed acquisition entries applicable to eleven games, not complete acquisition knowledge. Structured PokéAPI coverage is broader but uneven. Emerald and Red remain the only curated progression/boss packs. Field items, shops, tutors, gifts, transfer/events, bosses and postgame inventories still require reviewed batches for the other games. The content audit deliberately refuses to equate row counts with deep support.
2. **Question-suite and inventory sign-off.** Every applicable capability needs a reviewed inventory, positive/negative/unknown cases and conflict resolution. The audit currently exposes these as incomplete; a reviewer-signoff manifest and certification promotion workflow are still needed. See [content review](content-review.md).
3. **Live Gemini certification — deferred by the user.** No real key was supplied or used in this session. Model access, real thought-signature continuation, research usefulness, multi-turn entity resolution and real answer quality remain unverified. The configured initial model is `gemini-3.8-flash`; this is not an integration-test result.
4. **Deeper team strategy.** The initial story ranking does not fully optimize around upcoming opponents, training effort, favorite replacements or all progression constraints. Competitive legality and calculation work, but dated official-regulation review and format-specific strategy sources are not complete. Expanded saved training fields are available; full editing and transfer of every field between story profiles and the workshop still need work.
5. **Further product refinements.** Optional panels currently expand within the page; a dedicated mobile drawer interaction and more advanced clarifying/context suggestions remain to be built. The first factual record leads the answer; natural synthesis quality needs live evaluation. More manual screen-reader/focus checks are required.
6. **Deployment verification.** Docker now includes the Node adapter, but the local Docker daemon was not running, so the image was not built or exercised. HTTPS/proxy/header-redaction and multi-worker rate-limit coordination require deployment testing. No application was published.

## Reproduce checks

```sh
npm ci --prefix battle
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npm --prefix web run test
npm --prefix web run lint
npm --prefix web run build
npm --prefix web run e2e
.venv/bin/rotom eval --db data/build/rotom.sqlite3
.venv/bin/rotom content-audit --db data/build/rotom.sqlite3
```

Live evaluation is intentionally not part of this completed verification record. It requires explicit local CLI credentials and consumes their quota. Do not add those credentials to a save, command argument, report or committed file.
