# Record-level validation: Emerald and Red

Performed 2026-09-17 against snapshot databases built from the pinned source. Each record was checked
three ways: the raw CSV rows behind its evidence, the normalized database row, and a reference page read on
the access date (Bulbapedia, CC BY-NC-SA 2.5; read for verification only, nothing copied). Disagreements
are listed at the end and, where they concern the data, recorded as `data_issues`.

## Emerald (Generation III, version group `emerald`, version id 9)

| Record | Database | Reference | Result |
| --- | --- | --- | --- |
| Ralts typing | `psychic` only in generation 3; `psychic, fairy` from generation 6 | Ralts page: pure Psychic before Generation VI | agree |
| Ralts base stats | 28/25/25/45/35/40 | Ralts page | agree |
| Ralts Route 102 encounter | `walk`, level 4, slot 4 %, area `hoenn-route-102` | Ralts page lists Route 102 in R/S/E (rate not on page) | agree; rate source-only |
| Ralts → Kirlia → Gardevoir | level 20, level 30, both `applies`; Kirlia → Gallade (Dawn Stone, male) `not-applicable` in Emerald, `applies` in Platinum and X | Ralts page: Gallade introduced in Generation IV | agree |
| Treecko/Torchic/Mudkip | source `gift` encounters at level 5 on Route 101 plus pack routes with an explicit "only one starter" unknown leaf | Walkthrough section 1 | agree |
| Tackle | power 35, accuracy 95, physical | previously regression-tested; Bulbapedia Tackle history | agree |
| Leaf Blade | power 70, PP 15, damage class `special` (Grass is special before Generation IV); learned by Grovyle and Sceptile at level 29 | Leaf Blade page: 70 power in Generation III, 90 from IV; level 29 learners | agree on numbers and levels (see note 1 on category) |
| Bite | Dark, `special` in Emerald; Normal, `physical` in Red; `physical` in Platinum | Bite page: Normal in Generation I; special in II–III; physical from IV | agree |
| Sitrus Berry text | "A hold item that restores 30 HP in battle." for version group `emerald`; Platinum text no longer says 30 HP | Sitrus Berry page: 30 HP in Generation III, 25 % from IV | agree |
| Type chart | 289 pairs; Ghost→Steel 50, Dark→Steel 50, Ghost→Psychic 200; no Fairy | Generation III chart | agree |
| Machines | 50 TMs + 8 HMs linked to items and moves; TM39 = Rock Tomb | Roxanne page (TM39 Rock Tomb) | agree |
| Roxanne (curated) | Geodude ♀ L12 ×2 (Rock Head; Tackle, Defense Curl, Rock Throw, Rock Tomb), Nosepass ♀ L15 (Sturdy, Oran Berry; Block, Harden, Tackle, Rock Tomb); Stone Badge; TM39; $1500 | Roxanne page, Emerald section | agree; stored `reference-reviewed` |
| Rustboro Poké Mart (curated) | 10 always-available items with prices, Timer/Repeat Ball behind an unknown prerequisite | Rustboro City page | agree |
| Held items | Zigzagoon/Linoone Oran Berry 50 %, Sitrus Berry 5 % per encounter | source `pokemon_items` version 9 | source-only |
| Breeding | derived routes for base species, e.g. `breeding:9:280` requires any of Ralts/Kirlia/Gardevoir and an unknown leaf | mechanics pack: breeding present in Generation III | consistent |

## Red (Generation I, version group `red-blue`, version id 1)

| Record | Database | Reference | Result |
| --- | --- | --- | --- |
| Type count and chart | 15 types, 225 pairs; Ghost→Psychic 0; Bug→Poison 200; Poison→Bug 200; Ice→Fire 100 | Generation I chart (source `type_efficacy_past`) | agree |
| Bulbasaur stats | HP 45, Atk 49, Def 49, Special 65, Speed 45; no `special-attack`/`special-defense` rows | Bulbasaur page, Generation I stats | agree |
| Bulbasaur abilities / natures / held items | none; mechanics flags `abilities=0`, `natures=0`, `held_items=0` | Ability, Nature and Held item pages: introduced in Generations III, III and II | agree |
| Bite / Gust | Normal-type in version group 1 | Bite page | agree (Gust source-only) |
| Machines | 50 TMs + 5 HMs; `tm_reusable=0` | TM page: single-use through Generation IV | agree |
| Eevee | `gift`, level 25, area in `celadon-city` | Eevee page: received in Celadon Mansion | agree (level source-only) |
| Mewtwo | `static`, level 70, `cerulean-cave` | Mewtwo page: Cerulean Cave, only one | agree (level source-only) |
| In-game trades | 9 `npc-trade` routes (Jynx, Farfetch'd, Nidorina, Lickitung, Mr. Mime, Electrode, Tangela, Seel, Nidoran♀) | source only | source-only |
| Red vs Blue | 550 walking slots each, 59 (form, area) pairs differ; learnsets shared through version group 1 | version exclusives are expected | consistent |
| Breeding / held items | no rows; coverage "not applicable" | mechanics pack | consistent |

## Cross-game checks

- Steel loses its Ghost/Dark resistances in generation 6 (100 vs 50 in generation 3); Fairy exists only
  from generation 6 and Fairy→Dragon is 200.
- Hidden abilities: none in generations 3–4, 656 slots in generation 6.
- Ruby and Emerald share nothing at the exact-version level: 108 (form, area, method) encounter tuples
  differ; learnset counts differ between version groups 5 and 6.
- Scarlet has no source encounters: coverage `encounters=missing`, `data_issues` row
  `source:scarlet:encounters`, and the acquisition endpoint lists only derived evolution/breeding routes,
  all `unknown`, never `unavailable`. No imported row anywhere is `unavailable`.

## Notes and disagreements

1. **Leaf Blade category.** The extracted summary of the Leaf Blade page called the Generation III category
   "physical". The generation-scoped rule (Grass is special before the Generation IV split, per the Damage
   category article) is used instead; the database stores `special`. Treated as an extraction artifact, not a
   data dispute.
2. **Sitrus Berry price.** The database shows `purchase_price 80, provenance default-cost` (the source's
   generic cost); the reference says it cannot be bought and sells for $10. Provenance already marks the
   value as unverified for the game; a per-version-group price would come from `item_prices`, which has no
   Generation III row for it.
3. **Roseli Berry** appears twice in the source with the same identifier; the second is stored as
   `roseli-berry-2279` and recorded as a `disputed` data issue.
4. Nine Legends: Z-A mega forms have stats but no ability slots in the source; recorded as `missing`
   data issues rather than invented.

## How to repeat

```sh
uv run rotom import --db data/build/rotom.sqlite3 --games emerald,red
uv run rotom query ralts --game emerald --level 10 --db data/build/rotom.sqlite3
uv run rotom query bulbasaur --game red --db data/build/rotom.sqlite3
uv run pytest -q          # the same facts are asserted in tests/test_history.py and friends
```
