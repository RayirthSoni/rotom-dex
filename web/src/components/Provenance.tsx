/**
 * Assumptions, coverage and evidence: the envelope's own words, shown rather than stripped.
 *
 * These are collapsed by default because they appear on every screen, but they are always present
 * and never summarised away.
 */

import { useId, useState } from 'react'
import type { CoverageRow, Evidence } from '@/api/types'
import { CoverageChip } from './primitives'

export function AssumptionList({ assumptions, dense = false }: { assumptions: string[]; dense?: boolean }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  if (!assumptions.length) return null
  const shown = open ? assumptions : assumptions.slice(0, dense ? 1 : 2)
  return (
    <div className="mt-3 text-xs" style={{ color: 'var(--ink-faint)' }}>
      <ul id={id} className="space-y-1">
        {shown.map((assumption) => (
          <li key={assumption} className="flex gap-1.5 leading-relaxed">
            <span aria-hidden="true">·</span>
            <span>{assumption}</span>
          </li>
        ))}
      </ul>
      {assumptions.length > shown.length || open ? (
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls={id}
          className="mt-1 underline underline-offset-2"
          style={{ color: 'var(--ink-muted)' }}
        >
          {open ? 'Show fewer assumptions' : `Show all ${assumptions.length} assumptions`}
        </button>
      ) : null}
    </div>
  )
}

export function CoverageStrip({ coverage }: { coverage: CoverageRow[] }) {
  if (!coverage.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {coverage.map((row) => (
        <CoverageChip key={`${row.feature}:${row.subject}`} status={row.status} label={row.feature} title={row.note} />
      ))}
    </div>
  )
}

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  const [open, setOpen] = useState(false)
  if (!evidence.length) return null
  const sources = evidence.flatMap((entry) => entry.sources)
  const unique = new Map(sources.map((source) => [`${source.source_id}:${source.url}`, source]))
  return (
    <details
      className="mt-3 rounded border text-xs"
      style={{ borderColor: 'var(--line)' }}
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer select-none px-3 py-2" style={{ color: 'var(--ink-muted)' }}>
        Evidence: {evidence.length} record{evidence.length === 1 ? '' : 's'} from {unique.size} source
        {unique.size === 1 ? '' : 's'}
      </summary>
      <ul className="space-y-2 px-3 pb-3">
        {[...unique.values()].map((source) => (
          <li key={`${source.source_id}:${source.url}`}>
            <p className="font-medium">
              {source.source_id} <span style={{ color: 'var(--ink-faint)' }}>({source.kind})</span>
            </p>
            <p className="break-all" style={{ color: 'var(--ink-faint)' }}>
              {source.url.startsWith('http') ? (
                <a href={source.url} target="_blank" rel="noreferrer noopener" className="underline underline-offset-2">
                  {source.url}
                </a>
              ) : (
                source.url
              )}
            </p>
            <p style={{ color: 'var(--ink-faint)' }}>
              {source.selector} · {source.review_status} · {source.license}
            </p>
          </li>
        ))}
      </ul>
    </details>
  )
}
