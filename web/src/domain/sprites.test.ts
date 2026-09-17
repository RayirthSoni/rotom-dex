import { describe, expect, it } from 'vitest'
import { SPRITE_ORIGIN, isAllowedSpriteUrl, itemSprite, officialArtwork, pokemonSprite } from './sprites'

describe('sprite urls', () => {
  it('builds a pokemon sprite from a form id', () => {
    expect(pokemonSprite(280)).toBe(`${SPRITE_ORIGIN}master/sprites/pokemon/280.png`)
    expect(officialArtwork(280)).toBe(`${SPRITE_ORIGIN}master/sprites/pokemon/other/official-artwork/280.png`)
  })

  it('refuses ids that cannot be a form', () => {
    expect(pokemonSprite(0)).toBeNull()
    expect(pokemonSprite(-3)).toBeNull()
    expect(pokemonSprite(2.5)).toBeNull()
    expect(pokemonSprite(Number.NaN)).toBeNull()
    expect(officialArtwork(100000)).toBeNull()
  })

  it('builds an item sprite from a slug but skips machines', () => {
    expect(itemSprite('exp-share')).toBe(`${SPRITE_ORIGIN}master/sprites/items/exp-share.png`)
    expect(itemSprite('tm39')).toBeNull()
    expect(itemSprite('hm01')).toBeNull()
    expect(itemSprite('tr00')).toBeNull()
    expect(itemSprite('../etc')).toBeNull()
  })

  it('allowlists only the sprite origin', () => {
    expect(isAllowedSpriteUrl(pokemonSprite(4))).toBe(true)
    expect(isAllowedSpriteUrl('https://example.com/4.png')).toBe(false)
    expect(isAllowedSpriteUrl(null)).toBe(false)
  })
})
