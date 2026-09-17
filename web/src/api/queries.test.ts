import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { toState } from './queries'
import type { Envelope } from './types'

function envelope<T>(data: T, assumptions: string[] = []): Envelope<T> {
  return { game: null, snapshot_id: 'abc', coverage_status: 'partial', coverage: [], data, assumptions, evidence: [] }
}

describe('the envelope state machine', () => {
  it('treats data: null as a refusal to claim, never as an error', () => {
    const assumption = "'ralts' exists in the catalog but has no data for red"
    const state = toState(envelope(null, [assumption]), null, false)
    expect(state.kind).toBe('no_claim')
    expect(state.kind === 'no_claim' && state.assumptions).toEqual([assumption])
  })

  it('separates an empty result from an absent one', () => {
    expect(toState(envelope([]), null, false).kind).toBe('empty')
    expect(toState(envelope([{ id: 1 }]), null, false).kind).toBe('ready')
  })

  it('routes each failure to the state that can explain it', () => {
    expect(toState(undefined, new ApiError('offline', 0, 'x'), false).kind).toBe('offline')
    expect(toState(undefined, new ApiError('database_missing', 503, 'x'), false).kind).toBe('database_missing')
    expect(toState(undefined, new ApiError('not_found', 404, 'x'), false).kind).toBe('error')
    expect(toState(undefined, new ApiError('semantic', 400, 'x'), false).kind).toBe('error')
  })

  it('reports loading only while there is nothing to show', () => {
    expect(toState(undefined, null, true).kind).toBe('loading')
    expect(toState(envelope({ a: 1 }), null, false).kind).toBe('ready')
  })
})
