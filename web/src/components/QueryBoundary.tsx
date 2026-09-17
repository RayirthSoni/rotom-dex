/** One component that turns an `EnvelopeState` into the right thing on screen. */

import type { ReactNode } from 'react'
import type { EnvelopeState } from '@/api/queries'
import type { Envelope } from '@/api/types'
import { EmptyResult, ErrorState, NoClaim, Skeleton } from './states'

export function QueryBoundary<T>({
  state,
  onRetry,
  noClaimTitle = 'Not recorded for this game',
  emptyTitle = 'Nothing matches',
  emptyHint,
  skeletonRows = 4,
  children,
}: {
  state: EnvelopeState<T>
  onRetry?: () => void
  noClaimTitle?: string
  emptyTitle?: string
  emptyHint?: string
  skeletonRows?: number
  children: (data: NonNullable<T>, envelope: Envelope<T>) => ReactNode
}) {
  switch (state.kind) {
    case 'loading':
      return <Skeleton rows={skeletonRows} />
    case 'offline':
    case 'database_missing':
    case 'error':
      return <ErrorState error={state.error} onRetry={onRetry} />
    case 'no_claim':
      return <NoClaim title={noClaimTitle} assumptions={state.assumptions} coverage={state.coverage} />
    case 'empty':
      return <EmptyResult title={emptyTitle} hint={emptyHint} />
    case 'ready':
      return <>{children(state.data, state.envelope)}</>
  }
}
