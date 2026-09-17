import { describe, expect, it } from 'vitest'
import { countUnknown, flattenLeaves, isCombinator, phraseLeaf, titleise } from './conditions'
import type { Condition } from '@/api/types'

// Every leaf operator in rotom_dex/domain/conditions.py.
const OPS: Array<[string, string | number | undefined]> = [
  ['always', undefined], ['trade', undefined], ['overworld_rain', undefined], ['device_upside_down', undefined],
  ['level_at_least', 20], ['happiness_at_least', 220], ['beauty_at_least', 170], ['affection_at_least', 2],
  ['has_pokemon', 'ralts'], ['has_item', 'sun-stone'], ['use_item', 'sun-stone'], ['held_item', 'dragon-scale'],
  ['knows_move', 'rollout'], ['knows_move_type', 'dark'], ['party_has_pokemon', 'remoraid'], ['party_has_type', 'rock'],
  ['trade_for_pokemon', 'seedot'], ['at_location', 'rustboro-city'], ['in_region', 'hoenn'], ['milestone', 'stone-badge'],
  ['encounter_condition', 'swarm-yes'], ['encounter_pokemon', 'feebas'], ['time_of_day', 'night'],
  ['gender', 'female'], ['stat_relation', 'attack>defense'],
]

describe('condition phrasing', () => {
  it.each(OPS)('renders %s as a readable requirement', (op, value) => {
    const phrase = phraseLeaf(value === undefined ? { op } : { op, value })
    expect(phrase.text.length).toBeGreaterThan(0)
    // Never leak a raw slug or operator name at the user.
    expect(phrase.text).not.toMatch(/_/)
  })

  it('never paraphrases an unknown reason, because it is the project’s own abstention text', () => {
    const reason = 'Day Care/Nursery access, a compatible partner and Ditto availability have not been reviewed.'
    const phrase = phraseLeaf({ op: 'unknown', reason })
    expect(phrase.kind).toBe('unknown')
    expect(phrase.text).toBe(reason)
  })

  it('renders an operator this build does not know rather than dropping it', () => {
    // Dropping an unrecognised prerequisite would make a route look easier than it is.
    const phrase = phraseLeaf({ op: 'some_future_gate', value: 'mystery-key' })
    expect(phrase.kind).toBe('requirement')
    expect(phrase.text).toContain('Some Future Gate')
    expect(phrase.text).toContain('Mystery Key')
  })

  it('walks the tree', () => {
    const condition: Condition = {
      op: 'and',
      args: [
        { op: 'at_location', value: 'rustboro-city' },
        { op: 'or', args: [{ op: 'has_pokemon', value: 'ralts' }, { op: 'unknown', reason: 'not reviewed' }] },
      ],
    }
    expect(isCombinator(condition)).toBe(true)
    expect(flattenLeaves(condition).map((leaf) => leaf.op)).toEqual(['at_location', 'has_pokemon', 'unknown'])
    expect(countUnknown(condition)).toBe(1)
  })

  it('titleises slugs and keeps the abbreviations that are abbreviations', () => {
    expect(titleise('rustboro-city')).toBe('Rustboro City')
    expect(titleise('tm39')).toBe('Tm39')
    expect(titleise('tm-case')).toBe('TM Case')
    expect(titleise(null)).toBe('')
  })
})
