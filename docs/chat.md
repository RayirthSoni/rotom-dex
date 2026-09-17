# Game-aware chat contract

`POST /api/v2/chat` and `/api/v2/chat/stream` accept version 2, a message, optional exact game, history, optional playthrough context, story/competitive mode, optional competitive format, research preference, spoiler level and DLC access. The stream emits `progress`, `answer`, `error`, and `done` events. The final answer keeps the ordinary envelope and adds resolved games, typed facts/cards/actions, references, follow-ups and usage metadata.

## Credentials

Use `X-Rotom-Gemini-Key`, never a body/query field. The browser's credential store is deliberately not persisted. `/api/chat/connect` tests the visitor's model access. Public dependency injection replaces any environment key with the request header, including for research. Clients are request-scoped. Key-bearing dataclasses suppress their key in representations, and provider HTTP response bodies are not exposed.

Production must terminate HTTPS, forward the trusted scheme, redact sensitive headers in proxies/APM, and disable request-body logging. No deployment is performed by this change. The API rejects key-bearing non-local HTTP requests; localhost HTTP is for development only. The separate CLI evaluator may read `ROTOM_GEMINI_API_KEY` when explicitly invoked.

Limits are per process: 20 requests/minute/client by default, two concurrent requests per key, twelve total model requests, four battle-adapter processes, bounded message/history/tool sizes and a shared deadline across a comparison. Cancellation stops subsequent work; an already-running upstream request may continue until its bounded timeout and may still use quota.

## Factual rendering

Tool JSON Schemas are enforced server-side. Raw Gemini content parts, thought signatures and tool call IDs survive continuation. The final JSON must match the answer schema before traversal. The model selects `fact_id` bindings; the server supplies the displayed values, game and sources. Citation existence alone cannot validate a claim. Numeric/stat/acquisition cards are projections of those selected records. Current generic effect wording and unverified generic prices are withheld from historical facts; machines use the exact version-group move mapping.

Gemini can finish through a typed `submit_answer` call after retrieving evidence. This avoids an unnecessary third generation for a simple lookup. Providers that return ordinary text still have a schema-constrained closing fallback. Both paths run the same factual and spoiler validation. The browser delivers the final answer event immediately and has an independent timeout for a stalled connection.

Connection tests allow 30 seconds. Temporary upstream HTTP 500/502/503/504 errors receive at most two retries with backoff inside the caller's original time budget. Invalid keys and quota errors are not automatically retried. HTTP 429 is a Google project quota/rate-limit condition; repeated retries cannot establish available quota. See [connection troubleshooting](troubleshooting-chat.md).

Reviewed knowledge passages use explicit game → version-group → generation → invariant applicability. Grounded search includes the resolved game in the query and preserves each supported passage's citation mapping. Research remains unreviewed and may contain errors; grounding metadata is not independent source verification. All displayed surfaces, including action labels and source metadata, pass the spoiler check. For games without a usable spoiler map, research under a restrictive preference is withheld.

Recommendations remain labelled advice and are not certified optimal. Reachability claims are capped by tool-derived verdicts. The initial story shortlist considers recorded catch levels, typing, shared weaknesses, favorites passed to the tool, and known access. It is not yet a full progression/boss/training optimizer.

Actions are inert proposals with typed validation and handlers. Applying a milestone adds it to a set; applying it again cannot uncomplete it. Historical actions use the answer's game. Existing team/progress saves remain independent of conversations.

## Evaluation

`rotom eval` checks domain-service expectations without a credential. `rotom eval --live` executes real v2 conversations and tools, supports `follow_ups` in case files, and performs automated usefulness/support grading against reviewed expectations. It exits nonzero for failures or missing live credentials. Model grading is fallible and does not replace human review.

Live Gemini/tool-loop/research behavior has **not been certified in this implementation session**. Deterministic provider scripts and request serialization tests establish application invariants, not model quality. Do not claim all-game deep support until the capability inventories, game-specific question suites and human review are complete.
