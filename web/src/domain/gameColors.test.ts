import { describe, expect, it } from 'vitest'
import { GAME_COLOR_FALLBACK, gameColor } from './gameColors'

describe('gameColor', () => {
  it('returns a hex colour for a known version slug', () => {
    expect(gameColor('emerald')).toMatch(/^#[0-9A-F]{6}$/i)
  })

  it('gives an expansion its base game colour', () => {
    expect(gameColor('the-teal-mask-violet')).toBe(gameColor('violet'))
    expect(gameColor('the-crown-tundra-sword')).toBe(gameColor('sword'))
  })

  it('falls back to the chassis for anything unknown', () => {
    expect(gameColor('not-a-game')).toBe(GAME_COLOR_FALLBACK)
    expect(gameColor(null)).toBe(GAME_COLOR_FALLBACK)
  })
})
