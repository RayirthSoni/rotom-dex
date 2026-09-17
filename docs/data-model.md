# Data model

Schema: [`rotom_dex/db/migrations/0001_initial.sql`](../rotom_dex/db/migrations/0001_initial.sql).
Migrations are numbered SQL files applied once and recorded in `schema_migrations`. Databases built
by the earlier Emerald-only sample (`schema_version` table) are rejected and must be rebuilt.

## Scope: generation, version group, exact game

PokéAPI distinguishes three levels and so does this schema. Each fact is stored once at the level where it
actually varies; queries resolve `game_version → version_group → generation`.

| Level | Tables | Why |
| --- | --- | --- |
| generation | `types`, `type_effectiveness`, `pokemon_types`, `pokemon_stats`, `pokemon_abilities`, `ability_type_effects` | The source records changes to typings, base stats, ability slots and the type chart per generation. |
| version group | `pokemon_version_groups` (presence), `move_game_data`, `move_flavor_text`, `learnsets`, `machines`, `item_game_data`, `ability_flavor_text`, `evolution_applicability`, `game_mechanics`, `tutors` | Learnsets, machines, move values and item text are shared by paired games (Ruby/Sapphire) and differ between groups (Emerald). |
| exact game | `acquisitions`, `encounter_rates`, `pokemon_held_items`, `milestones`, `trainer_battles`, `shops`, `coverage`, `data_issues` | Encounters and held items differ between paired versions; progression and coverage are per game. |

`game_versions.support_tier` comes from [`data/games/registry.json`](../data/games/registry.json):
`validated` (record-level validation done: Emerald, Red), `imported` (full structured import),
`catalog` (identity only: Japanese Red/Green/Blue), `excluded` (Colosseum, XD, Champions). Expansion
pseudo-versions (Isle of Armor, Teal Mask, …) inherit version-group data from their base game as declared
in the registry's `inherits` map and are marked partial.

## Mechanics flags

`game_mechanics(version_group_id, key, value)` records whether a mechanic exists in a version group:
`abilities`, `hidden_abilities`, `natures`, `held_items`, `breeding`, `physical_special_split`,
`special_stat_single`, `tm_present`, `tm_reusable`, `hm_present`, `tr_present`, `fairy_type`. Values come
from [`data/mechanics/version_groups.json`](../data/mechanics/version_groups.json), each with a reference URL
and a verification status; a missing key means "unknown" and the API says so instead of guessing.
Validation uses these flags (Generation I forms have five stats and no abilities; hidden abilities only from
Generation V; no Fairy before Generation VI; 15×15 / 17×17 / 18×18 charts).

## Pokémon

- `species` (national number = id), `pokemon_forms` (PokéAPI *pokemon* rows: every form with its own battle
  data, e.g. Deoxys Attack Forme), `form_variants` (PokéAPI *pokemon_forms* rows: cosmetic/mega/battle-only
  identities with the version group that introduced them).
- `pokemon_version_groups.presence`: `present` when the form appears in the group's learnsets, in an
  encounter of one of its versions, or (through Generation VII) in the source's per-version game index;
  `unknown` for variant forms of a present species introduced by that group. Presence means "in the game's
  data", not "obtainable".
- Per-generation `pokemon_types`, `pokemon_stats` (`special` replaces the two special stats in
  Generation I), `pokemon_abilities` (`is_hidden` lives on the relationship).
- `pokemon_egg_groups`, `pokemon_dex_numbers` + `pokedexes` + `pokedex_version_groups`.

## Moves and learnsets

- `move_game_data` per version group: the current row rewound through `move_changelog` entries made after
  that group (type, power, PP, accuracy, priority, target, effect, effect chance). Damage class follows the
  type before Generation IV and the move afterwards. `power`/`accuracy` `NULL` mean "no fixed power" /
  "no accuracy check" (the source uses empty or 0).
- `move_effects` (current wording, flagged `wording='current'`), `move_flavor_text` (per version group,
  Generation III onward), `move_meta`, `move_flags`.
- `learnsets(form_id, version_group_id, move_id, method, level, ord)`: level 0 for non-level-up methods and
  for "learned on evolution" rows; composite foreign keys ensure the form is present and the move has
  values in that group.
- `machines(version_group_id, kind, machine_number, item_id, move_id)` with `kind` in `tm|hm|tr`; reuse
  rules come from `game_mechanics`. `tutors` holds curated tutor locations/costs (none from the source).

## Evolution

`evolution_rules` translate every populated PokéAPI column into typed conditions
(`rotom_dex/domain/conditions.py`): level, item, held item, gender, time of day, known move/type,
happiness/beauty/affection thresholds, stat relation, party members, trade partner, rain, upside-down device,
location and region. Mechanics the vocabulary does not model (personality value, nature, steps, damage
taken, move-use counts, random outcomes, exotic triggers) become `unknown` leaves with a reason, never
silent drops. `raw` keeps the original non-empty fields.

`evolution_applicability(rule_id, version_group_id, status, reason)` is derived per group: both forms
present, rule not introduced later, location/region compatible, required item indexed in that generation
→ `applies`; otherwise `not-applicable` or `unknown`. Derived rows are `unverified`; game packs can override
with `reference-reviewed` rows.

## Acquisition

`acquisitions(id, game_id, form_id | item_id, location_id, location_area_id, method, levels, chance_percent,
availability, prerequisites, encounter_conditions, verification_status, note)`:

- `encounter:<game>:<id>` from source encounters (walk, surf, rods, `gift`, `gift-egg`, `npc-trade`,
  `static`, …) with `prerequisites = at_location AND unknown(progression not reviewed)` and the source's
  encounter conditions (time, season, swarm, …) as typed leaves;
- `evolution:<game>:<rule>` for rules that apply in that game (`has_pokemon(pre-evolution) AND rule`);
- `breeding:<game>:<form>` for base species in games with breeding (`has_pokemon(any family member) [AND
  held_item(incense)] AND unknown(daycare/partner)`);
- `pack:<game>:<id>` from curated packs (starters, TM gifts, in-game trades, field items).

`availability` is one of `reachable | locked | unavailable | unknown`; every imported row is `unknown`
because reachability needs progression data. Nothing in the pipeline writes `unavailable`; that state is
reserved for reviewed evidence. `pokemon_held_items` (per exact game) and `encounter_rates` complete the
picture. Slot percentages are per method and area and must not be summed.

## Items, natures, progression, coverage

- `items` (+ `item_generations` presence, `item_game_data` per version group with flavor text and
  `purchase_price`/`sell_price` plus `price_provenance` ∈ `version-group | default-cost | unknown`,
  `item_effects` current wording, `item_attributes` such as `holdable`/`consumable`), curated `shops` and
  `shop_items`.
- `natures` is global; the API exposes it only where `game_mechanics.natures = 1`.
- `ability_type_effects(ability_id, generation_id, applies_to, type_id, damage_factor)` holds reviewed,
  arithmetic ability modifiers from [`data/mechanics/ability_type_effects.json`](../data/mechanics/ability_type_effects.json):
  a factor against one attacking type, or against super-effective / non-super-effective moves as a
  class. Separate from `ability_effects`, which is the source's prose. Scoped per generation because
  the modifier's first generation is not always the ability's: Lightning Rod and Storm Drain only
  redirected moves before Generation V. Abilities whose effect depends on a move flag, the weather,
  the field or remaining HP are listed under `excluded` in that file and become `data_issues`, so the
  omission is explicit rather than silent.
- Curated `milestones`, `trainer_battles`, `trainer_party` (level, gender, ability, held item, moves).
- `coverage(game_id, feature, subject, status, note)` with `status ∈ complete | partial | missing |
  disputed`, computed after import from actual row counts and mechanics; `data_issues` lists explicit
  gaps, disputes and unverified facts (from packs and from source analysis).

## Conditions

Conditions are JSON objects validated on write and read. Combinators `and`/`or`; leaves listed in
`rotom_dex/domain/conditions.py`; `unknown` carries a reason. Evaluation is three-valued: absent context
yields `None` (unknown), never `False`, so an unreviewed prerequisite can never make a route look reachable.
