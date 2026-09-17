/**
 * Artwork URLs, derived in the browser from ids the API already returns.
 *
 * The data pipeline is offline and carries no images, so this is the one runtime fetch the interface
 * makes. Every URL comes from the PokéAPI sprites repository, and `SPRITE_ORIGIN` is the same prefix
 * the chat screen allowlists for server-provided sprite URLs. Every image that uses one of these
 * falls back to a type-coloured backdrop when the fetch fails, so an offline machine sees a quiet
 * placeholder rather than a broken-image glyph.
 */

export const SPRITE_ORIGIN = 'https://raw.githubusercontent.com/PokeAPI/sprites/'
const BASE = `${SPRITE_ORIGIN}master/sprites`

/** Machines are named by their move's type in the sprite set, which the item payload does not carry. */
const MACHINE_PREFIX = /^(tm|hm|tr)\d+$/

function validId(id: number): boolean {
  return Number.isInteger(id) && id > 0 && id < 100000
}

/** The 96px front sprite for a form (`pokemon_forms.id`, which is PokéAPI's pokemon id). */
export function pokemonSprite(formId: number): string | null {
  return validId(formId) ? `${BASE}/pokemon/${formId}.png` : null
}

/** The official Ken Sugimori artwork for a form, ~475px. Fetched only on a detail hero. */
export function officialArtwork(formId: number): string | null {
  return validId(formId) ? `${BASE}/pokemon/other/official-artwork/${formId}.png` : null
}

/** An item's bag sprite, keyed by slug. Machines have no stable sprite name, so they get none. */
export function itemSprite(slug: string): string | null {
  if (!/^[a-z0-9-]+$/.test(slug) || MACHINE_PREFIX.test(slug)) return null
  return `${BASE}/items/${slug}.png`
}

export function isAllowedSpriteUrl(url: string | null | undefined): url is string {
  return typeof url === 'string' && url.startsWith(SPRITE_ORIGIN)
}
