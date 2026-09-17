import { beforeEach, describe, expect, it } from 'vitest'
import { MAX_MOVES, MAX_TEAM, orderedPlaythroughs, playthroughsForGame, toContext, usePlaythroughs } from './playthroughs'

const store = () => usePlaythroughs.getState()

beforeEach(() => {
  localStorage.clear()
  store().reset()
})

describe('playthroughs', () => {
  it('keeps saves for different games independent', () => {
    const emerald = store().create('emerald', 'Hoenn run')
    const red = store().create('red', 'Kanto run')

    store().addMember(emerald, 'ralts')
    store().toggleMilestone(emerald, 'littleroot-arrival')

    const state = usePlaythroughs.getState()
    expect(state.playthroughs[red]!.team).toEqual([])
    expect(state.playthroughs[red]!.completedMilestones).toEqual([])
    expect(state.playthroughs[emerald]!.team).toHaveLength(1)
    expect(playthroughsForGame(state, 'emerald').map((p) => p.id)).toEqual([emerald])
    expect(orderedPlaythroughs(state)).toHaveLength(2)
  })

  it('caps the team and each member’s moves', () => {
    const id = store().create('emerald', 'Hoenn run')
    for (const slug of ['ralts', 'torchic', 'mudkip', 'treecko', 'zigzagoon', 'poochyena', 'wurmple']) {
      store().addMember(id, slug)
    }
    expect(usePlaythroughs.getState().playthroughs[id]!.team).toHaveLength(MAX_TEAM)

    const member = usePlaythroughs.getState().playthroughs[id]!.team[0]!
    store().updateMember(id, member.id, { moves: ['a', 'b', 'c', 'd', 'e', 'f'] })
    expect(usePlaythroughs.getState().playthroughs[id]!.team[0]!.moves).toHaveLength(MAX_MOVES)
  })

  it('toggles milestones and visited locations idempotently', () => {
    const id = store().create('emerald', 'Hoenn run')
    store().toggleMilestone(id, 'stone-badge')
    store().toggleMilestone(id, 'stone-badge')
    expect(usePlaythroughs.getState().playthroughs[id]!.completedMilestones).toEqual([])
    store().toggleVisited(id, 'rustboro-city')
    expect(usePlaythroughs.getState().playthroughs[id]!.visitedLocations).toEqual(['rustboro-city'])
  })

  it('pins a plan once and can unpin it', () => {
    const id = store().create('emerald', 'Hoenn run')
    store().pinPlan(id, { kind: 'boss', battle: 'roxanne', label: 'Leader Roxanne', note: '' })
    store().pinPlan(id, { kind: 'boss', battle: 'roxanne', label: 'Leader Roxanne', note: '' })
    const pinned = usePlaythroughs.getState().playthroughs[id]!.pinnedPlans
    expect(pinned).toHaveLength(1)
    store().unpinPlan(id, pinned[0]!.id)
    expect(usePlaythroughs.getState().playthroughs[id]!.pinnedPlans).toEqual([])
  })

  it('moves the active playthrough on when the active one is deleted', () => {
    const first = store().create('emerald', 'Hoenn run')
    const second = store().create('red', 'Kanto run')
    expect(usePlaythroughs.getState().activeId).toBe(second)
    store().remove(second)
    expect(usePlaythroughs.getState().activeId).toBe(first)
    store().remove(first)
    expect(usePlaythroughs.getState().activeId).toBeNull()
  })

  it('sends only the closed-world families the player vouched for', () => {
    const id = store().create('emerald', 'Hoenn run')
    store().setClosedWorld(id, 'milestones', true)
    store().setClosedWorld(id, 'trade', true)
    const context = toContext(usePlaythroughs.getState().playthroughs[id]!)
    expect(context.closed_world).toEqual(['milestones', 'trade'])
  })

  it('builds a request body the services accept', () => {
    const id = store().create('emerald', 'Hoenn run')
    store().addMember(id, 'ralts')
    const member = usePlaythroughs.getState().playthroughs[id]!.team[0]!
    store().updateMember(id, member.id, { level: 12, moves: ['confusion'], heldItem: 'oran-berry' })
    const context = toContext(usePlaythroughs.getState().playthroughs[id]!) as Record<string, unknown>
    expect(context.game).toBe('emerald')
    // snake_case, and `heldItem` becomes `held_item`, as the API expects.
    expect(context.team).toEqual([
      { pokemon: 'ralts', level: 12, moves: ['confusion'], nature: null, ability: null, held_item: 'oran-berry', nickname: null },
    ])
  })

  it('discards a stored document it cannot parse rather than half-loading it', () => {
    localStorage.setItem('rotom-dex.playthroughs', JSON.stringify({ state: { playthroughs: 'not an object' }, version: 1 }))
    usePlaythroughs.persist.rehydrate()
    expect(usePlaythroughs.getState().playthroughs).toEqual({})
  })
})
