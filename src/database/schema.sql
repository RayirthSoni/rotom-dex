CREATE TABLE schema_version (version INTEGER PRIMARY KEY CHECK(version = 1));
INSERT INTO schema_version VALUES (1);
CREATE TABLE snapshots (id TEXT PRIMARY KEY, pack_sha256 TEXT NOT NULL);
CREATE TABLE sources (
 id TEXT PRIMARY KEY, url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 local_path TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE TABLE evidence (id TEXT PRIMARY KEY);
CREATE TABLE evidence_members (
 evidence_id TEXT NOT NULL REFERENCES evidence(id), source_id TEXT NOT NULL REFERENCES sources(id),
 selector TEXT NOT NULL, PRIMARY KEY(evidence_id,source_id,selector)
);
CREATE TABLE game_versions (
 id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, version_group_id INTEGER NOT NULL,
 version_group TEXT NOT NULL, generation INTEGER NOT NULL CHECK(generation>0),
 support_status TEXT NOT NULL CHECK(support_status IN ('sample','unsupported','supported')),
 evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE species (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE pokemon_forms (
 id INTEGER PRIMARY KEY, species_id INTEGER NOT NULL REFERENCES species(id), slug TEXT NOT NULL UNIQUE,
 form_name TEXT NOT NULL, height_dm INTEGER NOT NULL CHECK(height_dm>0), weight_hg INTEGER NOT NULL CHECK(weight_hg>0),
 evidence_id TEXT NOT NULL REFERENCES evidence(id)
);
CREATE TABLE pokemon_game_data (
 form_id INTEGER NOT NULL REFERENCES pokemon_forms(id), game_id INTEGER NOT NULL REFERENCES game_versions(id),
 availability TEXT NOT NULL CHECK(availability IN ('available','unavailable','unknown')),
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id,game_id)
);
CREATE TABLE types (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE pokemon_types (
 form_id INTEGER NOT NULL, game_id INTEGER NOT NULL, slot INTEGER NOT NULL CHECK(slot IN (1,2)),
 type_id INTEGER NOT NULL REFERENCES types(id), evidence_id TEXT NOT NULL REFERENCES evidence(id),
 PRIMARY KEY(form_id,game_id,slot), UNIQUE(form_id,game_id,type_id),
 FOREIGN KEY(form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id)
);
CREATE TABLE pokemon_stats (
 form_id INTEGER NOT NULL, game_id INTEGER NOT NULL,
 stat TEXT NOT NULL CHECK(stat IN ('hp','attack','defense','special-attack','special-defense','speed')),
 base_stat INTEGER NOT NULL CHECK(base_stat BETWEEN 1 AND 255), evidence_id TEXT NOT NULL REFERENCES evidence(id),
 PRIMARY KEY(form_id,game_id,stat), FOREIGN KEY(form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id)
);
CREATE TABLE abilities (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE pokemon_abilities (
 form_id INTEGER NOT NULL, game_id INTEGER NOT NULL, slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
 ability_id INTEGER NOT NULL REFERENCES abilities(id), is_hidden INTEGER NOT NULL CHECK(is_hidden IN (0,1)),
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id,game_id,slot),
 FOREIGN KEY(form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id)
);
CREATE TABLE moves (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE move_game_data (
 move_id INTEGER NOT NULL REFERENCES moves(id), game_id INTEGER NOT NULL REFERENCES game_versions(id),
 type_id INTEGER NOT NULL REFERENCES types(id), damage_class TEXT NOT NULL CHECK(damage_class IN ('physical','special','status')),
 power INTEGER CHECK(power>=0), accuracy INTEGER CHECK(accuracy BETWEEN 1 AND 100), pp INTEGER NOT NULL CHECK(pp>0),
 effect TEXT, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(move_id,game_id)
);
CREATE TABLE items (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, evidence_id TEXT NOT NULL REFERENCES evidence(id));
CREATE TABLE item_game_data (
 item_id INTEGER NOT NULL REFERENCES items(id), game_id INTEGER NOT NULL REFERENCES game_versions(id), effect TEXT,
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(item_id,game_id)
);
CREATE TABLE learnsets (
 form_id INTEGER NOT NULL, game_id INTEGER NOT NULL, move_id INTEGER NOT NULL, method TEXT NOT NULL,
 level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 100), machine_item_id INTEGER,
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(form_id,game_id,move_id,method,level),
 FOREIGN KEY(form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id),
 FOREIGN KEY(move_id,game_id) REFERENCES move_game_data(move_id,game_id),
 FOREIGN KEY(machine_item_id,game_id) REFERENCES item_game_data(item_id,game_id),
 CHECK((method='machine' AND machine_item_id IS NOT NULL) OR (method!='machine' AND machine_item_id IS NULL))
);
CREATE TABLE evolution_rules (
 id INTEGER NOT NULL, game_id INTEGER NOT NULL, from_form_id INTEGER NOT NULL, to_form_id INTEGER NOT NULL,
 trigger TEXT NOT NULL, conditions TEXT NOT NULL CHECK(json_valid(conditions)), evidence_id TEXT NOT NULL REFERENCES evidence(id),
 PRIMARY KEY(id,game_id), CHECK(from_form_id!=to_form_id),
 FOREIGN KEY(from_form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id),
 FOREIGN KEY(to_form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id)
);
CREATE TABLE locations (
 id INTEGER NOT NULL, game_id INTEGER NOT NULL REFERENCES game_versions(id), slug TEXT NOT NULL, area TEXT NOT NULL,
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(id,game_id)
);
CREATE TABLE acquisitions (
 id TEXT PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES game_versions(id), form_id INTEGER, item_id INTEGER,
 location_id INTEGER, method TEXT NOT NULL, min_level INTEGER CHECK(min_level BETWEEN 1 AND 100),
 max_level INTEGER CHECK(max_level BETWEEN 1 AND 100), chance_percent INTEGER CHECK(chance_percent BETWEEN 0 AND 100),
 availability TEXT NOT NULL CHECK(availability IN ('reachable','locked','unavailable','unknown')),
 prerequisites TEXT NOT NULL CHECK(json_valid(prerequisites)), encounter_conditions TEXT NOT NULL CHECK(json_valid(encounter_conditions)),
 evidence_id TEXT NOT NULL REFERENCES evidence(id), CHECK((form_id IS NULL)!=(item_id IS NULL)),
 CHECK(min_level IS NULL OR max_level>=min_level),
 FOREIGN KEY(form_id,game_id) REFERENCES pokemon_game_data(form_id,game_id),
 FOREIGN KEY(item_id,game_id) REFERENCES item_game_data(item_id,game_id),
 FOREIGN KEY(location_id,game_id) REFERENCES locations(id,game_id)
);
CREATE INDEX acquisitions_by_form ON acquisitions(game_id,form_id);
CREATE INDEX acquisitions_by_item ON acquisitions(game_id,item_id);
CREATE TABLE natures (
 id INTEGER NOT NULL, game_id INTEGER NOT NULL REFERENCES game_versions(id), slug TEXT NOT NULL,
 increased_stat TEXT NOT NULL, decreased_stat TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id),
 PRIMARY KEY(id,game_id), UNIQUE(slug,game_id)
);
CREATE TABLE type_effectiveness (
 game_id INTEGER NOT NULL REFERENCES game_versions(id), attack_type_id INTEGER NOT NULL REFERENCES types(id),
 defense_type_id INTEGER NOT NULL REFERENCES types(id), damage_factor INTEGER NOT NULL CHECK(damage_factor IN (0,50,100,200)),
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(game_id,attack_type_id,defense_type_id)
);
CREATE TABLE coverage (
 game_id INTEGER NOT NULL REFERENCES game_versions(id), subject TEXT NOT NULL, feature TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('complete','partial','missing','disputed')),
 note TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(game_id,subject,feature)
);
