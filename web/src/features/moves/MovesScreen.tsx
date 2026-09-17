/** Searchable moves, with the values that applied in this game's version group. */

import { useEffect, useState } from 'react'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList, EvidenceList } from '@/components/Provenance'
import { Card, Pill, SectionHeading, Stat, TypeChip } from '@/components/primitives'
import { useGame } from '@/state/useGame'
import { titleise } from '@/domain/conditions'
import type { MoveDetail, MoveListRow, Vocabulary } from '@/api/types'

const PAGE = 40

function MoveCard({ game, slug, onClose }: { game: string; slug: string; onClose: () => void }) {
  const { state, refetch } = useEnvelope<MoveDetail>(useKey(game, 'move', slug), () => api.move(game, slug))
  return (
    <Card className="mt-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <SectionHeading>{titleise(slug)}</SectionHeading>
        <button type="button" onClick={onClose} className="text-xs underline underline-offset-2" style={{ color: 'var(--ink-muted)' }}>
          Close
        </button>
      </div>
      <QueryBoundary state={state} onRetry={() => refetch()} skeletonRows={4} noClaimTitle={`${titleise(slug)} has no values in ${titleise(game)}`}>
        {(move, envelope) => (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <TypeChip type={move.type} />
              <Pill>{titleise(move.damage_class)}</Pill>
              {move.machine ? (
                <Pill tone="accent">
                  {move.machine.kind.toUpperCase()}
                  {move.machine.machine_number} · {titleise(move.machine.item)}
                </Pill>
              ) : null}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Power" value={move.power ?? 'No fixed power'} />
              <Stat label="Accuracy" value={move.accuracy ?? 'Never misses'} />
              <Stat label="PP" value={move.pp ?? '—'} />
              <Stat label="Priority" value={move.priority} />
            </dl>
            {move.short_effect ? <p className="mt-3 text-sm">{move.short_effect}</p> : null}
            {move.flavor_text ? (
              <p className="mt-2 text-sm italic" style={{ color: 'var(--ink-muted)' }}>
                “{move.flavor_text.text}”
              </p>
            ) : null}
            <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
              {move.learner_count} Pokémon can learn this in {titleise(game)}.
            </p>
            <AssumptionList assumptions={envelope.assumptions} dense />
            <EvidenceList evidence={envelope.evidence} />
          </>
        )}
      </QueryBoundary>
    </Card>
  )
}

export function MovesScreen() {
  const game = useGame()
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [damageClass, setDamageClass] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(term.trim())
      setOffset(0)
    }, 220)
    return () => clearTimeout(timer)
  }, [term])

  const vocabulary = useEnvelope<Vocabulary>(useKey(game, 'vocabulary'), () => api.vocabulary(game))
  const list = useEnvelope<MoveListRow[]>(useKey(game, 'moves', query, type, damageClass, offset), () =>
    api.moves(game, { q: query || undefined, type: type || undefined, damage_class: damageClass || undefined, limit: PAGE, offset }),
  )
  const vocab = vocabulary.state.kind === 'ready' ? vocabulary.state.data : null

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-bold tracking-tight">Moves · {titleise(game)}</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Power, accuracy, type and damage class as they were in this version group, rewound through the source's changelog.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <label className="flex-1 min-w-[12rem]">
          <span className="sr-only">Search moves</span>
          <input
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Move name…"
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
          />
        </label>
        <label>
          <span className="sr-only">Filter by type</span>
          <select
            value={type}
            onChange={(event) => { setType(event.target.value); setOffset(0) }}
            className="rounded border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
          >
            <option value="">All types</option>
            {vocab?.types.map((entry) => (
              <option key={entry.slug} value={entry.slug}>{entry.name}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by damage class</span>
          <select
            value={damageClass}
            onChange={(event) => { setDamageClass(event.target.value); setOffset(0) }}
            className="rounded border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
          >
            <option value="">All classes</option>
            {(vocab?.damage_classes ?? []).map((entry) => (
              <option key={entry} value={entry}>{titleise(entry)}</option>
            ))}
          </select>
        </label>
      </div>

      {selected ? <MoveCard game={game} slug={selected} onClose={() => setSelected(null)} /> : null}

      <div className="mt-4">
        <QueryBoundary
          state={list.state}
          onRetry={() => list.refetch()}
          skeletonRows={8}
          noClaimTitle={`No move data for ${titleise(game)}`}
          emptyTitle="No moves match"
        >
          {(rows, envelope) => (
            <>
              <p className="text-xs" style={{ color: 'var(--ink-faint)' }}>
                {envelope.pagination ? `${rows.length} of ${envelope.pagination.total}` : `${rows.length} moves`}
              </p>
              <div className="mt-2 table-scroll" tabIndex={0} role="region" aria-label="Moves table, scrollable">
                <table className="grid w-full min-w-[32rem] border-collapse text-sm">
                  <thead>
                    <tr style={{ color: 'var(--ink-faint)' }}>
                      <th scope="col" className="py-1 text-left text-xs font-medium">Move</th>
                      <th scope="col" className="py-1 text-left text-xs font-medium">Type</th>
                      <th scope="col" className="py-1 text-left text-xs font-medium">Class</th>
                      <th scope="col" className="py-1 text-right text-xs font-medium">Pow</th>
                      <th scope="col" className="py-1 text-right text-xs font-medium">Acc</th>
                      <th scope="col" className="py-1 text-right text-xs font-medium">PP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((move) => (
                      <tr key={move.id}>
                        <td className="py-1">
                          <button type="button" onClick={() => setSelected(move.slug)} className="underline underline-offset-2">
                            {move.name}
                          </button>
                        </td>
                        <td className="py-1"><TypeChip type={move.type} size="sm" /></td>
                        <td className="py-1 text-xs" style={{ color: 'var(--ink-muted)' }}>{titleise(move.damage_class)}</td>
                        <td className="py-1 text-right font-mono text-xs">{move.power ?? '—'}</td>
                        <td className="py-1 text-right font-mono text-xs">{move.accuracy ?? '—'}</td>
                        <td className="py-1 text-right font-mono text-xs">{move.pp ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {envelope.pagination && envelope.pagination.total > PAGE ? (
                <div className="mt-4 flex items-center justify-between">
                  <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-40" style={{ borderColor: 'var(--line-strong)' }}>Previous</button>
                  <button type="button" disabled={offset + PAGE >= envelope.pagination.total} onClick={() => setOffset(offset + PAGE)}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-40" style={{ borderColor: 'var(--line-strong)' }}>Next</button>
                </div>
              ) : null}
              <AssumptionList assumptions={envelope.assumptions} dense />
            </>
          )}
        </QueryBoundary>
      </div>
    </div>
  )
}
