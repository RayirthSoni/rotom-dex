/** Searchable Pokédex, scoped to one game's version group. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { TypeChip } from '@/components/primitives'
import { useGame } from '@/state/useGame'
import { titleise } from '@/domain/conditions'
import type { PokemonListRow, Vocabulary } from '@/api/types'

const PAGE = 40

export function DexSearch() {
  const game = useGame()
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [offset, setOffset] = useState(0)

  // Debounce so a search does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(term.trim())
      setOffset(0)
    }, 220)
    return () => clearTimeout(timer)
  }, [term])

  const vocabulary = useEnvelope<Vocabulary>(useKey(game, 'vocabulary'), () => api.vocabulary(game))
  const results = useEnvelope<PokemonListRow[]>(useKey(game, 'pokemon', query, type, offset), () =>
    api.pokemonSearch(game, { q: query || undefined, type: type || undefined, limit: PAGE, offset }),
  )

  const types = vocabulary.state.kind === 'ready' ? vocabulary.state.data.types : []

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-bold tracking-tight">Pokédex · {titleise(game)}</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Forms present in this game's data, with the typings that applied in its generation.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <label className="flex-1 min-w-[12rem]">
          <span className="sr-only">Search by name or number</span>
          <input
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Name or National number…"
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
          />
        </label>
        <label>
          <span className="sr-only">Filter by type</span>
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value)
              setOffset(0)
            }}
            className="rounded border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
          >
            <option value="">All types</option>
            {types.map((entry) => (
              <option key={entry.slug} value={entry.slug}>
                {entry.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4">
        <QueryBoundary
          state={results.state}
          onRetry={() => results.refetch()}
          skeletonRows={8}
          noClaimTitle={`No Pokémon data for ${titleise(game)}`}
          emptyTitle="No Pokémon match that search"
          emptyHint="Try a different name, number or type. Absence here means nothing matched in this game's data."
        >
          {(rows, envelope) => (
            <>
              <p className="text-xs" style={{ color: 'var(--ink-faint)' }}>
                {envelope.pagination
                  ? `${envelope.pagination.offset + 1}–${Math.min(envelope.pagination.offset + rows.length, envelope.pagination.total)} of ${envelope.pagination.total}`
                  : `${rows.length} results`}
              </p>
              <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                {rows.map((row) => (
                  <li key={row.id}>
                    <Link
                      to={`/g/${game}/dex/${row.slug}`}
                      className="flex items-center gap-3 rounded border px-3 py-2 transition-colors hover:border-[var(--accent)]"
                      style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface-raised)' }}
                    >
                      <span className="w-10 shrink-0 font-mono text-xs" style={{ color: 'var(--ink-faint)' }}>
                        #{String(row.species_id).padStart(3, '0')}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">{row.name}</span>
                      <span className="flex shrink-0 gap-1">
                        {row.types.map((t) => (
                          <TypeChip key={t} type={t} size="sm" />
                        ))}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {envelope.pagination && envelope.pagination.total > PAGE ? (
                <div className="mt-4 flex items-center justify-between">
                  <button
                    type="button"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE))}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-40"
                    style={{ borderColor: 'var(--line-strong)' }}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={offset + PAGE >= envelope.pagination.total}
                    onClick={() => setOffset(offset + PAGE)}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-40"
                    style={{ borderColor: 'var(--line-strong)' }}
                  >
                    Next
                  </button>
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
