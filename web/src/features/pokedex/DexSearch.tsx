/** Searchable Pokédex, scoped to one game's version group. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { Button, TypeChip } from '@/components/primitives'
import { PokemonSprite } from '@/components/Sprite'
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
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-extrabold tracking-tight">{titleise(game)} Pokédex</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Forms present in this game's data, with the typings that applied in its generation.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <label className="min-w-[12rem] flex-1">
          <span className="sr-only">Search by name or number</span>
          <input
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Name or National number…"
            className="field"
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
            className="field"
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
              <ul className="dex-grid mt-2">
                {rows.map((row) => (
                  <li key={row.id}>
                    <Link to={`/g/${game}/dex/${row.slug}`} className="dex-tile">
                      <PokemonSprite formId={row.id} type={row.types[0]} size={64} />
                      <span className="dex-number">#{String(row.species_id).padStart(3, '0')}</span>
                      <span className="dex-name">{row.name}</span>
                      <span className="dex-types">
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
                  <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                    Previous
                  </Button>
                  <Button disabled={offset + PAGE >= envelope.pagination.total} onClick={() => setOffset(offset + PAGE)}>
                    Next
                  </Button>
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
