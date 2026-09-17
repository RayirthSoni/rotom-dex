import { describe, expect, it } from 'vitest'
import { exportToText, parseImport } from './transfer'
import { SAVE_SCHEMA, SAVE_VERSION, type Playthrough } from './schema'

const playthrough: Playthrough = {
  id: 'p1',
  name: 'Hoenn run',
  game: 'emerald',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
  currentLocation: 'rustboro-city',
  visitedLocations: ['littleroot-town'],
  completedMilestones: ['littleroot-arrival'],
  bag: ['oran-berry'],
  tradeAccess: 'none',
  spoilerLevel: 'hint',
  closedWorld: { milestones: true, locations: false, bag: false, party: false, trade: false },
  team: [{ id: 'm1', pokemon: 'ralts', nickname: null, level: 12, moves: ['confusion'], nature: 'modest', ability: 'synchronize', heldItem: null }],
  pinnedPlans: [],
}

describe('save files', () => {
  it('round-trips without losing anything', () => {
    const result = parseImport(exportToText([playthrough], 'p1', 'snap'), 'snap')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.playthroughs).toEqual([playthrough])
    expect(result.activeId).toBe('p1')
    expect(result.warnings).toEqual([])
  })

  it('refuses a file written by a newer build rather than coercing it', () => {
    const result = parseImport(JSON.stringify({ schema: SAVE_SCHEMA, version: SAVE_VERSION + 5, exportedAt: 'x', playthroughs: [] }), null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.problems[0]!.message).toMatch(/newer version/)
    expect(result.problems[0]!.message).toMatch(/Nothing was changed/)
  })

  it('refuses a file that is not an export at all', () => {
    const result = parseImport(JSON.stringify({ some: 'other tool' }), null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.problems[0]!.path).toBe('schema')
  })

  it('refuses invalid JSON with the parser’s own message', () => {
    const result = parseImport('{ not json', null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.problems[0]!.message).toMatch(/not valid JSON/)
  })

  it('reports every bad field with its path, not just the first', () => {
    const broken = {
      schema: SAVE_SCHEMA,
      version: 1,
      exportedAt: 'x',
      playthroughs: [{ id: 'a', name: '', game: 'Emerald!', createdAt: 'x', updatedAt: 'x', team: [{ id: 'm', pokemon: 'ralts', moves: ['a', 'b', 'c', 'd', 'e'] }] }],
    }
    const result = parseImport(JSON.stringify(broken), null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    const paths = result.problems.map((p) => p.path)
    expect(paths).toContain('playthroughs.0.name')
    expect(paths).toContain('playthroughs.0.game')
    expect(paths).toContain('playthroughs.0.team.0.moves')
  })

  it('caps a team at six and a member at four moves', () => {
    const tooMany = { ...playthrough, team: Array.from({ length: 7 }, (_, i) => ({ ...playthrough.team[0]!, id: `m${i}` })) }
    const result = parseImport(exportToText([tooMany], null, null), null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.problems.map((p) => p.path)).toContain('playthroughs.0.team')
  })

  it('warns when the file was exported against a different snapshot', () => {
    const result = parseImport(exportToText([playthrough], 'p1', 'old-snapshot'), 'new-snapshot')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.warnings.join(' ')).toMatch(/different data snapshot/)
    // The playthrough is still imported: it degrades visibly rather than disappearing.
    expect(result.playthroughs).toHaveLength(1)
  })

  it('refuses two playthroughs sharing an id', () => {
    const result = parseImport(exportToText([playthrough, { ...playthrough, name: 'Copy' }], null, null), null)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.problems[0]!.message).toMatch(/share the id/)
  })

  it('drops an activeId that names nothing in the file', () => {
    const result = parseImport(exportToText([playthrough], 'missing', null), null)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.activeId).toBeNull()
  })
})
