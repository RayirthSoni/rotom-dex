/** Every game in the catalogue, grouped by generation, each card wearing its cartridge colour. */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { useEnvelope } from '../../api/queries'
import { useKey } from '../../api/SnapshotProvider'
import { QueryBoundary } from '../../components/QueryBoundary'
import { gameColor } from '../../domain/gameColors'
import type { GameListRow } from '../../api/types'
import { useConversations } from '../../state/conversations'

function label(game: GameListRow) {
  return `${game.name}${game.slug.endsWith('-japan') ? ' (Japan)' : ''}`
}

export function GameSelector() {
  const [filter, setFilter] = useState('')
  const navigate = useNavigate()
  const { state, refetch } = useEnvelope<GameListRow[]>(useKey('games'), api.games)

  function choose(game: GameListRow) {
    useConversations.getState().create(game.slug)
    navigate(`/g/${game.slug}/ask`)
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-extrabold tracking-tight">Choose a game</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Your answer changes with your game. Choose the exact version, including its expansion when relevant.
      </p>
      <label className="my-5 block max-w-md text-sm font-medium">
        Find your game
        <input
          type="search"
          className="field mt-2 font-normal"
          aria-label="Filter games"
          placeholder="Emerald, Diamond, Scarlet…"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
      </label>
      <QueryBoundary state={state} onRetry={() => refetch()}>
        {(games) => {
          const shown = games.filter(
            (game) => game.support_tier !== 'excluded' && `${game.name} ${game.slug}`.toLowerCase().includes(filter.toLowerCase()),
          )
          const generations = [...new Set(shown.map((game) => game.generation))].sort((a, b) => a - b)
          return (
            <>
              {generations.map((generation) => (
                <div key={generation} className="game-group">
                  <h2>Generation {generation}</h2>
                  <ul className="game-grid">
                    {shown
                      .filter((game) => game.generation === generation)
                      .map((game) => (
                        <li key={game.slug}>
                          <button type="button" className="game-card" style={{ '--game': gameColor(game.slug) } as React.CSSProperties} onClick={() => choose(game)}>
                            <span className="spine" aria-hidden="true" />
                            <span className="body">
                              <strong>{label(game)}</strong>
                              <span>
                                Generation {game.generation}
                                {game.support_tier === 'catalog' ? ' · Local reference data not yet imported' : ''}
                              </span>
                            </span>
                          </button>
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </>
          )
        }}
      </QueryBoundary>
      <p className="mt-6 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Some questions still need research.{' '}
        <Link className="underline underline-offset-2" to="/coverage">
          View detailed data coverage
        </Link>
      </p>
    </div>
  )
}
