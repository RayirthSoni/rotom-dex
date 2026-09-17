/**
 * Holds the snapshot id and the reachability of the backend.
 *
 * Both are global facts about the session: every cache key is prefixed with the snapshot id, and a
 * failed health check is the difference between "this screen has no data" and "nothing has data".
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, plain } from './client'
import type { Health } from './types'

const SNAPSHOT_STORAGE_KEY = 'rotom-dex.snapshot'

export interface SnapshotContextValue {
  snapshotId: string | null
  database: string | null
  status: 'checking' | 'ok' | 'unreachable' | 'no_database'
  error: ApiError | null
  online: boolean
  retry: () => void
}

const SnapshotContext = createContext<SnapshotContextValue | null>(null)

function readStored(): string | null {
  try {
    return localStorage.getItem(SNAPSHOT_STORAGE_KEY)
  } catch {
    return null
  }
}

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [value, setValue] = useState<Omit<SnapshotContextValue, 'retry' | 'online'>>({
    snapshotId: null,
    database: null,
    status: 'checking',
    error: null,
  })
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    plain<Health>('/health')
      .then((health) => {
        if (cancelled) return
        // A different snapshot means every cached answer describes a different database.
        if (readStored() && readStored() !== health.snapshot_id) client.clear()
        try {
          localStorage.setItem(SNAPSHOT_STORAGE_KEY, health.snapshot_id)
        } catch {
          /* private browsing; the cache simply is not persisted */
        }
        setValue({ snapshotId: health.snapshot_id, database: health.database, status: 'ok', error: null })
      })
      .catch((error: ApiError) => {
        if (cancelled) return
        setValue({
          snapshotId: null,
          database: null,
          status: error.kind === 'database_missing' ? 'no_database' : 'unreachable',
          error,
        })
      })
    return () => {
      cancelled = true
    }
  }, [attempt, client])

  return (
    <SnapshotContext.Provider value={{ ...value, online, retry: () => setAttempt((a) => a + 1) }}>
      {children}
    </SnapshotContext.Provider>
  )
}

export function useSnapshot(): SnapshotContextValue {
  const context = useContext(SnapshotContext)
  if (!context) throw new Error('useSnapshot must be used inside SnapshotProvider')
  return context
}

/** Cache keys are always prefixed with the snapshot, so stale data can never outlive its database. */
export function useKey(...parts: unknown[]): unknown[] {
  const { snapshotId } = useSnapshot()
  return [snapshotId ?? 'unknown', ...parts]
}
