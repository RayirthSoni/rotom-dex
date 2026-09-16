# Emerald source and coverage report

Reviewed 2026-09-17. This is a data feasibility sample, not a complete playthrough guide.

## Source assessment and reuse

| Candidate | Assessment | Decision |
| --- | --- | --- |
| [PokéAPI REST API](https://pokeapi.co/docs/v2) | Structured Pokémon, version-group learnsets, exact-version encounters, evolution and historical fields. Its fair-use policy requests local caching. Endpoint existence does not establish complete acquisition or progression coverage. | Suitable source family; use its pinned CSV repository to avoid many live calls and preserve historical correction tables. |
| [PokéAPI CSV repository](https://github.com/PokeAPI/pokeapi/tree/39bc03a43df25a1898f5aa03cbc2a0abbeea30e8/data/v2/csv) | Inspected actual Emerald rows and historical tables before selecting. Supports reproducible snapshots, machine-to-item relationships, and exact-version held items. | Selected; 35 unmodified compressed CSVs plus hashes and retrieval metadata retained. |
| [veekun/pokedex](https://github.com/veekun/pokedex) | An alternative structured Pokédex and schema; its [MIT license](https://github.com/veekun/pokedex/blob/master/LICENSE) permits reuse with notice. A second related data source would not by itself independently verify these facts. | Not imported; PokéAPI has the historical tables needed for this sample. |
| [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) | Structured simulator data under an [MIT license](https://github.com/smogon/pokemon-showdown/blob/master/LICENSE). Relevant to historical battle mechanics; competitive legality is not story acquisition. | Deferred; not used as an encounter/walkthrough source. |
| [pret/pokeemerald](https://github.com/pret/pokeemerald) | Game-specific decompilation, potentially useful for independent mechanics and progression review. No blanket reuse permission for game content was established in this assessment. | No code, scripts, assets, or data copied. Possible later verification source after a targeted review. |
| Pokémon Database and walkthrough websites | No scraping or reuse clearance established. | Existing `pokemondb.py` stays unused. No website scraping. |

The selected repository's [BSD-style license](https://github.com/PokeAPI/pokeapi/blob/39bc03a43df25a1898f5aa03cbc2a0abbeea30e8/LICENSE.md) permits redistribution subject to retaining its copyright, conditions, disclaimer, and non-endorsement requirement. The full notice is retained in [the cached source directory](../data/sources/pokeapi/LICENSE.md). The notice identifies Pokémon names as Nintendo trademarks. This import includes no artwork or ROM assets. Repository licensing is not presented as ownership of Pokémon IP.

The source URLs are immutable commit URLs. [The manifest](../data/sources/pokeapi/manifest.json) records SHA-256 hashes of the **decompressed original bytes** and initial UTC retrieval times. Runtime evidence additionally records row selectors and normalization policy. No independent ROM or second-source verification is claimed.

## Implemented coverage

| Area | Imported records | Coverage/limitations |
| --- | ---: | --- |
| Species/default forms | 10 / 10 | Four complete Emerald evolution lines: Treecko, Ralts, Zigzagoon and Shroomish. All other species/forms outside sample. |
| Game data | 10 | Emerald exact-game mapping. Ruby is an unsupported catalog entry only. |
| Types / stats / ability slots | 11 / 60 / 13 | Historical resolution applied; 5 distinct abilities. Effects of abilities not imported. |
| Moves / learnset rows | 127 / 562 | All Emerald-version-group rows for selected forms, including level-up, machine, tutor and egg methods. Historical type/category/power/accuracy/PP imported; effect descriptions absent. |
| Evolution | 6 | Reviewed default level-up rules explicitly mapped to Emerald. No later Gallade or regional Linoone rules. |
| Pokémon acquisitions | 28 | 21 walking encounter slots, 1 Treecko gift, 6 derived evolution routes; 6 source location areas. These are not 28 distinct places. |
| Items / Emerald descriptions | 53 / 53 | Related machines, Poké Ball, Potion, Oran Berry and Sitrus Berry. In-game effect descriptions only. |
| Item acquisitions | 21 | Derived wild-held-berry routes from Emerald Zigzagoon/Linoone encounters and held-item rates. No shops, field pickups or gift locations. |
| Natures | 25 | Game-scoped stat modifiers, including 5 neutral natures. |
| Type effectiveness | 289 | All 17×17 Gen III pairs; neutral pairs and immunities included. |
| Coverage records | 183 | Per-form, per-item and game-wide status and gap notes. |

Raw source files include other Pokémon/games for provenance and rebuilds. That does not expand the supported query coverage. Query results distinguish game obtainability from reachability now: all ten forms have a sourced route or evolution ancestry, but every acquisition route retains unknown player availability.

## Normalization decisions

- Exact versions are never inferred from a generation alone. Encounters and held items filter `version_id=9`; learnsets, machines and item descriptions filter `version_group_id=6` (Emerald).
- For types, the nearest historical endpoint at or after generation 3 replaces the whole type set. For stats and abilities it replaces the relevant stat/slot. Empty historical ability IDs remove later slots. Ralts stays pure Psychic, Zigzagoon keeps only Pickup, and Breloom keeps only Effect Spore.
- Move changes are undone newest-to-oldest after the source's Emerald version-group ordering. Damaging moves use Gen III type-based physical/special categories. Regression examples include Tackle at 35 power/95 accuracy, Leaf Blade at 70 power and special, Giga Drain at 60 power/5 PP, and Sitrus Berry restoring 30 HP.
- Six default, simple level-up evolution rules are explicitly reviewed in [the Emerald pack](../data/game-packs/emerald/pack.json). Unsupported fields cause failure rather than being discarded. Cross-generation evolution data is not blindly imported.
- Acquisition prerequisites separate what the source records (location/method/encounter conditions) from what is unreviewed (progression, starter selection, equipment and other restrictions). A gift at Route 101 does not imply an unlimited/repeatable starter.
- Missing values and coverage gaps stay visible. No sample record asserts confirmed unavailability. The schema supports an explicit unavailable state with evidence; tests use synthetic unavailable records to verify it stays distinct from unknown.
- Repeated identical rows are allowed; divergent facts or snapshot manifests fail without overwriting published facts. A transaction commits only after relationship, required-record and integrity checks pass.

## Gaps and next review work

1. No reachability graph or playthrough milestones; cannot answer “available before Roxanne” safely. Boss rosters/preparation are outside this request.
2. Acquisition coverage is partial even where encounters exist. Breeding, trades, event restrictions and complete alternative routes remain unreviewed. No encounters is not evidence of no acquisition route.
3. Machine/tutor eligibility does not establish access. Tutor locations/costs, TM/HM locations, shops and ground items remain missing. Held-item percentages are conditional on the species, not overall encounter probabilities.
4. Item descriptions are short game text, not exhaustive effects. Move and ability effect models remain missing, as do special interactions and a battle simulator.
5. Only ten default forms and simple level-up evolution conditions are included. More forms, special evolution mechanics, and other exact games require additional reviewed packs and regression cases.
6. Source-derived records have not been independently checked against the game. A full product release needs stronger source review and broader coverage; these tests validate normalization and data integrity, not every upstream fact.

## Verification

`python3 -m unittest discover -s tests -v` covers repeat imports and fresh rebuild equivalence; adversarial Ruby/Emerald filtering; foreign keys and invalid relationships; historical types, abilities, stats, moves and effectiveness; evolution/encounter records; machine/item links; NULL/gap behavior; evidence resolution; corrupted caches; conflict rollback; source snapshot changes; CLI behavior; and three-valued conditions.

`python3 -m src.cli check` runs SQLite integrity/foreign-key checks and verifies required stat/type/ability/learnset records, the type chart, nature count, source relationships and condition expressions. `coverage` emits the database's inspectable gap report as JSON.
