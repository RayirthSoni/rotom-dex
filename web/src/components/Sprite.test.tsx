import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ItemSprite, PokemonSprite } from './Sprite'

describe('PokemonSprite', () => {
  it('renders the sprite over a type-tinted backdrop', () => {
    const { container } = render(<PokemonSprite formId={280} type="psychic" />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('src')).toContain('/pokemon/280.png')
    expect(img.getAttribute('alt')).toBe('')
    expect(container.querySelector('.sprite-backdrop')?.getAttribute('data-type')).toBe('psychic')
  })

  it('keeps only the backdrop once the image fails', () => {
    const { container } = render(<PokemonSprite formId={280} type="psychic" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.sprite-backdrop')).not.toBeNull()
  })

  it('falls from artwork to the sprite, then to the backdrop', () => {
    const { container } = render(<PokemonSprite formId={4} type="fire" artwork />)
    expect(container.querySelector('img')!.getAttribute('src')).toContain('official-artwork/4.png')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')!.getAttribute('src')).toContain('/pokemon/4.png')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
  })

  it('renders nothing but the backdrop for an impossible id', () => {
    const { container } = render(<PokemonSprite formId={0} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.sprite-backdrop')).not.toBeNull()
  })
})

describe('ItemSprite', () => {
  it('skips machines, which have no stable sprite name', () => {
    expect(render(<ItemSprite slug="tm39" />).container.querySelector('img')).toBeNull()
    expect(render(<ItemSprite slug="exp-share" />).container.querySelector('img')?.getAttribute('src')).toContain('items/exp-share.png')
  })
})
