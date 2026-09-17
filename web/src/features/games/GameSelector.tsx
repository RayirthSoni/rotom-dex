/**
 * Choosing a game, with what is actually known about it.
 *
 * Three groups, because "no data" has three different meanings here: a game with reviewed facts, a
 * catalogue-only release that was never imported, and a title excluded by the project's support
 * policy. Collapsing them would turn a deliberate decision into an apparent gap.
 */

import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { Card, CoverageChip, SectionHeading } from '@/components/primitives'
import { titleise } from '@/domain/conditions'
import type { CoverageMatrix, CoverageStatus } from '@/api/types'

const MARK: Record<CoverageStatus, string> = { complete: '●', partial: '◐', missing: '○', disputed: '✕' }
const MARK_COLOUR: Record<CoverageStatus, string> = {
  complete: 'var(--known)',
  partial: 'var(--blocked)',
  missing: 'var(--unknown)',
  disputed: 'var(--alert)',
}

/** Features a player actually chooses a game for, in the order they matter for a playthrough. */
const HEADLINE_FEATURES = ['pokemon', 'encounters', 'learnsets', 'evolution', 'item-acquisition', 'progression', 'boss-teams']

function FeatureGrid({ matrix, game }: { matrix: CoverageMatrix; game: CoverageMatrix['games'][number] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
      {HEADLINE_FEATURES.map((feature) => {
        const cell = game.features[feature]
        const status = cell?.status ?? 'missing'
        return (
          <span key={feature} className="inline-flex items-center gap-1 text-[11px]" title={cell?.note}>
            <span aria-hidden="true" style={{ color: MARK_COLOUR[status] }}>
              {MARK[status]}
            </span>
            <span style={{ color: 'var(--ink-faint)' }}>{feature}</span>
          </span>
        )
      })}
      <span className="text-[11px]" style={{ color: 'var(--ink-faint)' }}>
        · {game.counts.complete}/{matrix.features.length} complete
      </span>
    </div>
  )
}

export function GameSelector() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const [showAllFeatures, setShowAllFeatures] = useState(false)
  const { state, refetch } = useEnvelope<CoverageMatrix>(useKey('coverage-matrix'), () => api.coverageMatrix(true))

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-bold tracking-tight">Choose a game</h1>
      <p className="mt-1 max-w-2xl text-sm" style={{ color: 'var(--ink-muted)' }}>
        Every fact in Rotom Dex is scoped to one exact version. Paired versions are separate games, and coverage differs
        between them. Nothing is ever borrowed from a similar game.
      </p>

      <label className="mt-4 block max-w-sm">
        <span className="sr-only">Filter games</span>
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter by name…"
          className="w-full rounded border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
        />
      </label>

      <div className="mt-5">
        <QueryBoundary state={state} onRetry={() => refetch()} skeletonRows={8}>
          {(matrix, envelope) => {
            const needle = filter.trim().toLowerCase()
            const matching = matrix.games.filter((g) => !needle || g.name.toLowerCase().includes(needle) || g.slug.includes(needle))
            const withFacts = matching.filter((g) => g.has_facts)
            const catalogue = matching.filter((g) => !g.has_facts && g.support_tier === 'catalog')
            const excluded = matching.filter((g) => !g.has_facts && g.support_tier === 'excluded')

            return (
              <>
                <SectionHeading hint={`${withFacts.length} games with imported facts. ● complete · ◐ partial · ○ missing · ✕ disputed.`}>
                  Playable
                </SectionHeading>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {withFacts.map((game) => (
                    <li key={game.slug}>
                      <button
                        type="button"
                        onClick={() => navigate(`/g/${game.slug}/journey`)}
                        className="w-full rounded-lg border p-3 text-left transition-colors hover:border-[var(--accent)]"
                        style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface-raised)' }}
                      >
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="font-semibold">{game.name}</span>
                          <span className="shrink-0 text-[11px]" style={{ color: 'var(--ink-faint)' }}>
                            Gen {game.generation} · {game.support_tier}
                          </span>
                        </div>
                        <FeatureGrid matrix={matrix} game={game} />
                      </button>
                    </li>
                  ))}
                </ul>

                {catalogue.length ? (
                  <div className="mt-6">
                    <SectionHeading hint="Recognised releases that were never imported. The catalogue records that they exist; it makes no claim about their contents.">
                      Catalogue only
                    </SectionHeading>
                    <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
                      {catalogue.map((g) => g.name).join(', ')}
                    </p>
                  </div>
                ) : null}

                {excluded.length ? (
                  <div className="mt-6">
                    <SectionHeading hint="Excluded by the project's support policy, not missing by accident.">Not supported</SectionHeading>
                    <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
                      {excluded.map((g) => g.name).join(', ')}
                    </p>
                  </div>
                ) : null}

                <div className="mt-8">
                  <button
                    type="button"
                    onClick={() => setShowAllFeatures((value) => !value)}
                    aria-expanded={showAllFeatures}
                    className="text-sm underline underline-offset-2"
                    style={{ color: 'var(--accent)' }}
                  >
                    {showAllFeatures ? 'Hide the full coverage matrix' : `Show all ${matrix.features.length} features for every game`}
                  </button>
                  {showAllFeatures ? <FullMatrix matrix={matrix} rows={withFacts} /> : null}
                </div>

                <Card className="mt-6">
                  <SectionHeading>Known gaps across every game</SectionHeading>
                  <ul className="space-y-1.5 text-xs" style={{ color: 'var(--ink-muted)' }}>
                    {matrix.global_issues.slice(0, 8).map((issue) => (
                      <li key={issue.id}>
                        <CoverageChip status={issue.kind === 'disputed' ? 'disputed' : 'missing'} label={issue.feature} /> {issue.description}
                      </li>
                    ))}
                  </ul>
                  <AssumptionList assumptions={envelope.assumptions} />
                </Card>
              </>
            )
          }}
        </QueryBoundary>
      </div>
    </div>
  )
}

function FullMatrix({ matrix, rows }: { matrix: CoverageMatrix; rows: CoverageMatrix['games'] }) {
  const features = useMemo(() => matrix.features, [matrix.features])
  return (
    <div className="mt-3 table-scroll" tabIndex={0} role="region" aria-label="Coverage matrix, scrollable">
      <table className="grid w-full min-w-[46rem] border-collapse text-[11px]">
        <caption className="sr-only">Coverage of every feature for every game with imported facts</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 px-2 py-1 text-left" style={{ backgroundColor: 'var(--surface)' }}>
              Game
            </th>
            {features.map((feature) => (
              <th key={feature} scope="col" className="px-1 py-1 text-left align-bottom">
                <span className="block origin-bottom-left translate-y-1 -rotate-45 whitespace-nowrap" style={{ color: 'var(--ink-faint)' }}>
                  {feature}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((game) => (
            <tr key={game.slug}>
              <th scope="row" className="sticky left-0 z-10 whitespace-nowrap px-2 py-1 text-left font-medium" style={{ backgroundColor: 'var(--surface)' }}>
                {game.name}
              </th>
              {features.map((feature) => {
                const cell = game.features[feature]
                const status = cell?.status ?? 'missing'
                return (
                  <td key={feature} className="px-1 py-1 text-center" title={`${titleise(feature)}: ${cell?.note ?? 'no data'}`}>
                    <span style={{ color: MARK_COLOUR[status] }}>{MARK[status]}</span>
                    <span className="sr-only">{status}</span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
