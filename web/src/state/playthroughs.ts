/**
 * Saved playthroughs, persisted to this browser only.
 *
 * Each playthrough owns its game. Switching the browsed game never writes to a playthrough: the
 * browse game lives in the URL, and the active playthrough is chosen explicitly. That is what keeps
 * one save from overwriting another when a player flips between Emerald and Red.
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import {
  SAVE_VERSION,
  migrate,
  emptyClosedWorld,
  storedStateSchema,
  type ClosedWorld,
  type PinnedPlan,
  type Playthrough,
  type TeamMember,
} from './schema'

export const STORAGE_KEY = 'rotom-dex.playthroughs'
export const MAX_TEAM = 6
export const MAX_MOVES = 4

function id(): string {
  return globalThis.crypto?.randomUUID?.() ?? `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function now(): string {
  return new Date().toISOString()
}

export function newPlaythrough(game: string, name: string): Playthrough {
  return {
    id: id(),
    name,
    game,
    createdAt: now(),
    updatedAt: now(),
    currentLocation: null,
    visitedLocations: [],
    completedMilestones: [],
    bag: [],
    tradeAccess: 'none',
    spoilerLevel: 'hint',
    closedWorld: emptyClosedWorld(),
    team: [],
    pinnedPlans: [],
  }
}

export function newMember(pokemon: string): TeamMember {
  return { id: id(), pokemon, nickname: null, level: null, moves: [], nature: null, ability: null, heldItem: null }
}

interface State {
  version: number
  activeId: string | null
  playthroughs: Record<string, Playthrough>
}

interface Actions {
  create: (game: string, name: string) => string
  remove: (playthroughId: string) => void
  rename: (playthroughId: string, name: string) => void
  setActive: (playthroughId: string | null) => void
  update: (playthroughId: string, patch: Partial<Omit<Playthrough, 'id' | 'createdAt'>>) => void
  toggleMilestone: (playthroughId: string, slug: string) => void
  toggleVisited: (playthroughId: string, slug: string) => void
  setClosedWorld: (playthroughId: string, key: keyof ClosedWorld, value: boolean) => void
  addMember: (playthroughId: string, pokemon: string) => void
  removeMember: (playthroughId: string, memberId: string) => void
  updateMember: (playthroughId: string, memberId: string, patch: Partial<Omit<TeamMember, 'id'>>) => void
  pinPlan: (playthroughId: string, plan: Omit<PinnedPlan, 'id' | 'pinnedAt'>) => void
  unpinPlan: (playthroughId: string, planId: string) => void
  replaceAll: (playthroughs: Playthrough[], activeId: string | null) => void
  mergeIn: (playthroughs: Playthrough[]) => { added: number; replaced: number }
  reset: () => void
}

const EMPTY: State = { version: SAVE_VERSION, activeId: null, playthroughs: {} }

function touch(playthrough: Playthrough): Playthrough {
  return { ...playthrough, updatedAt: now() }
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((entry) => entry !== value) : [...list, value]
}

export const usePlaythroughs = create<State & Actions>()(
  persist(
    (set, get) => ({
      ...EMPTY,

      create: (game, name) => {
        const playthrough = newPlaythrough(game, name)
        set((state) => ({
          playthroughs: { ...state.playthroughs, [playthrough.id]: playthrough },
          activeId: playthrough.id,
        }))
        return playthrough.id
      },

      remove: (playthroughId) =>
        set((state) => {
          const next = { ...state.playthroughs }
          delete next[playthroughId]
          const activeId = state.activeId === playthroughId ? (Object.keys(next)[0] ?? null) : state.activeId
          return { playthroughs: next, activeId }
        }),

      rename: (playthroughId, name) => get().update(playthroughId, { name }),

      setActive: (playthroughId) => set({ activeId: playthroughId }),

      update: (playthroughId, patch) =>
        set((state) => {
          const existing = state.playthroughs[playthroughId]
          if (!existing) return state
          return { playthroughs: { ...state.playthroughs, [playthroughId]: touch({ ...existing, ...patch }) } }
        }),

      toggleMilestone: (playthroughId, slug) => {
        const existing = get().playthroughs[playthroughId]
        if (existing) get().update(playthroughId, { completedMilestones: toggle(existing.completedMilestones, slug) })
      },

      toggleVisited: (playthroughId, slug) => {
        const existing = get().playthroughs[playthroughId]
        if (existing) get().update(playthroughId, { visitedLocations: toggle(existing.visitedLocations, slug) })
      },

      setClosedWorld: (playthroughId, key, value) => {
        const existing = get().playthroughs[playthroughId]
        if (existing) get().update(playthroughId, { closedWorld: { ...existing.closedWorld, [key]: value } })
      },

      addMember: (playthroughId, pokemon) => {
        const existing = get().playthroughs[playthroughId]
        if (!existing || existing.team.length >= MAX_TEAM) return
        get().update(playthroughId, { team: [...existing.team, newMember(pokemon)] })
      },

      removeMember: (playthroughId, memberId) => {
        const existing = get().playthroughs[playthroughId]
        if (existing) get().update(playthroughId, { team: existing.team.filter((m) => m.id !== memberId) })
      },

      updateMember: (playthroughId, memberId, patch) => {
        const existing = get().playthroughs[playthroughId]
        if (!existing) return
        const team = existing.team.map((member) => {
          if (member.id !== memberId) return member
          const next = { ...member, ...patch }
          if (next.moves.length > MAX_MOVES) next.moves = next.moves.slice(0, MAX_MOVES)
          return next
        })
        get().update(playthroughId, { team })
      },

      pinPlan: (playthroughId, plan) => {
        const existing = get().playthroughs[playthroughId]
        if (!existing || existing.pinnedPlans.some((p) => p.battle === plan.battle)) return
        get().update(playthroughId, { pinnedPlans: [...existing.pinnedPlans, { ...plan, id: id(), pinnedAt: now() }] })
      },

      unpinPlan: (playthroughId, planId) => {
        const existing = get().playthroughs[playthroughId]
        if (existing) get().update(playthroughId, { pinnedPlans: existing.pinnedPlans.filter((p) => p.id !== planId) })
      },

      replaceAll: (playthroughs, activeId) =>
        set({
          playthroughs: Object.fromEntries(playthroughs.map((p) => [p.id, p])),
          activeId: activeId ?? playthroughs[0]?.id ?? null,
        }),

      mergeIn: (incoming) => {
        let added = 0
        let replaced = 0
        set((state) => {
          const next = { ...state.playthroughs }
          for (const playthrough of incoming) {
            if (next[playthrough.id]) replaced += 1
            else added += 1
            next[playthrough.id] = playthrough
          }
          return { playthroughs: next, activeId: state.activeId ?? incoming[0]?.id ?? null }
        })
        return { added, replaced }
      },

      reset: () => set({ ...EMPTY }),
    }),
    {
      name: STORAGE_KEY,
      version: SAVE_VERSION,
      migrate: (persisted, from) => migrate(persisted, from).value as State,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ version: state.version, activeId: state.activeId, playthroughs: state.playthroughs }),
      // Stored state is still untrusted: another tab, an extension or a hand edit can reach it.
      // A document we cannot parse is discarded rather than allowed to half-load.
      merge: (persisted, current) => {
        const parsed = storedStateSchema.safeParse(persisted)
        if (!parsed.success) return { ...current, ...EMPTY }
        return { ...current, ...parsed.data }
      },
    },
  ),
)

export function activePlaythrough(state: State): Playthrough | null {
  return state.activeId ? (state.playthroughs[state.activeId] ?? null) : null
}

export function playthroughsForGame(state: State, game: string): Playthrough[] {
  return Object.values(state.playthroughs)
    .filter((p) => p.game === game)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

export function orderedPlaythroughs(state: State): Playthrough[] {
  return Object.values(state.playthroughs).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

/** The request body the analysis services expect. Empty fields are omitted, never guessed. */
export function toContext(playthrough: Playthrough): Record<string, unknown> {
  return {
    game: playthrough.game,
    current_location: playthrough.currentLocation,
    visited_locations: playthrough.visitedLocations,
    completed_milestones: playthrough.completedMilestones,
    bag: playthrough.bag,
    trade_access: playthrough.tradeAccess,
    spoiler_level: playthrough.spoilerLevel,
    closed_world: (Object.keys(playthrough.closedWorld) as Array<keyof ClosedWorld>).filter((key) => playthrough.closedWorld[key]),
    team: playthrough.team.map((member) => ({
      pokemon: member.pokemon,
      level: member.level,
      moves: member.moves,
      nature: member.nature,
      ability: member.ability,
      held_item: member.heldItem,
      nickname: member.nickname,
    })),
  }
}
