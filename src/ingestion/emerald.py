"""Reproducible, offline import of one deliberately bounded Emerald pack."""
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from src.database.connection import connect, initialize
from src.domain import models as m
from src.domain.conditions import validate_condition
from src.ingestion.sources.pokeapi import PokeAPICache

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / 'data/sources/pokeapi'
DEFAULT_PACK = ROOT / 'data/game-packs/emerald/pack.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def unknown(reason):
    return {'op': 'unknown', 'reason': reason}


class Writer:
    def __init__(self, db):
        self.db = db

    def row(self, table, values):
        """Repeated identical rows are safe; conflicting facts fail the transaction."""
        columns = list(values)
        params = [canonical(v) if isinstance(v, (dict, list)) else v for v in values.values()]
        self.db.execute(
            f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in params)}) ON CONFLICT DO NOTHING', params)
        if not self.db.execute(f'SELECT 1 FROM {table} WHERE ' + ' AND '.join(f'{c} IS ?' for c in columns), params).fetchone():
            raise ValueError(f'Conflicting fact in {table}: {values}')

    def add(self, record):
        values = asdict(record)
        for key in ('conditions', 'prerequisites', 'encounter_conditions'):
            if key in values:
                validate_condition(values[key])
        self.row(record.table, values)

    def evidence(self, *refs):
        # Selectors name raw CSV fields (including reviewed filters/derivations).
        refs = sorted(set(refs))
        eid = hashlib.sha256(canonical(refs).encode()).hexdigest()[:24]
        self.row('evidence', {'id': eid})
        for source, selector in refs:
            self.row('evidence_members', {'evidence_id': eid, 'source_id': source, 'selector': selector})
        return eid


def historical(current, past, generation, keys):
    """Past entries are valid through generation_id, inclusive; nearest wins per key.

    Caller uses keys=() for full type sets, slot for abilities, stat_id for stats.
    Empty past ability_id explicitly removes a slot.
    """
    selected = defaultdict(list)
    for row in past:
        if int(row['generation_id']) >= generation:
            selected[tuple(row[k] for k in keys)].append(row)
    result = {tuple(r[k] for k in keys): [r] for r in current} if keys else {(): list(current)}
    for key, rows in selected.items():
        end = min(int(r['generation_id']) for r in rows)
        result[key] = [r for r in rows if int(r['generation_id']) == end]
    return [r for group in result.values() for r in group]


def import_emerald(path, cache_path=DEFAULT_CACHE, pack_path=DEFAULT_PACK):
    cache = PokeAPICache(Path(cache_path))
    pack_bytes = Path(pack_path).read_bytes()
    pack = json.loads(pack_bytes)
    if (pack['format_version'], pack['game_id'], pack['version_group_id'], pack['generation']) != (1, 9, 6, 3):
        raise ValueError('This importer only supports Emerald pack format 1')
    snapshot = hashlib.sha256(canonical(cache.manifest).encode() + pack_bytes + b'emerald-normalizer-v1').hexdigest()
    db = connect(path)
    try:
        initialize(db)
        with db:
            existing = db.execute('SELECT id FROM snapshots').fetchall()
            if existing and [r[0] for r in existing] != [snapshot]:
                raise ValueError('Different source snapshot; import into a new database and review the changes')
            w = Writer(db)
            w.row('snapshots', {'id': snapshot, 'pack_sha256': hashlib.sha256(pack_bytes).hexdigest()})
            for source in cache.manifest['sources']:
                w.add(m.SourceReference(source['id'], source['url'], source['retrieved_at'], source['sha256'], snapshot,
                                        'data/sources/pokeapi/' + source['path'], 'source-derived'))
            w.add(m.SourceReference('emerald-pack', 'local:data/game-packs/emerald/pack.json', pack['reviewed_at'],
                                    hashlib.sha256(pack_bytes).hexdigest(), snapshot,
                                    'data/game-packs/emerald/pack.json', 'applicability-reviewed'))
            populate(cache, pack, w)
            validate_database(db)
        return {'snapshot_id': snapshot, 'counts': table_counts(db)}
    finally:
        db.close()


def populate(c, pack, w):
    game, group, gen = pack['game_id'], pack['version_group_id'], pack['generation']
    roster = set(pack['roster'])
    versions, groups = c.index('versions'), c.index('version_groups')
    ev = w.evidence
    policy = ('emerald-pack', 'policy; exact applicability to Emerald')
    for gid in (game, 7):  # Ruby is a catalog-only negative control, never populated with Emerald facts.
        r = versions[gid]; g = groups[int(r['version_group_id'])]
        w.add(m.GameVersion(gid, r['identifier'], int(g['id']), g['identifier'], int(g['generation_id']),
                            'sample' if gid == game else 'unsupported', ev(('versions', f'id={gid}'), ('version_groups', f'id={g["id"]}'))))
    w.add(m.Coverage(7, '*', 'all', 'missing', 'Ruby catalog identity only; no Ruby facts imported.', ev(policy)))
    species, pokemon, forms = c.index('pokemon_species'), c.index('pokemon'), c.index('pokemon_forms')
    types = {i: r for i, r in c.index('types').items() if i <= 17}
    stats = c.index('stats')
    for tid, r in types.items():
        w.add(m.Type(tid, r['identifier'], ev(('types', f'id={tid}'))))
    obtainable = {int(r['pokemon_id']) for r in c.rows('encounters') if int(r['version_id']) == game}
    reviewed_rules = [r for r in c.rows('pokemon_evolution') if int(r['id']) in pack['reviewed_evolution_ids']]
    for _ in roster:
        for rule in reviewed_rules:
            target = int(rule['evolved_species_id'])
            if int(species[target]['evolves_from_species_id']) in obtainable:
                obtainable.add(target)
    for pid in sorted(roster):
        p, s, f = pokemon[pid], species[pid], forms[pid]
        if int(p['species_id']) != pid or int(f['pokemon_id']) != pid or f['is_default'] != '1' or int(s['generation_id']) > gen:
            raise ValueError('Roster must contain default forms from generation 3 or earlier')
        w.add(m.Species(pid, s['identifier'], ev(('pokemon_species', f'id={pid}'))))
        w.add(m.PokemonForm(pid, pid, p['identifier'], f['form_identifier'] or 'default', int(p['height']), int(p['weight']),
                            ev(('pokemon', f'id={pid}'), ('pokemon_forms', f'id={pid}'))))
        # At least one sourced route establishes existence, but not current reachability.
        w.add(m.PokemonGameData(pid, game, 'available' if pid in obtainable else 'unknown',
                               ev(('encounters', f'version_id=9; pokemon_id={pid}; or reviewed evolution ancestry'),
                                  ('pokemon_evolution', 'reviewed_evolution_ids in emerald-pack'), policy)))
    for name, keys in [('pokemon_types', ()), ('pokemon_stats', ('stat_id',)), ('pokemon_abilities', ('slot',))]:
        now, past = defaultdict(list), defaultdict(list)
        for r in c.rows(name):
            now[int(r['pokemon_id'])].append(r)
        for r in c.rows(name + '_past'):
            past[int(r['pokemon_id'])].append(r)
        abilities = c.index('abilities')
        for pid in sorted(roster):
            evidence = ev((name, f'pokemon_id={pid}'), (name + '_past', f'pokemon_id={pid}; nearest generation_id >= 3'), policy)
            for r in historical(now[pid], past[pid], gen, keys):
                if name == 'pokemon_types':
                    w.add(m.PokemonType(pid, game, int(r['slot']), int(r['type_id']), evidence))
                elif name == 'pokemon_stats':
                    if int(r['stat_id']) <= 6:
                        w.add(m.PokemonStat(pid, game, stats[int(r['stat_id'])]['identifier'], int(r['base_stat']), evidence))
                elif r['ability_id']:
                    aid = int(r['ability_id'])
                    if int(abilities[aid]['generation_id']) > gen or r['is_hidden'] == '1':
                        raise ValueError('Post-Emerald ability survived historical resolution')
                    w.add(m.Ability(aid, abilities[aid]['identifier'], ev(('abilities', f'id={aid}'))))
                    w.add(m.PokemonAbility(pid, game, int(r['slot']), aid, False, evidence))

    learnsets = [r for r in c.rows('pokemon_moves') if int(r['pokemon_id']) in roster and int(r['version_group_id']) == group]
    move_ids = {int(r['move_id']) for r in learnsets}
    machines = {int(r['move_id']): int(r['item_id']) for r in c.rows('machines') if int(r['version_group_id']) == group}
    held_items = [r for r in c.rows('pokemon_items') if int(r['pokemon_id']) in roster and int(r['version_id']) == game]
    item_ids = set(pack['extra_item_ids']) | {int(r['item_id']) for r in held_items}
    item_ids |= {machines[int(r['move_id'])] for r in learnsets if r['pokemon_move_method_id'] == '4'}
    items = c.index('items')
    flavor = {int(r['item_id']): r['flavor_text'] for r in c.rows('item_flavor_text') if int(r['version_group_id']) == group and r['language_id'] == '9'}
    for iid in sorted(item_ids):
        w.add(m.Item(iid, items[iid]['identifier'], ev(('items', f'id={iid}'))))
        text = ' '.join(flavor[iid].split()) if iid in flavor else None
        w.add(m.ItemGameData(iid, game, text, ev(('item_flavor_text', f'item_id={iid}; version_group_id=6; language_id=9'))))
        w.add(m.Coverage(game, f'item:{iid}', 'effects', 'partial' if text else 'missing',
                         'Emerald in-game description only; not a complete mechanical effect model.', ev(policy)))
        w.add(m.Coverage(game, f'item:{iid}', 'acquisition', 'partial' if any(int(r['item_id']) == iid for r in held_items) else 'missing',
                         'Only wild held-item routes are derived; shops, field items and gifts are not covered.', ev(policy)))
    moves = c.index('moves')
    changes = defaultdict(list)
    for r in c.rows('move_changelog'):
        if groups[int(r['changed_in_version_group_id'])]['order'] and int(groups[int(r['changed_in_version_group_id'])]['order']) > int(groups[group]['order']):
            changes[int(r['move_id'])].append(r)
    for mid in sorted(move_ids):
        r = dict(moves[mid])
        for change in sorted(changes[mid], key=lambda x: int(groups[int(x['changed_in_version_group_id'])]['order']), reverse=True):
            for field in ('type_id', 'power', 'accuracy', 'pp'):
                if change[field] != '':
                    r[field] = change[field]
        tid = int(r['type_id'])
        category = 'status' if r['damage_class_id'] == '1' else {'2': 'physical', '3': 'special'}[types[tid]['damage_class_id']]
        w.add(m.Move(mid, r['identifier'], ev(('moves', f'id={mid}'))))
        w.add(m.MoveGameData(mid, game, tid, category, int(r['power']) if r['power'] else None,
                             int(r['accuracy']) if r['accuracy'] else None, int(r['pp']), None,
                             ev(('moves', f'id={mid}'), ('move_changelog', f'move_id={mid}; rewind changes after version_group_id=6'), ('types', f'id={tid}; generation-3 damage class'), policy)))
    methods = c.index('pokemon_move_methods')
    for r in learnsets:
        pid, mid = int(r['pokemon_id']), int(r['move_id'])
        method = methods[int(r['pokemon_move_method_id'])]['identifier']
        refs = [('pokemon_moves', f'pokemon_id={pid}; version_group_id=6; move_id={mid}; method_id={r["pokemon_move_method_id"]}; level={r["level"]}')]
        if method == 'machine':
            refs.append(('machines', f'version_group_id=6; move_id={mid}'))
        w.add(m.LearnsetEntry(pid, game, mid, method, int(r['level']), machines[mid] if method == 'machine' else None, ev(*refs)))

    rules = c.index('pokemon_evolution')
    for rid in pack['reviewed_evolution_ids']:
        r = rules[rid]; target = int(r['evolved_species_id']); origin = int(species[target]['evolves_from_species_id'])
        meaningful = {k: v for k, v in r.items() if v not in ('', '0')}
        expected = {'id', 'evolved_species_id', 'evolution_trigger_id', 'version_group_id', 'is_default', 'minimum_level'}
        if set(meaningful) != expected or r['evolution_trigger_id'] != '1' or r['version_group_id'] != '5':
            raise ValueError(f'Evolution rule {rid} needs review')
        condition = {'op': 'level_at_least', 'value': int(r['minimum_level'])}
        evidence = ev(('pokemon_evolution', f'id={rid}'), ('pokemon_species', f'id={target}; evolves_from_species_id'), policy)
        w.add(m.EvolutionRule(rid, game, origin, target, 'level-up', condition, evidence))
        w.add(m.Acquisition(f'evolution:{game}:{rid}', game, target, None, None, 'evolution', None, None, None, 'unknown',
                            {'op': 'and', 'args': [{'op': 'has_pokemon', 'value': pokemon[origin]['identifier']}, condition]},
                            {'op': 'always'}, evidence))

    encounters = [r for r in c.rows('encounters') if int(r['version_id']) == game and int(r['pokemon_id']) in roster]
    slots, areas, locations = c.index('encounter_slots'), c.index('location_areas'), c.index('locations')
    methods = c.index('encounter_methods')
    condition_map = defaultdict(list)
    conditions = c.index('encounter_condition_values')
    for r in c.rows('encounter_condition_value_map'):
        condition_map[int(r['encounter_id'])].append(conditions[int(r['encounter_condition_value_id'])]['identifier'])
    for r in encounters:
        eid, pid, lid = int(r['id']), int(r['pokemon_id']), int(r['location_area_id'])
        slot, area = slots[int(r['encounter_slot_id'])], areas[lid]
        if int(slot['version_group_id']) != group:
            raise ValueError('Encounter slot version mismatch')
        location = locations[int(area['location_id'])]
        method = methods[int(slot['encounter_method_id'])]['identifier']
        w.add(m.Location(lid, game, location['identifier'], area['identifier'],
                         ev(('location_areas', f'id={lid}'), ('locations', f'id={area["location_id"]}'))))
        prerequisites = {'op': 'and', 'args': [
            {'op': 'at_location', 'value': location['identifier']},
            unknown('Progression, method requirements and gift restrictions have not been reviewed.')]}
        encounter_condition = {'op': 'and', 'args': [{'op': 'encounter_condition', 'value': value} for value in condition_map[eid]]} if condition_map[eid] else {'op': 'always'}
        evidence = ev(('encounters', f'id={eid}; version_id=9'), ('encounter_slots', f'id={r["encounter_slot_id"]}'),
                      ('encounter_condition_value_map', f'encounter_id={eid}'))
        w.add(m.Acquisition(f'encounter:{eid}', game, pid, None, lid, method, int(r['min_level']), int(r['max_level']),
                            int(slot['rarity']) if slot['rarity'] else None, 'unknown', prerequisites, encounter_condition, evidence))
        # A held-item rate is conditional on encountering this species, not a combined encounter probability.
        if method == 'walk':
            for held in held_items:
                if int(held['pokemon_id']) != pid:
                    continue
                iid = int(held['item_id'])
                w.add(m.Acquisition(f'held:{eid}:{iid}', game, None, iid, lid, 'capture-held-item',
                                    int(r['min_level']), int(r['max_level']), int(held['rarity']), 'unknown',
                                    {'op': 'and', 'args': [prerequisites, {'op': 'encounter_pokemon', 'value': pokemon[pid]['identifier']}]},
                                    encounter_condition, ev(('encounters', f'id={eid}; wild {pokemon[pid]["identifier"]}'),
                                    ('pokemon_items', f'pokemon_id={pid}; version_id=9; item_id={iid}'), policy)))

    for r in c.rows('natures'):
        w.add(m.Nature(int(r['id']), game, r['identifier'], stats[int(r['increased_stat_id'])]['identifier'],
                       stats[int(r['decreased_stat_id'])]['identifier'], ev(('natures', f'id={r["id"]}'), policy)))
    past_efficacy = defaultdict(list)
    for r in c.rows('type_efficacy_past'):
        past_efficacy[(r['damage_type_id'], r['target_type_id'])].append(r)
    for r in c.rows('type_efficacy'):
        a, d = int(r['damage_type_id']), int(r['target_type_id'])
        if a not in types or d not in types:
            continue
        applicable = [p for p in past_efficacy[(str(a), str(d))] if int(p['generation_id']) >= gen]
        value = min(applicable, key=lambda p: int(p['generation_id'])) if applicable else r
        w.add(m.TypeEffectiveness(game, a, d, int(value['damage_factor']), ev(('type_efficacy', f'damage_type_id={a}; target_type_id={d}'),
                                  ('type_efficacy_past', f'damage_type_id={a}; target_type_id={d}; nearest generation_id >= 3'), policy)))
    for pid in sorted(roster):
        subject = f'pokemon:{pid}'
        for feature in ('types', 'stats', 'abilities', 'learnset', 'evolution'):
            w.add(m.Coverage(game, subject, feature, 'complete', 'Complete for this default form within the pinned source and reviewed Emerald mapping; not independently game-tested.', ev(policy)))
        w.add(m.Coverage(game, subject, 'acquisition', 'partial', 'Imported exact-version encounters and reviewed evolution routes. Breeding/trades and progression prerequisites remain unreviewed; absent rows do not mean unavailable.', ev(policy)))
        w.add(m.Coverage(game, subject, 'prerequisites', 'missing', pack['gaps'], ev(policy)))
    for feature, status, note in [
        ('roster', 'partial', '10 default forms; all other Pokémon outside sample coverage.'),
        ('natures', 'complete', '25 natures. Identical increase/decrease stats mean neutral.'),
        ('type-effectiveness', 'complete', '17x17 Emerald chart; historical Steel resistances applied.'),
        ('move-effects', 'missing', 'Historical power/accuracy/PP/type/category included; effect descriptions deliberately NULL.'),
        ('ability-effects', 'missing', 'Ability slots only; ability effects not imported.'),
        ('progression', 'missing', 'No reachability graph, milestones or boss data in this foundation.')]:
        w.add(m.Coverage(game, '*', feature, status, note, ev(policy)))


def table_counts(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in tables}


def validate_database(db):
    if db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Broken foreign keys')
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('Database integrity check failed')
    for r in db.execute('SELECT form_id,game_id FROM pokemon_game_data'):
        if db.execute('SELECT count(*) FROM pokemon_stats WHERE form_id=? AND game_id=?', tuple(r)).fetchone()[0] != 6:
            raise ValueError('Each supported form needs six base stats')
        for table in ('pokemon_types', 'pokemon_abilities', 'learnsets'):
            if not db.execute(f'SELECT 1 FROM {table} WHERE form_id=? AND game_id=?', tuple(r)).fetchone():
                raise ValueError(f'Missing required {table}')
    if db.execute('SELECT count(*) FROM type_effectiveness WHERE game_id=9').fetchone()[0] != 289:
        raise ValueError('Incomplete Emerald type chart')
    if db.execute('SELECT count(*) FROM natures WHERE game_id=9').fetchone()[0] != 25:
        raise ValueError('Incomplete nature table')
    if db.execute('SELECT 1 FROM evidence e LEFT JOIN evidence_members m ON e.id=m.evidence_id WHERE m.evidence_id IS NULL').fetchone():
        raise ValueError('Evidence without sources')
    for table, fields in [('evolution_rules', ['conditions']), ('acquisitions', ['prerequisites', 'encounter_conditions'])]:
        for row in db.execute(f'SELECT {",".join(fields)} FROM {table}'):
            for value in row:
                validate_condition(json.loads(value))
