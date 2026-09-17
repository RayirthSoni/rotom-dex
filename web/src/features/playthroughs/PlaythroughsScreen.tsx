/**
 * Managing saved playthroughs: create, switch, delete, export and import.
 *
 * Playthroughs are independent by construction. Each owns its game, and nothing here writes to more
 * than the one being edited, so switching between an Emerald run and a Red run cannot lose either.
 */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey, useSnapshot } from '@/api/SnapshotProvider'
import { Card, CoverageChip, Pill, SectionHeading } from '@/components/primitives'
import { orderedPlaythroughs, usePlaythroughs } from '@/state/playthroughs'
import { exportToText, parseImport, type ImportProblem } from '@/state/transfer'
import { titleise } from '@/domain/conditions'
import type { GameListRow } from '@/api/types'

export function PlaythroughsScreen() {
  const navigate = useNavigate()
  const { snapshotId } = useSnapshot()
  const state = usePlaythroughs()
  const create = usePlaythroughs((s) => s.create)
  const remove = usePlaythroughs((s) => s.remove)
  const setActive = usePlaythroughs((s) => s.setActive)
  const rename = usePlaythroughs((s) => s.rename)
  const mergeIn = usePlaythroughs((s) => s.mergeIn)

  const [game, setGame] = useState('emerald')
  const [name, setName] = useState('')
  const [problems, setProblems] = useState<ImportProblem[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const games = useEnvelope<GameListRow[]>(useKey('games'), () => api.games())
  const playable = games.state.kind === 'ready' ? games.state.data.filter((row) => row.coverage_status !== 'missing') : []
  const list = orderedPlaythroughs(state)

  const onExport = () => {
    const text = exportToText(list, state.activeId, snapshotId)
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `rotom-dex-playthroughs-${new Date().toISOString().slice(0, 10)}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setNotice(`Exported ${list.length} playthrough${list.length === 1 ? '' : 's'}.`)
  }

  const onImport = async (file: File) => {
    setProblems([])
    setNotice(null)
    const result = parseImport(await file.text(), snapshotId)
    if (!result.ok) {
      setProblems(result.problems)
      return
    }
    const { added, replaced } = mergeIn(result.playthroughs)
    setNotice(
      [`Imported ${added} new and updated ${replaced} existing playthrough${added + replaced === 1 ? '' : 's'}.`, ...result.warnings].join(' '),
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-extrabold tracking-tight">Playthroughs</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Saved in this browser only. Export to move them elsewhere or keep a backup — the file holds your progress and team, never
        any Pokémon data.
      </p>

      <Card className="mt-4">
        <SectionHeading>Start a playthrough</SectionHeading>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            const id = create(game, name.trim() || `${titleise(game)} run`)
            setName('')
            navigate(`/g/${game}/journey`)
            return id
          }}
        >
          <label className="text-sm">
            <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Game</span>
            <select
              value={game}
              onChange={(event) => setGame(event.target.value)}
              className="field"
            >
              {playable.map((row) => (
                <option key={row.slug} value={row.slug}>{row.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Name</span>
            <input
              type="text" value={name} maxLength={60} onChange={(event) => setName(event.target.value)}
              placeholder={`${titleise(game)} run`}
              className="field"
            />
          </label>
          <button type="submit" className="btn btn-primary">
            Start
          </button>
        </form>
      </Card>

      <Card className="mt-3">
        <SectionHeading>Saved</SectionHeading>
        {list.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>None yet.</p>
        ) : (
          <ul className="space-y-2">
            {list.map((playthrough) => (
              <li key={playthrough.id} className="rounded border p-3" style={{ borderColor: 'var(--line)' }} data-testid="playthrough-row">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text" value={playthrough.name} aria-label={`Name of ${playthrough.name}`}
                    onChange={(event) => rename(playthrough.id, event.target.value)}
                    className="min-w-0 flex-1 rounded border-transparent bg-transparent px-1 py-0.5 text-sm font-semibold"
                    style={{ color: 'var(--ink)' }}
                  />
                  {state.activeId === playthrough.id ? <Pill tone="accent">Active</Pill> : null}
                </div>
                <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
                  {titleise(playthrough.game)} · {playthrough.team.length} on the team · {playthrough.completedMilestones.length}{' '}
                  milestones · {playthrough.pinnedPlans.length} pinned
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => { setActive(playthrough.id); navigate(`/g/${playthrough.game}/journey`) }}
                    className="rounded border px-2 py-1"
                    style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(playthrough.id)}
                    className="rounded border px-2 py-1"
                    style={{ borderColor: 'var(--line-strong)', color: 'var(--alert)' }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="mt-3">
        <SectionHeading hint="A JSON file holding only your own progress: game, location, milestones, team and pinned plans.">
          Export and import
        </SectionHeading>
        <div className="flex flex-wrap gap-2">
          <button
            type="button" onClick={onExport} disabled={list.length === 0}
            className="btn"
          >
            Export {list.length} playthrough{list.length === 1 ? '' : 's'}
          </button>
          <button
            type="button" onClick={() => fileInput.current?.click()}
            className="btn btn-sm"
          >
            Import a file
          </button>
          <input
            ref={fileInput} type="file" accept="application/json,.json" className="sr-only" data-testid="import-input"
            aria-label="Choose a playthrough export file to import"
            onChange={(event) => { const file = event.target.files?.[0]; if (file) void onImport(file); event.target.value = '' }}
          />
        </div>
        {notice ? (
          <p className="mt-2 text-xs" role="status" style={{ color: 'var(--known)' }} data-testid="import-notice">{notice}</p>
        ) : null}
        {problems.length ? (
          <div className="mt-2 rounded border p-2.5" role="alert" style={{ borderColor: 'var(--alert)', backgroundColor: 'var(--alert-soft)' }} data-testid="import-problems">
            <p className="text-xs font-semibold" style={{ color: 'var(--alert)' }}>
              Nothing was imported. {problems.length} problem{problems.length === 1 ? '' : 's'} with that file:
            </p>
            <ul className="mt-1 space-y-0.5">
              {problems.map((problem) => (
                <li key={`${problem.path}:${problem.message}`} className="font-mono text-[11px]" style={{ color: 'var(--ink-muted)' }}>
                  {problem.path}: {problem.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      {games.state.kind === 'ready' ? (
        <p className="mt-4 text-xs" style={{ color: 'var(--ink-faint)' }}>
          <CoverageChip status="partial" label="note" /> Coverage differs by game. Check the{' '}
          <button type="button" onClick={() => navigate('/games')} className="underline underline-offset-2">game selector</button> before
          committing to a long run.
        </p>
      ) : null}
    </div>
  )
}
