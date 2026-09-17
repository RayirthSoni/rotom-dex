/**
 * Reference tools: the type chart for this game's generation, and natures.
 *
 * Both are generation-scoped, so Red shows a 15×15 chart with no Dark or Steel, and no natures at
 * all — with the mechanic's absence stated rather than left as an empty list.
 */

import { useState } from 'react'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { Card, Multiplier, Pill, SectionHeading, TypeChip } from '@/components/primitives'
import { useGame } from '@/state/useGame'
import { titleise } from '@/domain/conditions'
import type { Matchup, Nature, TypeChart, TypeRow } from '@/api/types'

const FACTOR_LABEL: Record<number, string> = { 0: 'no effect', 50: 'not very effective', 100: 'neutral', 200: 'super effective' }

function Chart({ game }: { game: string }) {
  const { state, refetch } = useEnvelope<TypeChart>(useKey(game, 'type-chart'), () => api.typeChart(game))
  return (
    <Card>
      <SectionHeading hint="Attacking type down the side, defending type across the top. The chart is the one that applied in this game's generation.">
        Type chart
      </SectionHeading>
      <QueryBoundary state={state} onRetry={() => refetch()} skeletonRows={6} noClaimTitle={`No type chart for ${titleise(game)}`}>
        {(chart, envelope) => {
          const types = [...new Set(chart.pairs.map((pair) => pair.attack))]
          const lookup = new Map(chart.pairs.map((pair) => [`${pair.attack}:${pair.defense}`, pair.damage_factor]))
          return (
            <>
              <p className="mb-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
                Generation {chart.generation} · {types.length} types
              </p>
              <div className="table-scroll" tabIndex={0} role="region" aria-label="Type chart, scrollable">
                <table className="w-full min-w-[40rem] border-collapse text-[11px]">
                  <caption className="sr-only">Type effectiveness chart for generation {chart.generation}</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="sticky left-0 z-10 p-1 text-left" style={{ backgroundColor: 'var(--surface-raised)' }}>
                        <span className="sr-only">Attacking type</span>
                      </th>
                      {types.map((type) => (
                        <th key={type} scope="col" className="p-0.5">
                          <TypeChip type={type} size="sm" />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {types.map((attack) => (
                      <tr key={attack}>
                        <th scope="row" className="sticky left-0 z-10 p-0.5 text-left" style={{ backgroundColor: 'var(--surface-raised)' }}>
                          <TypeChip type={attack} size="sm" />
                        </th>
                        {types.map((defense) => {
                          const factor = lookup.get(`${attack}:${defense}`) ?? 100
                          const label = `${titleise(attack)} against ${titleise(defense)}: ${FACTOR_LABEL[factor] ?? `${factor}%`}`
                          return (
                            <td key={defense} className="p-0.5 text-center" title={label}>
                              {factor === 100 ? (
                                <span style={{ color: 'var(--ink-faint)' }}>·</span>
                              ) : (
                                <Multiplier value={factor / 100} />
                              )}
                              <span className="sr-only">{label}</span>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <AssumptionList assumptions={envelope.assumptions} dense />
            </>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

function Matchups({ game }: { game: string }) {
  const [attack, setAttack] = useState('')
  const [defense, setDefense] = useState('')
  const [defense2, setDefense2] = useState('')
  const types = useEnvelope<TypeRow[]>(useKey(game, 'types'), () => api.types(game))
  const ready = attack && defense
  const matchup = useEnvelope<Matchup>(useKey(game, 'matchup', attack, defense, defense2), () => api.matchup(game, attack, defense, defense2 || undefined), {
    enabled: Boolean(ready),
  })
  const options = types.state.kind === 'ready' ? types.state.data : []

  return (
    <Card>
      <SectionHeading hint="Type multipliers only. Abilities, items and move-specific interactions are not applied.">
        Matchup calculator
      </SectionHeading>
      <div className="flex flex-wrap gap-2">
        <label className="text-sm">
          <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Attacking</span>
          <select value={attack} onChange={(event) => setAttack(event.target.value)} className="field">
            <option value="">Choose…</option>
            {options.map((type) => (<option key={type.slug} value={type.slug}>{type.name}</option>))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Defending</span>
          <select value={defense} onChange={(event) => setDefense(event.target.value)} className="field">
            <option value="">Choose…</option>
            {options.map((type) => (<option key={type.slug} value={type.slug}>{type.name}</option>))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Second type</span>
          <select value={defense2} onChange={(event) => setDefense2(event.target.value)} className="field">
            <option value="">None</option>
            {options.map((type) => (<option key={type.slug} value={type.slug}>{type.name}</option>))}
          </select>
        </label>
      </div>
      <div className="mt-3" aria-live="polite">
        {ready ? (
          <QueryBoundary state={matchup.state} onRetry={() => matchup.refetch()} skeletonRows={1}>
            {(result, envelope) => (
              <>
                <p className="text-sm">
                  <TypeChip type={result.attack} /> against {result.defenses.map((type) => <TypeChip key={type} type={type} />)} ={' '}
                  <Multiplier value={result.multiplier} />
                </p>
                <AssumptionList assumptions={envelope.assumptions} dense />
              </>
            )}
          </QueryBoundary>
        ) : (
          <p className="text-sm" style={{ color: 'var(--ink-faint)' }}>Choose an attacking and a defending type.</p>
        )}
      </div>
    </Card>
  )
}

function Natures({ game }: { game: string }) {
  const { state, refetch } = useEnvelope<Nature[]>(useKey(game, 'natures'), () => api.natures(game))
  return (
    <Card>
      <SectionHeading>Natures</SectionHeading>
      <QueryBoundary state={state} onRetry={() => refetch()} skeletonRows={4} noClaimTitle={`Natures in ${titleise(game)}`}>
        {(natures, envelope) => (
          <>
            <ul className="grid gap-1 sm:grid-cols-2">
              {natures.map((nature) => (
                <li key={nature.id} className="flex items-center gap-2 text-sm">
                  <span className="w-20 font-medium">{nature.name}</span>
                  {nature.neutral ? (
                    <Pill>Neutral</Pill>
                  ) : (
                    <span className="text-xs" style={{ color: 'var(--ink-muted)' }}>
                      <span style={{ color: 'var(--known)' }}>+{titleise(nature.increased_stat)}</span>{' '}
                      <span style={{ color: 'var(--blocked)' }}>−{titleise(nature.decreased_stat)}</span>
                    </span>
                  )}
                </li>
              ))}
            </ul>
            <AssumptionList assumptions={envelope.assumptions} dense />
          </>
        )}
      </QueryBoundary>
    </Card>
  )
}

export function ToolsScreen() {
  const game = useGame()
  return (
    <div className="mx-auto max-w-4xl space-y-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{titleise(game)} reference</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
          Every value here is the one that applied in this game, not the current one.
        </p>
      </div>
      <Matchups game={game} />
      <Chart game={game} />
      <Natures game={game} />
    </div>
  )
}
