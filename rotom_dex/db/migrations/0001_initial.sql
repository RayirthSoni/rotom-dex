-- Rotom Dex schema. Facts are scoped at their natural granularity:
--   generation      : types, type chart, base stats, typings, ability slots
--   version group   : moves, learnsets, machines, item data, flavor text, presence, evolution applicability
--   exact version   : encounters, held items, acquisitions, progression, coverage
-- Queries resolve game_version -> version_group -> generation. Every fact row carries evidence.

CREATE TABLE snapshots (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
  packs_sha256 TEXT NOT NULL, normalizer TEXT NOT NULL
);
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('dataset','game-pack','reference','code')),
  url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  sha256 TEXT CHECK(sha256 IS NULL OR length(sha256)=64),
  license TEXT NOT NULL, local_path TEXT, review_status TEXT NOT NULL,
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  CHECK(kind='reference' OR sha256 IS NOT NULL)
);
CREATE TABLE evidence (id TEXT PRIMARY KEY);
CREATE TABLE evidence_members (
  evidence_id TEXT NOT NULL REFERENCES evidence(id), source_id TEXT NOT NULL REFERENCES sources(id),
  selector TEXT NOT NULL, PRIMARY KEY(evidence_id, source_id, selector)
);

-- Scope -----------------------------------------------------------------------
CREATE TABLE generations (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE version_groups (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  generation_id INTEGER NOT NULL REFERENCES generations(id), ord INTEGER NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE game_versions (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  is_main_series INTEGER NOT NULL CHECK(is_main_series IN (0,1)),
  support_tier TEXT NOT NULL CHECK(support_tier IN ('validated','imported','catalog','excluded')),
  note TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE regions (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE version_group_regions (
  version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  region_id INTEGER NOT NULL REFERENCES regions(id), PRIMARY KEY(version_group_id, region_id)
);
CREATE TABLE game_mechanics (
  version_group_id INTEGER NOT NULL REFERENCES version_groups(id), key TEXT NOT NULL,
  value INTEGER NOT NULL, note TEXT NOT NULL, verification_status TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(version_group_id, key)
);

-- Types -----------------------------------------------------------------------
CREATE TABLE types (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  generation_id INTEGER NOT NULL REFERENCES generations(id), evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE type_effectiveness (
  generation_id INTEGER NOT NULL REFERENCES generations(id),
  attack_type_id INTEGER NOT NULL REFERENCES types(id), defense_type_id INTEGER NOT NULL REFERENCES types(id),
  damage_factor INTEGER NOT NULL CHECK(damage_factor IN (0,50,100,200)),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(generation_id, attack_type_id, defense_type_id)
);

-- Pokémon ---------------------------------------------------------------------
CREATE TABLE species (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  generation_id INTEGER NOT NULL REFERENCES generations(id),
  evolves_from_species_id INTEGER REFERENCES species(id), evolution_chain_id INTEGER,
  gender_rate INTEGER, capture_rate INTEGER, base_happiness INTEGER, hatch_counter INTEGER,
  growth_rate TEXT, is_baby INTEGER NOT NULL CHECK(is_baby IN (0,1)),
  is_legendary INTEGER NOT NULL CHECK(is_legendary IN (0,1)), is_mythical INTEGER NOT NULL CHECK(is_mythical IN (0,1)),
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE pokemon_forms (
  id INTEGER PRIMARY KEY, species_id INTEGER NOT NULL REFERENCES species(id), slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL, is_default INTEGER NOT NULL CHECK(is_default IN (0,1)),
  height_dm INTEGER CHECK(height_dm IS NULL OR height_dm>=0), weight_hg INTEGER CHECK(weight_hg IS NULL OR weight_hg>=0),
  base_experience INTEGER, ord INTEGER, evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE form_variants (
  id INTEGER PRIMARY KEY, form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), slug TEXT NOT NULL UNIQUE,
  form_name TEXT NOT NULL, is_default INTEGER NOT NULL CHECK(is_default IN (0,1)),
  is_mega INTEGER NOT NULL CHECK(is_mega IN (0,1)), is_battle_only INTEGER NOT NULL CHECK(is_battle_only IN (0,1)),
  introduced_in_version_group_id INTEGER REFERENCES version_groups(id),
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE pokemon_egg_groups (
  species_id INTEGER NOT NULL REFERENCES species(id), egg_group TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(species_id, egg_group)
);
CREATE TABLE pokedexes (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, region_id INTEGER REFERENCES regions(id),
  is_main_series INTEGER NOT NULL CHECK(is_main_series IN (0,1)), evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE pokedex_version_groups (
  pokedex_id INTEGER NOT NULL REFERENCES pokedexes(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  PRIMARY KEY(pokedex_id, version_group_id)
);
CREATE TABLE pokemon_dex_numbers (
  species_id INTEGER NOT NULL REFERENCES species(id), pokedex_id INTEGER NOT NULL REFERENCES pokedexes(id),
  number INTEGER NOT NULL CHECK(number>=0), evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(species_id, pokedex_id)
);
CREATE TABLE pokemon_types (
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), generation_id INTEGER NOT NULL REFERENCES generations(id),
  slot INTEGER NOT NULL CHECK(slot IN (1,2)), type_id INTEGER NOT NULL REFERENCES types(id),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id, generation_id, slot),
  UNIQUE(form_id, generation_id, type_id)
);
CREATE TABLE pokemon_stats (
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), generation_id INTEGER NOT NULL REFERENCES generations(id),
  stat TEXT NOT NULL CHECK(stat IN ('hp','attack','defense','special-attack','special-defense','speed','special')),
  base_stat INTEGER NOT NULL CHECK(base_stat BETWEEN 1 AND 255), effort INTEGER NOT NULL CHECK(effort BETWEEN 0 AND 3),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id, generation_id, stat)
);
CREATE TABLE abilities (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  generation_id INTEGER NOT NULL REFERENCES generations(id), is_main_series INTEGER NOT NULL CHECK(is_main_series IN (0,1)),
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE pokemon_abilities (
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), generation_id INTEGER NOT NULL REFERENCES generations(id),
  slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3), ability_id INTEGER NOT NULL REFERENCES abilities(id),
  is_hidden INTEGER NOT NULL CHECK(is_hidden IN (0,1)), evidence_id TEXT NOT NULL REFERENCES evidence(id),
  PRIMARY KEY(form_id, generation_id, slot)
);
CREATE TABLE pokemon_version_groups (
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  presence TEXT NOT NULL CHECK(presence IN ('present','unknown')), evidence_id TEXT NOT NULL REFERENCES evidence(id),
  PRIMARY KEY(form_id, version_group_id)
);
CREATE TABLE ability_effects (
  ability_id INTEGER PRIMARY KEY REFERENCES abilities(id), short_effect TEXT NOT NULL, effect TEXT NOT NULL,
  wording TEXT NOT NULL CHECK(wording IN ('current')), evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE ability_flavor_text (
  ability_id INTEGER NOT NULL REFERENCES abilities(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  text TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(ability_id, version_group_id)
);
CREATE TABLE ability_changes (
  ability_id INTEGER NOT NULL REFERENCES abilities(id), changed_in_version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  effect TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(ability_id, changed_in_version_group_id)
);

-- Moves -----------------------------------------------------------------------
CREATE TABLE moves (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  generation_id INTEGER NOT NULL REFERENCES generations(id), evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE move_effects (
  id INTEGER PRIMARY KEY, short_effect TEXT NOT NULL, effect TEXT NOT NULL,
  wording TEXT NOT NULL CHECK(wording IN ('current')), evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE move_game_data (
  move_id INTEGER NOT NULL REFERENCES moves(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  type_id INTEGER NOT NULL REFERENCES types(id),
  damage_class TEXT NOT NULL CHECK(damage_class IN ('physical','special','status')),
  power INTEGER CHECK(power IS NULL OR power>=0), accuracy INTEGER CHECK(accuracy IS NULL OR accuracy BETWEEN 1 AND 100),
  pp INTEGER CHECK(pp IS NULL OR pp>0), priority INTEGER NOT NULL, target TEXT NOT NULL,
  effect_id INTEGER REFERENCES move_effects(id), effect_chance INTEGER,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(move_id, version_group_id)
);
CREATE TABLE move_flavor_text (
  move_id INTEGER NOT NULL REFERENCES moves(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  text TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(move_id, version_group_id)
);
CREATE TABLE move_meta (
  move_id INTEGER PRIMARY KEY REFERENCES moves(id), category TEXT NOT NULL, ailment TEXT NOT NULL,
  min_hits INTEGER, max_hits INTEGER, min_turns INTEGER, max_turns INTEGER, drain INTEGER NOT NULL,
  healing INTEGER NOT NULL, crit_rate INTEGER NOT NULL, ailment_chance INTEGER NOT NULL,
  flinch_chance INTEGER NOT NULL, stat_chance INTEGER NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE move_flags (
  move_id INTEGER NOT NULL REFERENCES moves(id), flag TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(move_id, flag)
);

-- Learnsets and machines --------------------------------------------------------
CREATE TABLE learnsets (
  form_id INTEGER NOT NULL, version_group_id INTEGER NOT NULL, move_id INTEGER NOT NULL,
  method TEXT NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 100), ord INTEGER,
  evidence_id TEXT NOT NULL REFERENCES evidence(id),
  PRIMARY KEY(form_id, version_group_id, move_id, method, level),
  FOREIGN KEY(form_id, version_group_id) REFERENCES pokemon_version_groups(form_id, version_group_id),
  FOREIGN KEY(move_id, version_group_id) REFERENCES move_game_data(move_id, version_group_id),
  CHECK(method='level-up' OR level=0)
);
CREATE INDEX learnsets_by_move ON learnsets(version_group_id, move_id);
CREATE TABLE items (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL, pocket TEXT NOT NULL,
  default_cost INTEGER CHECK(default_cost IS NULL OR default_cost>=0), fling_power INTEGER,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE machines (
  version_group_id INTEGER NOT NULL REFERENCES version_groups(id), machine_number INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('tm','hm','tr')), item_id INTEGER NOT NULL REFERENCES items(id),
  move_id INTEGER NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id),
  PRIMARY KEY(version_group_id, kind, machine_number), UNIQUE(version_group_id, item_id),
  FOREIGN KEY(move_id, version_group_id) REFERENCES move_game_data(move_id, version_group_id)
);
CREATE TABLE tutors (
  id TEXT PRIMARY KEY, version_group_id INTEGER NOT NULL REFERENCES version_groups(id), move_id INTEGER NOT NULL,
  location_id INTEGER, cost_item_id INTEGER REFERENCES items(id), cost_amount INTEGER,
  prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)), verification_status TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id),
  FOREIGN KEY(move_id, version_group_id) REFERENCES move_game_data(move_id, version_group_id)
);

-- Evolution -------------------------------------------------------------------
CREATE TABLE evolution_rules (
  id INTEGER PRIMARY KEY, from_form_id INTEGER NOT NULL REFERENCES pokemon_forms(id),
  to_form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), trigger TEXT NOT NULL,
  introduced_version_group_id INTEGER REFERENCES version_groups(id),
  conditions TEXT NOT NULL CHECK(json_valid(conditions)), raw TEXT NOT NULL CHECK(json_valid(raw)),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), CHECK(from_form_id!=to_form_id)
);
CREATE INDEX evolution_rules_from ON evolution_rules(from_form_id);
CREATE INDEX evolution_rules_to ON evolution_rules(to_form_id);
CREATE TABLE evolution_applicability (
  rule_id INTEGER NOT NULL REFERENCES evolution_rules(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  status TEXT NOT NULL CHECK(status IN ('applies','not-applicable','unknown')), reason TEXT NOT NULL,
  verification_status TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(rule_id, version_group_id)
);

-- Locations and acquisition -----------------------------------------------------
CREATE TABLE locations (
  id INTEGER PRIMARY KEY, region_id INTEGER REFERENCES regions(id), slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE location_areas (
  id INTEGER PRIMARY KEY, location_id INTEGER NOT NULL REFERENCES locations(id), slug TEXT NOT NULL, name TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE encounter_rates (
  location_area_id INTEGER NOT NULL REFERENCES location_areas(id), method TEXT NOT NULL,
  game_id INTEGER NOT NULL REFERENCES game_versions(id), rate INTEGER NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(location_area_id, method, game_id)
);
CREATE TABLE acquisitions (
  id TEXT PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES game_versions(id),
  form_id INTEGER REFERENCES pokemon_forms(id), item_id INTEGER REFERENCES items(id),
  location_id INTEGER REFERENCES locations(id), location_area_id INTEGER REFERENCES location_areas(id),
  method TEXT NOT NULL, min_level INTEGER CHECK(min_level IS NULL OR min_level BETWEEN 1 AND 100),
  max_level INTEGER CHECK(max_level IS NULL OR max_level BETWEEN 1 AND 100),
  chance_percent INTEGER CHECK(chance_percent IS NULL OR chance_percent BETWEEN 0 AND 100),
  availability TEXT NOT NULL CHECK(availability IN ('reachable','locked','unavailable','unknown')),
  prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)),
  encounter_conditions TEXT NOT NULL CHECK(json_valid(encounter_conditions)),
  verification_status TEXT NOT NULL, note TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id),
  CHECK((form_id IS NULL)!=(item_id IS NULL)), CHECK(min_level IS NULL OR max_level IS NULL OR max_level>=min_level)
);
CREATE INDEX acquisitions_by_form ON acquisitions(game_id, form_id);
CREATE INDEX acquisitions_by_item ON acquisitions(game_id, item_id);
CREATE INDEX acquisitions_by_area ON acquisitions(game_id, location_area_id);
CREATE TABLE pokemon_held_items (
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), game_id INTEGER NOT NULL REFERENCES game_versions(id),
  item_id INTEGER NOT NULL REFERENCES items(id), rarity INTEGER NOT NULL CHECK(rarity BETWEEN 0 AND 100),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id, game_id, item_id)
);

-- Items -----------------------------------------------------------------------
CREATE TABLE item_generations (
  item_id INTEGER NOT NULL REFERENCES items(id), generation_id INTEGER NOT NULL REFERENCES generations(id),
  game_index INTEGER NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(item_id, generation_id, game_index)
);
CREATE TABLE item_game_data (
  item_id INTEGER NOT NULL REFERENCES items(id), version_group_id INTEGER NOT NULL REFERENCES version_groups(id),
  flavor_text TEXT, purchase_price INTEGER CHECK(purchase_price IS NULL OR purchase_price>=0),
  sell_price INTEGER CHECK(sell_price IS NULL OR sell_price>=0),
  price_provenance TEXT NOT NULL CHECK(price_provenance IN ('version-group','default-cost','unknown')),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(item_id, version_group_id)
);
CREATE TABLE item_effects (
  item_id INTEGER PRIMARY KEY REFERENCES items(id), short_effect TEXT NOT NULL, effect TEXT NOT NULL,
  wording TEXT NOT NULL CHECK(wording IN ('current')), evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE item_attributes (
  item_id INTEGER NOT NULL REFERENCES items(id), flag TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(item_id, flag)
);
CREATE TABLE shops (
  id TEXT PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES game_versions(id),
  location_id INTEGER REFERENCES locations(id), name TEXT NOT NULL,
  prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)), verification_status TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE shop_items (
  shop_id TEXT NOT NULL REFERENCES shops(id), item_id INTEGER NOT NULL REFERENCES items(id),
  price INTEGER CHECK(price IS NULL OR price>=0), prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)),
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(shop_id, item_id)
);

-- Natures ---------------------------------------------------------------------
CREATE TABLE natures (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, increased_stat TEXT NOT NULL,
  decreased_stat TEXT NOT NULL, likes_flavor TEXT, hates_flavor TEXT, evidence_id TEXT NOT NULL REFERENCES evidence(id)
);

-- Progression (curated) --------------------------------------------------------
CREATE TABLE milestones (
  id TEXT PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES game_versions(id), slug TEXT NOT NULL, name TEXT NOT NULL,
  ord INTEGER NOT NULL, kind TEXT NOT NULL, location_id INTEGER REFERENCES locations(id),
  prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)), spoiler_level TEXT NOT NULL,
  verification_status TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), UNIQUE(game_id, slug)
);
CREATE TABLE trainer_battles (
  id TEXT PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES game_versions(id),
  milestone_id TEXT REFERENCES milestones(id), name TEXT NOT NULL, trainer_class TEXT NOT NULL,
  location_id INTEGER REFERENCES locations(id), prize_money INTEGER, verification_status TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE trainer_party (
  battle_id TEXT NOT NULL REFERENCES trainer_battles(id), slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 6),
  form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 100),
  gender TEXT, ability_id INTEGER REFERENCES abilities(id), held_item_id INTEGER REFERENCES items(id),
  moves TEXT CHECK(moves IS NULL OR json_valid(moves)), verification_status TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(battle_id, slot)
);

-- Coverage and explicit gaps -----------------------------------------------------
CREATE TABLE coverage (
  game_id INTEGER NOT NULL REFERENCES game_versions(id), feature TEXT NOT NULL, subject TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('complete','partial','missing','disputed')), note TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(game_id, feature, subject)
);
CREATE TABLE data_issues (
  id TEXT PRIMARY KEY, game_id INTEGER REFERENCES game_versions(id), feature TEXT NOT NULL, subject TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('missing','disputed','unverified')), description TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE INDEX pokemon_types_by_type ON pokemon_types(generation_id, type_id);
CREATE INDEX pokemon_abilities_by_ability ON pokemon_abilities(ability_id, generation_id);
CREATE INDEX move_game_data_by_type ON move_game_data(version_group_id, type_id);
CREATE INDEX pokemon_forms_by_species ON pokemon_forms(species_id);
CREATE INDEX pokemon_version_groups_by_vg ON pokemon_version_groups(version_group_id);
CREATE INDEX held_items_by_item ON pokemon_held_items(game_id, item_id);
CREATE INDEX location_areas_by_location ON location_areas(location_id);
