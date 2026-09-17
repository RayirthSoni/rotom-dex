import { Navigate } from 'react-router-dom'
import { usePlaythroughs, activePlaythrough } from '@/state/playthroughs'

/** Straight to the active playthrough's game, or to the selector on a first visit. */
export function Landing() {
  const active = usePlaythroughs(activePlaythrough)
  return active ? <Navigate to={`/g/${active.game}/journey`} replace /> : <Navigate to="/games" replace />
}
