/**
 * The browsed game and the active playthrough, kept deliberately separate.
 *
 * The URL owns which game is being *looked at*; a playthrough owns which game is being *played*.
 * Browsing Red while your Emerald save is active is a normal thing to do, and it must not write
 * anything to the Emerald save. When the two differ the shell says so and offers to switch.
 */

import { useParams } from 'react-router-dom'
import { usePlaythroughs, playthroughsForGame, activePlaythrough } from './playthroughs'
import type { Playthrough } from './schema'

export interface GameContext {
  /** The game every query on this page is scoped to. Always defined inside a /g/:game route. */
  game: string
  /** The playthrough being edited, if one exists for this game. */
  playthrough: Playthrough | null
  /** The active playthrough, whatever game it belongs to. */
  active: Playthrough | null
  /** True when the active playthrough is for a different game than the one being browsed. */
  browsingElsewhere: boolean
  candidates: Playthrough[]
}

export function useGameContext(): GameContext {
  const params = useParams<{ game: string }>()
  const game = params.game ?? ''
  const state = usePlaythroughs()
  const active = activePlaythrough(state)
  const candidates = playthroughsForGame(state, game)
  const playthrough = active && active.game === game ? active : (candidates[0] ?? null)
  return {
    game,
    playthrough,
    active,
    browsingElsewhere: Boolean(active && active.game !== game),
    candidates,
  }
}

export function useGame(): string {
  return useParams<{ game: string }>().game ?? ''
}
