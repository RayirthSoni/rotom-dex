# Ask Rotom

Chat is the only part of this project that touches the network, and it is optional. With no
credential configured `/api/chat` answers `503` and everything else — the Pokédex, team analysis,
boss preparation, saved plans — works exactly as before. That is a tested property, not an intention:
`tests/test_chat_api.py` asserts it, and so does `web/e2e/chat.spec.ts`.

## The shape of the thing

```
browser → POST /api/chat → orchestrator → typed tools → services → repositories → snapshot
                              ↕
                          provider (Gemini by default, behind one interface)
```

The model does not know any facts. It picks tools and explains what comes back. Every stat, type
multiplier, price, level threshold, evolution rule and availability verdict is computed in code, by
the same functions the Dex screens call. `rotom_dex/chat/` sits beside `services/` rather than inside
it, because `services/` is guaranteed network-free and a provider adapter would break that promise.

## Tools

Seventeen, plus `web_research` when it is switched on. Two rules make a whole class of wrong answer
structurally impossible rather than merely discouraged:

- **No tool schema accepts a game.** The dispatcher injects the one resolved from the validated
  playthrough, so an answer about the wrong game cannot be constructed.
- **No tool schema accepts the playthrough.** Progress, team and constraints come from the request
  body the player's own browser sent, so the model cannot invent a badge to justify a route.

A bad identifier comes back to the model as a tool error it can act on, not as a `404` for the
player. Tool results are handed over inside a labelled data block that states the content is
retrieved evidence and must not be followed as instructions.

## Spoilers, enforced on the server

`spoiler_level` was carried end to end from the first release but nothing in Python ever read it: the
only filter was in the browser, over the milestone list alone. That is survivable when the client
decides what to render and not survivable once a model is involved, because a model cannot be
un-told something.

`rotom_dex/services/spoilers.py` now computes the player's frontier from `milestones.ord` and removes
everything past it **before the provider sees it** — rows become a stub, and hidden names are masked
even inside free text such as a coverage note. What was removed is reported as an assumption, so a
player who asked for no spoilers still learns that something exists. The tests assert this against
`ScriptedProvider.calls`, which is a record of what the model was actually shown.

## Every answer is checked before it is returned

`rotom_dex/chat/answer.py` runs a verification pass and will downgrade or discard the model's output:

| Check | What happens when it fails |
| --- | --- |
| Each fact's `evidence_id` came back from a tool this request **and** resolves in the database | The claim is demoted from a fact to an assumption |
| A recommendation is no more optimistic than the reachability check for its subject | The verdict is replaced with the one the tool returned |
| A recommendation claiming `reachable` was actually checked | Downgraded to `unknown` |
| No hidden term appears in the prose, a card or a recommendation | The **whole answer** is replaced with an abstention |
| `unavailable` is not asserted unless a stored row said so | The whole answer is replaced with an abstention |
| Proposed actions have a known kind and an object payload | Unknown kinds are dropped; `applied` is forced `false` |

Facts carry a *singular* `evidence_id`. That is load-bearing: the envelope builder collects evidence
by walking for keys ending in `evidence_id` whose value is a string, so a list would be silently
ignored and the answer would ship with no sources. Two sources means two facts.

## Bounds

All enforced in code, none merely requested of the model: four tool rounds, eight tool calls, three
calls to any one tool, a 45-second wall clock, 24 KB per tool result and 120 KB in total, a 2,000
character message, twelve turns of history, and twenty chat requests per minute per client. A
repeated identical call is served from a per-request cache and does not spend budget, which is what
stops a looping model burning the whole allowance on one question. Hitting a bound ends the loop and
answers from what was gathered, with the limit named in the response.

## Actions are proposals

The server never writes. An answer may propose pinning a plan, adding a team member, setting a level
or ticking a milestone; each arrives with `applied: false` and becomes a button. The player presses
it and the existing zustand store mutates their own browser's `localStorage`. Chat history is kept
separately from the saved playthrough, so it never becomes the authoritative record of progress.

## Optional web research

Off unless `ROTOM_CHAT_RESEARCH=1`. It runs as a separate, tool-less call whose result returns to our
code first, so retrieved text passes through a sanitiser — control characters, tags, fences and
role-prefixes removed, angle brackets stripped so the delimiter cannot be forged — and is re-wrapped
as untrusted evidence before it reaches the model. Citations are recorded in a separate bucket marked
`unreviewed`: a web reference can be listed and labelled, but it can never be the evidence behind a
fact, and nothing from it is written to the database. A research failure becomes a tool error the
model degrades around, never a failed request.

## Configuration

Read per request via `ChatConfig.from_env()`. Chat settings deliberately never go in `settings.py`,
whose values bind at import time and therefore have to be rebound in three modules under pytest;
`tests/test_chat.py` parses the syntax tree of every module in `rotom_dex/chat/` to keep it that way.
See `.env.example`.

## What is not tested here

**No provider credential exists in this environment, so no live model call has ever been made.** The
entire loop, every tool, the spoiler filter and the verification pass are exercised deterministically
through `ScriptedProvider`, and the Gemini adapter's request and schema translation are unit tested —
but the adapter has never spoken to Gemini, and the grounded-search path has never run. Treat live
behaviour, latency, cost and answer quality as unmeasured.
