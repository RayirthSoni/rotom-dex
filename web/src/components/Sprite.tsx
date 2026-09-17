/**
 * Pokémon and item artwork with an honest fallback.
 *
 * The image is hotlinked from PokéAPI (see `domain/sprites`). While it loads, and whenever it cannot,
 * the viewer sees a circular backdrop tinted with the primary type, never a broken-image glyph.
 * Failed URLs are remembered per instance so a lost connection settles on the backdrop after one
 * attempt instead of retrying on every render.
 */

import { useState } from 'react'
import { itemSprite, officialArtwork, pokemonSprite } from '@/domain/sprites'

function Backdrop({ type, size, children }: { type?: string; size: number; children?: React.ReactNode }) {
  return (
    <span
      className="sprite-backdrop"
      data-type={type ?? 'none'}
      style={{ width: size, height: size, '--backdrop': type ? `var(--type-${type}-glow, var(--line-strong))` : 'var(--line-strong)' } as React.CSSProperties}
    >
      {children}
    </span>
  )
}

function useCandidates(urls: Array<string | null>) {
  const [failed, setFailed] = useState<string[]>([])
  const src = urls.find((url): url is string => Boolean(url) && !failed.includes(url as string)) ?? null
  const fail = () => {
    if (src) setFailed((list) => (list.includes(src) ? list : [...list, src]))
  }
  return { src, fail }
}

export function PokemonSprite({
  formId,
  type,
  size = 64,
  artwork = false,
}: {
  formId: number
  /** Primary type slug, for the backdrop tint. */
  type?: string
  size?: number
  /** Try the official artwork first, then the 96px sprite. One image per page, please. */
  artwork?: boolean
}) {
  const { src, fail } = useCandidates(artwork ? [officialArtwork(formId), pokemonSprite(formId)] : [pokemonSprite(formId)])
  const pixel = src !== null && !src.includes('official-artwork')
  return (
    <Backdrop type={type} size={size}>
      {src ? (
        <img
          src={src}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          draggable={false}
          className={pixel ? 'sprite sprite-pixel' : 'sprite'}
          onError={fail}
        />
      ) : null}
    </Backdrop>
  )
}

export function ItemSprite({ slug, size = 32 }: { slug: string; size?: number }) {
  const { src, fail } = useCandidates([itemSprite(slug)])
  return (
    <Backdrop size={size}>
      {src ? (
        <img src={src} alt="" width={size} height={size} loading="lazy" decoding="async" draggable={false} className="sprite sprite-pixel" onError={fail} />
      ) : null}
    </Backdrop>
  )
}
