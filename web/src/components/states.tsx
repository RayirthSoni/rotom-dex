/**
 * The four states every screen needs, defined once.
 *
 * `NoClaim` is the reason this file exists. A 200 with `data: null` means the project has no
 * reviewed facts to offer, and the API always says why in `assumptions`. Rendering it as an error,
 * or as "not found", would turn an honest silence into a false negative.
 */

import type { ReactNode } from 'react'
import type { ApiError } from '@/api/client'
import type { CoverageRow } from '@/api/types'
import { CoverageChip } from './primitives'

export function Skeleton({ rows = 3, label = 'Loading' }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="space-y-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-4" style={{ width: `${88 - index * 11}%` }} />
      ))}
    </div>
  )
}

export function NoClaim({
  title,
  assumptions,
  coverage = [],
  action,
}: {
  title: string
  assumptions: string[]
  coverage?: CoverageRow[]
  action?: ReactNode
}) {
  const relevant = coverage.filter((row) => row.status !== 'complete')
  return (
    <div
      className="rounded-lg border border-dashed p-4"
      style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-sunken)' }}
      data-state="no-claim"
    >
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-2 space-y-1.5">
        {assumptions.map((assumption) => (
          <li key={assumption} className="text-xs leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
            {assumption}
          </li>
        ))}
      </ul>
      {relevant.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {relevant.map((row) => (
            <CoverageChip key={`${row.feature}:${row.subject}`} status={row.status} label={row.feature} title={row.note} />
          ))}
        </div>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  )
}

export function EmptyResult({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed p-6 text-center" style={{ borderColor: 'var(--line)' }} data-state="empty">
      <p className="text-sm font-medium">{title}</p>
      {hint ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const copy: Record<string, { title: string; body: string }> = {
    offline: {
      title: 'Rotom cannot reach the server',
      body: 'The Rotom Dex API is not responding. Start it with `uv run rotom serve --db data/build/rotom.sqlite3` and try again. Your saved playthroughs are untouched.',
    },
    database_missing: {
      title: 'No snapshot database',
      body: 'The server is running but has no database to read. Build one with `uv run rotom import --db data/build/rotom.sqlite3`.',
    },
    not_found: { title: 'Not in the catalog', body: error.message },
    semantic: { title: 'That does not apply to this game', body: error.message },
    validation: { title: 'Rotom could not read that request', body: error.message },
    server: { title: 'Something went wrong', body: error.message },
  }
  const { title, body } = copy[error.kind] ?? copy.server!
  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: 'var(--alert)', backgroundColor: 'var(--alert-soft)' }}
      role="alert"
      data-state="error"
      data-error-kind={error.kind}
    >
      <p className="text-sm font-semibold" style={{ color: 'var(--alert)' }}>
        {title}
      </p>
      <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
        {body}
      </p>
      {error.fields.length ? (
        <ul className="mt-2 space-y-0.5">
          {error.fields.map((field) => (
            <li key={`${field.path}:${field.message}`} className="font-mono text-[11px]" style={{ color: 'var(--ink-muted)' }}>
              {field.path ? `${field.path}: ` : ''}
              {field.message}
            </li>
          ))}
        </ul>
      ) : null}
      {onRetry && error.retryable ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border px-2.5 py-1 text-xs font-medium"
          style={{ borderColor: 'var(--alert)', color: 'var(--alert)' }}
        >
          Try again
        </button>
      ) : null}
    </div>
  )
}
