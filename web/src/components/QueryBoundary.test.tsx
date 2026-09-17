import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '@/api/client'
import type { EnvelopeState } from '@/api/queries'
import type { Envelope } from '@/api/types'
import { QueryBoundary } from './QueryBoundary'

function envelope<T>(data: T): Envelope<T> {
  return { game: null, snapshot_id: 'x', coverage_status: 'partial', coverage: [], data, assumptions: [], evidence: [] }
}

const CHILD = () => <p>payload rendered</p>

describe('QueryBoundary', () => {
  it('renders "not recorded" for data: null, with the API’s own words', () => {
    const state: EnvelopeState<string[]> = {
      kind: 'no_claim',
      envelope: envelope(null),
      assumptions: ["'ralts' exists in the catalog but has no data for red. This does not by itself prove the Pokemon is unobtainable."],
      coverage: [{ feature: 'encounters', subject: '*', status: 'missing', note: 'No encounters imported.', evidence_id: 'e1' }],
    }
    render(<QueryBoundary state={state} noClaimTitle="Ralts is not recorded for Red">{CHILD}</QueryBoundary>)

    expect(screen.getByText('Ralts is not recorded for Red')).toBeInTheDocument()
    expect(screen.getByText(/does not by itself prove/)).toBeInTheDocument()
    expect(screen.getByText('encounters')).toBeInTheDocument()
    // Crucially: not an error, and not the payload.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('payload rendered')).not.toBeInTheDocument()
  })

  it('distinguishes an empty result from an absent one', () => {
    render(
      <QueryBoundary state={{ kind: 'empty', envelope: envelope([]), data: [] }} emptyTitle="No Pokémon match that search">
        {CHILD}
      </QueryBoundary>,
    )
    expect(screen.getByText('No Pokémon match that search')).toBeInTheDocument()
    expect(screen.queryByText(/not recorded/)).not.toBeInTheDocument()
  })

  it('tells the reader how to fix a missing database', () => {
    const error = new ApiError('database_missing', 503, 'Database not found')
    render(<QueryBoundary state={{ kind: 'database_missing', error }}>{CHILD}</QueryBoundary>)
    expect(screen.getByRole('alert')).toHaveTextContent('rotom import')
  })

  it('offers a retry only where retrying could help', async () => {
    const onRetry = vi.fn()
    const { unmount } = render(
      <QueryBoundary state={{ kind: 'offline', error: new ApiError('offline', 0, 'unreachable') }} onRetry={onRetry}>
        {CHILD}
      </QueryBoundary>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
    unmount()

    render(
      <QueryBoundary state={{ kind: 'error', error: new ApiError('semantic', 400, 'Fairy does not exist in generation 1') }} onRetry={onRetry}>
        {CHILD}
      </QueryBoundary>,
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('lists field paths for a rejected request', () => {
    const error = new ApiError('validation', 422, 'context.team: too long', [{ path: 'context.team', message: 'List should have at most 6 items' }])
    render(<QueryBoundary state={{ kind: 'error', error }}>{CHILD}</QueryBoundary>)
    expect(screen.getByText(/context.team: List should have at most 6 items/)).toBeInTheDocument()
  })

  it('announces loading to assistive technology', () => {
    render(<QueryBoundary state={{ kind: 'loading' }}>{CHILD}</QueryBoundary>)
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true')
  })

  it('renders the payload only when there is one', () => {
    render(<QueryBoundary state={{ kind: 'ready', envelope: envelope(['a']), data: ['a'] }}>{CHILD}</QueryBoundary>)
    expect(screen.getByText('payload rendered')).toBeInTheDocument()
  })
})
