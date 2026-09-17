/**
 * The application shell: a plasma seam, the active game, and navigation.
 *
 * Desktop keeps the game and team beside the work, as the product spec asks; mobile drops to four
 * bottom tabs. The banner at the top is the one place the "browsing a different game to the one you
 * are playing" distinction is surfaced.
 */

import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useSnapshot } from './api/SnapshotProvider'
import { usePlaythroughs, activePlaythrough, orderedPlaythroughs } from './state/playthroughs'
import { useGameContext } from './state/useGame'
import { titleise } from './domain/conditions'
import { TypeChip } from './components/primitives'

const TABS = [
  { to: 'journey', label: 'Journey', glyph: '◆' },
  { to: 'dex', label: 'Dex', glyph: '◉' },
  { to: 'team', label: 'Team', glyph: '⬢' },
  { to: 'ask', label: 'Ask', glyph: '◌' },
] as const

const SECONDARY_EXTRA = [{ to: 'tools', label: 'Tools' }] as const

const SECONDARY = [
  { to: 'moves', label: 'Moves' },
  { to: 'items', label: 'Items' },
  ...SECONDARY_EXTRA,
] as const

function BackendBanner() {
  const { status, error, retry, online } = useSnapshot()
  if (status === 'ok' && online) return null
  if (status === 'checking') return null
  const message = !online
    ? 'Your browser is offline. Saved playthroughs still work; lookups will resume when the connection returns.'
    : status === 'no_database'
      ? 'The server has no snapshot database. Run `uv run rotom import --db data/build/rotom.sqlite3`.'
      : (error?.message ?? 'The Rotom Dex server is not responding.')
  return (
    <div
      role="status"
      className="px-4 py-2 text-xs"
      style={{ backgroundColor: 'var(--alert-soft)', color: 'var(--alert)' }}
      data-testid="backend-banner"
    >
      <span className="font-semibold">Rotom is disconnected. </span>
      {message}{' '}
      <button type="button" onClick={retry} className="underline underline-offset-2">
        Retry
      </button>
    </div>
  )
}

function GameBanner() {
  const { game, active, browsingElsewhere } = useGameContext()
  const setActive = usePlaythroughs((s) => s.setActive)
  const state = usePlaythroughs()
  if (!game || !browsingElsewhere || !active) return null
  const forThisGame = orderedPlaythroughs(state).find((p) => p.game === game)
  return (
    <div className="px-4 py-2 text-xs" style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }} data-testid="game-banner">
      Viewing <strong>{titleise(game)}</strong>. Your active playthrough is <strong>{active.name}</strong> ({titleise(active.game)}).{' '}
      {forThisGame ? (
        <button type="button" onClick={() => setActive(forThisGame.id)} className="underline underline-offset-2">
          Switch to {forThisGame.name}
        </button>
      ) : (
        <NavLink to="/playthroughs" className="underline underline-offset-2" style={{ color: 'var(--accent)' }}>
          Start a playthrough for {titleise(game)}
        </NavLink>
      )}
    </div>
  )
}

function TeamRail() {
  const { game, playthrough } = useGameContext()
  if (!game) return null
  return (
    <aside className="hidden w-60 shrink-0 border-l p-4 lg:block" style={{ borderColor: 'var(--line)' }}>
      <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-muted)' }}>
        {playthrough ? playthrough.name : 'No playthrough'}
      </h2>
      {playthrough ? (
        <>
          <p className="mt-0.5 text-xs" style={{ color: 'var(--ink-faint)' }}>
            {titleise(playthrough.game)}
            {playthrough.currentLocation ? ` · ${titleise(playthrough.currentLocation)}` : ''}
          </p>
          <ul className="mt-3 space-y-1.5">
            {playthrough.team.length === 0 ? (
              <li className="text-xs" style={{ color: 'var(--ink-faint)' }}>
                No team members yet.
              </li>
            ) : (
              playthrough.team.map((member) => (
                <li key={member.id} className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="truncate">{member.nickname || titleise(member.pokemon)}</span>
                  <span className="shrink-0 font-mono text-xs" style={{ color: 'var(--ink-faint)' }}>
                    {member.level ? `L${member.level}` : '—'}
                  </span>
                </li>
              ))
            )}
          </ul>
          <NavLink to={`/g/${game}/team`} className="mt-3 inline-block text-xs underline underline-offset-2" style={{ color: 'var(--accent)' }}>
            Edit team
          </NavLink>
        </>
      ) : (
        <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
          Reference mode. Start a playthrough to track progress and get preparation advice.
        </p>
      )}
    </aside>
  )
}

export function Shell() {
  const { game } = useGameContext()
  const state = usePlaythroughs()
  const active = activePlaythrough(state)
  const location = useLocation()
  const base = game ? `/g/${game}` : ''

  return (
    <div className="flex min-h-dvh flex-col" style={{ backgroundColor: 'var(--surface)' }}>
      <div className="seam" />
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-3" style={{ borderColor: 'var(--line)' }}>
        <NavLink to="/" className="flex items-baseline gap-2">
          <span className="text-base font-bold tracking-tight">
            Rotom<span style={{ color: 'var(--accent)' }}>Dex</span>
          </span>
        </NavLink>
        {game ? (
          <NavLink
            to="/games"
            className="rounded border px-2 py-0.5 text-xs font-medium"
            style={{ borderColor: 'var(--line-strong)', color: 'var(--ink-muted)' }}
          >
            {titleise(game)} ▾
          </NavLink>
        ) : (
          <NavLink to="/games" className="text-xs underline underline-offset-2" style={{ color: 'var(--accent)' }}>
            Choose a game
          </NavLink>
        )}
        <nav className="ml-auto hidden items-center gap-3 text-sm sm:flex" aria-label="Sections">
          {game
            ? [...TABS, ...SECONDARY].map((tab) => (
                <NavLink
                  key={tab.to}
                  to={`${base}/${tab.to}`}
                  className={({ isActive }) => (isActive ? 'font-semibold' : '')}
                  style={({ isActive }) => ({ color: isActive ? 'var(--accent)' : 'var(--ink-muted)' })}
                >
                  {tab.label}
                </NavLink>
              ))
            : null}
          <NavLink
            to="/playthroughs"
            className={({ isActive }) => (isActive ? 'font-semibold' : '')}
            style={({ isActive }) => ({ color: isActive ? 'var(--accent)' : 'var(--ink-muted)' })}
          >
            Playthroughs{active ? ` · ${active.name}` : ''}
          </NavLink>
        </nav>
      </header>
      <BackendBanner />
      <GameBanner />
      <div className="flex flex-1">
        <main className="min-w-0 flex-1 px-4 pb-24 pt-5 sm:pb-8" key={location.pathname}>
          <Outlet />
        </main>
        <TeamRail />
      </div>
      {game ? (
        <nav
          className="fixed inset-x-0 bottom-0 grid grid-cols-4 border-t sm:hidden"
          style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface-raised)', paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
          aria-label="Sections"
        >
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={`${base}/${tab.to}`}
              className="flex flex-col items-center gap-0.5 py-2 text-[11px]"
              style={({ isActive }) => ({ color: isActive ? 'var(--accent)' : 'var(--ink-muted)' })}
            >
              <span aria-hidden="true" className="text-sm">
                {tab.glyph}
              </span>
              {tab.label}
            </NavLink>
          ))}
        </nav>
      ) : null}
    </div>
  )
}

export { TypeChip }
