/**
 * Data fetching.
 *
 * The snapshot is immutable by construction: changing a source, a pack or the normaliser produces a
 * new snapshot id and a new database. So everything is cached forever under that id, and the only
 * invalidation that exists is "the id changed", handled once in `SnapshotProvider`.
 *
 * `useEnvelope` turns a query into one of six states. `no_claim` is the important one: a 200 with
 * `data: null` means the project declines to claim anything, which is neither an error nor a
 * statement that the thing does not exist.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { ApiError } from './client'
import type { CoverageRow, Envelope } from './types'

export type EnvelopeState<T> =
  | { kind: 'loading' }
  | { kind: 'offline'; error: ApiError }
  | { kind: 'database_missing'; error: ApiError }
  | { kind: 'error'; error: ApiError }
  | { kind: 'no_claim'; envelope: Envelope<null>; assumptions: string[]; coverage: CoverageRow[] }
  | { kind: 'empty'; envelope: Envelope<T>; data: T }
  | { kind: 'ready'; envelope: Envelope<T>; data: NonNullable<T> }

export function toState<T>(
  envelope: Envelope<T> | undefined,
  error: unknown,
  isPending: boolean,
): EnvelopeState<T> {
  if (error instanceof ApiError) {
    if (error.kind === 'offline') return { kind: 'offline', error }
    if (error.kind === 'database_missing') return { kind: 'database_missing', error }
    return { kind: 'error', error }
  }
  if (error) return { kind: 'error', error: new ApiError('server', 0, (error as Error).message) }
  if (isPending || envelope === undefined) return { kind: 'loading' }
  if (envelope.data === null || envelope.data === undefined) {
    return {
      kind: 'no_claim',
      envelope: envelope as unknown as Envelope<null>,
      assumptions: envelope.assumptions,
      coverage: envelope.coverage,
    }
  }
  if (Array.isArray(envelope.data) && envelope.data.length === 0) {
    return { kind: 'empty', envelope, data: envelope.data }
  }
  return { kind: 'ready', envelope, data: envelope.data as NonNullable<T> }
}

type Options<T> = Omit<UseQueryOptions<Envelope<T | null>, ApiError>, 'queryKey' | 'queryFn'>

/**
 * `T` is the payload when there is one. The fetcher may return `Envelope<T | null>`, because an
 * endpoint answering "nothing is claimed here" is a 200, not an error.
 */
export function useEnvelope<T>(key: unknown[], fetcher: () => Promise<Envelope<T | null>>, options: Options<T> = {}) {
  const query = useQuery<Envelope<T | null>, ApiError>({
    queryKey: key,
    queryFn: ({ signal: _signal }) => fetcher(),
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60,
    retry: (attempt, error) => error.retryable && attempt < 2,
    ...options,
  })
  return {
    state: toState<T>(query.data as Envelope<T> | undefined, query.error, query.isPending),
    refetch: query.refetch,
    isFetching: query.isFetching,
  }
}

export function isReady<T>(state: EnvelopeState<T>): state is Extract<EnvelopeState<T>, { kind: 'ready' }> {
  return state.kind === 'ready'
}
