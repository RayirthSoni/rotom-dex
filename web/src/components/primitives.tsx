/** Small shared pieces: chips, badges, cards, section headers. */

import type { ReactNode } from 'react'
import type { CoverageStatus, DerivedStatus } from '@/api/types'
import { titleise } from '@/domain/conditions'

export function TypeChip({ type, size = 'md' }: { type: string; size?: 'sm' | 'md' }) {
  return (
    <span
      className={`inline-flex items-center rounded font-semibold uppercase tracking-wide text-white ${
        size === 'sm' ? 'px-1.5 py-px text-[10px]' : 'px-2 py-0.5 text-[11px]'
      }`}
      style={{ backgroundColor: `var(--type-${type}, var(--color-void-600))` }}
    >
      {type}
    </span>
  )
}

const COVERAGE_STYLE: Record<CoverageStatus, { label: string; fg: string; bg: string; mark: string }> = {
  complete: { label: 'Complete', fg: 'var(--known)', bg: 'var(--known-soft)', mark: '●' },
  partial: { label: 'Partial', fg: 'var(--blocked)', bg: 'var(--blocked-soft)', mark: '◐' },
  missing: { label: 'Missing', fg: 'var(--unknown)', bg: 'var(--unknown-soft)', mark: '○' },
  disputed: { label: 'Disputed', fg: 'var(--alert)', bg: 'var(--alert-soft)', mark: '✕' },
}

export function CoverageChip({ status, label, title }: { status: CoverageStatus; label?: string; title?: string }) {
  const style = COVERAGE_STYLE[status]
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ color: style.fg, backgroundColor: style.bg }}
      title={title}
    >
      <span aria-hidden="true">{style.mark}</span>
      {label ?? style.label}
    </span>
  )
}

const VERDICT_STYLE: Record<DerivedStatus, { fg: string; bg: string }> = {
  reachable: { fg: 'var(--known)', bg: 'var(--known-soft)' },
  locked: { fg: 'var(--blocked)', bg: 'var(--blocked-soft)' },
  unknown: { fg: 'var(--unknown)', bg: 'var(--unknown-soft)' },
  'not-applicable': { fg: 'var(--unknown)', bg: 'var(--unknown-soft)' },
}

export function VerdictChip({ status, label, title }: { status: DerivedStatus; label: string; title?: string }) {
  const style = VERDICT_STYLE[status]
  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold"
      style={{ color: style.fg, backgroundColor: style.bg }}
      title={title}
      data-verdict={status}
    >
      {label}
      {/* `title` is not reachable by keyboard and is not reliably announced, so the explanation is
          also available to a screen reader. */}
      {title ? <span className="sr-only"> — {title}</span> : null}
    </span>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-lg border p-4 ${className}`}
      style={{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--line)' }}
    >
      {children}
    </section>
  )
}

/** `level` exists so a heading nested inside another card does not emit a sibling `h2`. */
export function SectionHeading({ children, hint, level = 2 }: { children: ReactNode; hint?: string; level?: 2 | 3 | 4 }) {
  const Heading = `h${level}` as 'h2' | 'h3' | 'h4'
  return (
    <div className="mb-3">
      <Heading className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-muted)' }}>
        {children}
      </Heading>
      {hint ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'accent' }) {
  return (
    <span
      className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs"
      style={
        tone === 'accent'
          ? { color: 'var(--accent)', borderColor: 'var(--accent)', backgroundColor: 'var(--accent-soft)' }
          : { color: 'var(--ink-muted)', borderColor: 'var(--line)' }
      }
    >
      {children}
    </span>
  )
}

export function Multiplier({ value }: { value: number }) {
  const tone =
    value === 0 ? 'var(--known)' : value > 1 ? 'var(--alert)' : value < 1 ? 'var(--spark)' : 'var(--ink-faint)'
  const label = value === 0 ? '0×' : `${Number.isInteger(value) ? value : value.toFixed(2).replace(/0+$/, '')}×`
  return (
    <span className="font-mono text-xs font-semibold" style={{ color: tone }}>
      {label}
    </span>
  )
}

export function Label({ children }: { children: ReactNode }) {
  return <span className="text-sm">{titleise(String(children))}</span>
}
