import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useConversations } from './state/conversations'
import { useGameContext } from './state/useGame'
import { useSnapshot } from './api/SnapshotProvider'
import { TypeChip } from './components/primitives'
import { RotomMark } from './components/RotomMark'
import { gameColor } from './domain/gameColors'
import { titleise } from './domain/conditions'

const SECTIONS: Array<[label: string, path: string]> = [
  ['Dex', 'dex'],
  ['Items', 'items'],
  ['Moves', 'moves'],
  ['Tools', 'tools'],
  ['Team', 'team'],
  ['Journey', 'journey'],
]

/**
 * The device. The header is the orange chassis with Rotom's face on it; everything below it is
 * the screen. The chassis keeps the same colour in both themes, so the dark ink on it is fixed too.
 */
export function Shell() {
  const [theme, setTheme] = useState(() => localStorage.getItem('rotom.theme') || 'dark')
  const conversation = useConversations((s) => s.conversations.find((c) => c.id === s.activeId))
  const { game, active, browsingElsewhere } = useGameContext()
  const { status, retry, online } = useSnapshot()
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  const location = useLocation()
  const toolsMenu = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    if (toolsMenu.current) toolsMenu.current.open = false
  }, [location.pathname])
  const chat = location.pathname === '/' || location.pathname.endsWith('/ask')
  const currentGame = game || conversation?.game
  const base = currentGame ? `/g/${currentGame}` : null

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.dataset.theme = next
    localStorage.setItem('rotom.theme', next)
  }

  return (
    <div className={`app-shell ${chat ? 'is-chat' : ''}`}>
      <header className="app-header">
        <Link to="/" className="brand">
          <RotomMark size={30} blink />
          <span className="wordmark">
            rotom<span>dex</span>
          </span>
        </Link>
        <nav className="primary-nav" aria-label="Sections">
          <NavLink to={base ? `${base}/ask` : '/'} end>
            Ask
          </NavLink>
          {base
            ? SECTIONS.map(([label, path]) => (
                <NavLink key={path} to={`${base}/${path}`}>
                  {label}
                </NavLink>
              ))
            : null}
        </nav>
        <div className="header-tools">
          <Link to="/games" className="game-slot" style={{ '--game': gameColor(currentGame) } as React.CSSProperties}>
            <span className="cartridge" aria-hidden="true" />
            <span>{currentGame ? titleise(currentGame) : 'Choose a game'}</span>
          </Link>
          <details ref={toolsMenu} className="reference-menu">
            <summary>
              Explore tools
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
                <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </summary>
            <div>
              <Link to="/games">Choose a game</Link>
              <Link to="/coverage">Data coverage</Link>
              <Link to="/competitive">Competitive</Link>
              <Link to="/playthroughs">Playthroughs</Link>
            </div>
          </details>
          <button type="button" className="theme-toggle" aria-label="Toggle light or dark theme" onClick={toggleTheme}>
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>
      </header>
      <div className="screen">
        {(!online || (status !== 'ok' && status !== 'checking')) && (
          <div className="backend-warning" role="status" data-testid="backend-banner">
            Rotom is disconnected. {status === 'no_database' ? 'Game data is not ready on this server.' : 'Your browser or game server is offline.'} Your
            saved chats are still here. <button onClick={retry}>Retry</button>
          </div>
        )}
        {!chat && game && browsingElsewhere && active && (
          <div className="backend-warning" data-testid="game-banner">
            Viewing {game}. Your active playthrough is <strong>{active.name}</strong> ({active.game}).{' '}
            <Link to="/playthroughs">Start a playthrough for {game.charAt(0).toUpperCase() + game.slice(1)}</Link>
          </div>
        )}
        <main className={chat ? 'main-chat' : 'main-reference'}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
export { TypeChip }
