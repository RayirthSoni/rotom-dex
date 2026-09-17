/**
 * Progress and preparation.
 *
 * Reviewed progression exists for Emerald's first gym and nowhere else, so the empty state is the
 * common case and has to be useful: it names what is missing rather than showing a blank page.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { Card, Multiplier, Pill, SectionHeading, TypeChip, VerdictChip } from '@/components/primitives'
import { BadgeMark } from '@/components/BadgeMark'
import { toContext, usePlaythroughs } from '@/state/playthroughs'
import { useGameContext } from '@/state/useGame'
import { VERDICT_LABEL, titleise } from '@/domain/conditions'
import type { BattleSummary, BossPreparation, Milestone } from '@/api/types'
import type { ClosedWorld, Playthrough } from '@/state/schema'

const CLOSED_WORLD_COPY: Record<keyof ClosedWorld, string> = {
  milestones: 'My completed-milestone list is complete',
  locations: 'My visited-location list is complete',
  bag: 'My bag list is complete',
  party: 'My party list is complete',
  trade: 'My trade access is as recorded',
}

function ProgressControls({ playthrough }: { playthrough: Playthrough }) {
  const setClosedWorld = usePlaythroughs((s) => s.setClosedWorld)
  const update = usePlaythroughs((s) => s.update)
  return (
    <Card>
      <SectionHeading hint="Rotom only reports something as blocked when you have told it the relevant list is complete. Anything you have not vouched for stays undetermined.">
        What Rotom may assume
      </SectionHeading>
      <ul className="space-y-1.5">
        {(Object.keys(CLOSED_WORLD_COPY) as Array<keyof ClosedWorld>).map((key) => (
          <li key={key}>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={playthrough.closedWorld[key]}
                onChange={(event) => setClosedWorld(playthrough.id, key, event.target.checked)}
                className="mt-1"
              />
              <span>{CLOSED_WORLD_COPY[key]}</span>
            </label>
          </li>
        ))}
      </ul>
      <label className="mt-3 block text-sm">
        <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Spoiler preference</span>
        <select
          value={playthrough.spoilerLevel}
          onChange={(event) => update(playthrough.id, { spoilerLevel: event.target.value as Playthrough['spoilerLevel'] })}
          className="field"
        >
          <option value="none">Hide anything ahead of me</option>
          <option value="hint">Hints only (default)</option>
          <option value="full">Show everything</option>
        </select>
      </label>
      <label className="mt-3 block text-sm">
        <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Trade access</span>
        <select
          value={playthrough.tradeAccess}
          onChange={(event) => update(playthrough.id, { tradeAccess: event.target.value as Playthrough['tradeAccess'] })}
          className="field"
        >
          <option value="none">I cannot trade</option>
          <option value="local">Local trading only</option>
          <option value="any">Any trade</option>
        </select>
      </label>
    </Card>
  )
}

function Checklist({ game, playthrough }: { game: string; playthrough: Playthrough }) {
  const toggle = usePlaythroughs((s) => s.toggleMilestone)
  const update = usePlaythroughs((s) => s.update)
  const { state, refetch } = useEnvelope<Milestone[]>(useKey(game, 'milestones'), () => api.milestones(game))
  return (
    <Card>
      <SectionHeading hint="Curated and reference-reviewed. Ticking a milestone is what lets Rotom say a route is blocked rather than undetermined.">
        Progress checklist
      </SectionHeading>
      <QueryBoundary
        state={state}
        onRetry={() => refetch()}
        skeletonRows={4}
        noClaimTitle={`No reviewed progression for ${titleise(game)}`}
        emptyTitle={`No milestones reviewed for ${titleise(game)} yet`}
        emptyHint="Progression is curated per game. Emerald is reviewed through the first gym; other games have none yet, which is a gap in the reviewed data rather than a claim about the game."
      >
        {(milestones, envelope) => {
          const visible =
            playthrough.spoilerLevel === 'none'
              ? milestones.filter((m) => playthrough.completedMilestones.includes(m.slug) || m.spoiler_level === 'none')
              : milestones
          const hidden = milestones.length - visible.length
          return (
            <>
              <ol className="space-y-1.5">
                {visible.map((milestone) => {
                  const done = playthrough.completedMilestones.includes(milestone.slug)
                  return (
                    <li key={milestone.id}>
                      <label className="flex items-start gap-2 text-sm">
                        <input type="checkbox" checked={done} onChange={() => toggle(playthrough.id, milestone.slug)} className="mt-1" />
                        <span>
                          <span className={done ? 'line-through opacity-60' : ''}>{milestone.name}</span>
                          {milestone.kind === 'badge' ? (
                            <span className="ml-1.5"><Pill tone="accent"><BadgeMark /> Badge</Pill></span>
                          ) : null}
                          {milestone.location ? (
                            <span className="ml-1.5 text-xs" style={{ color: 'var(--ink-faint)' }}>{titleise(milestone.location)}</span>
                          ) : null}
                        </span>
                      </label>
                    </li>
                  )
                })}
              </ol>
              {hidden > 0 ? (
                <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
                  {hidden} later milestone{hidden === 1 ? '' : 's'} hidden by your spoiler preference.
                </p>
              ) : null}
              <label className="mt-3 block text-sm">
                <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Where are you now?</span>
                <select
                  value={playthrough.currentLocation ?? ''}
                  onChange={(event) => update(playthrough.id, { currentLocation: event.target.value || null })}
                  className="field"
                >
                  <option value="">Not recorded</option>
                  {[...new Set(milestones.map((m) => m.location).filter(Boolean))].map((slug) => (
                    <option key={slug} value={slug!}>{titleise(slug!)}</option>
                  ))}
                </select>
              </label>
              <AssumptionList assumptions={envelope.assumptions} dense />
            </>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

function Preparation({ game, playthrough, battle }: { game: string; playthrough: Playthrough; battle: string }) {
  const pin = usePlaythroughs((s) => s.pinPlan)
  const unpin = usePlaythroughs((s) => s.unpinPlan)
  const context = toContext(playthrough)
  const pinned = playthrough.pinnedPlans.find((plan) => plan.battle === battle)
  const { state, refetch } = useEnvelope<BossPreparation>(useKey(game, 'boss', battle, JSON.stringify(context)), () =>
    api.bossPrepare(context, battle), { gcTime: 1000 * 60 * 10 },
  )
  return (
    <QueryBoundary
      state={state}
      onRetry={() => refetch()}
      skeletonRows={5}
      noClaimTitle={`No reviewed roster for this battle in ${titleise(game)}`}
    >
      {(plan, envelope) => (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <SectionHeading hint="Preparation, not a prediction. No battle is simulated and nothing here states an outcome.">
              {plan.battle.name}
            </SectionHeading>
            <button
              type="button"
              onClick={() =>
                pinned ? unpin(playthrough.id, pinned.id) : pin(playthrough.id, { kind: 'boss', battle, label: plan.battle.name, note: '' })
              }
              className="btn btn-sm"
            >
              {pinned ? 'Unpin plan' : 'Pin plan'}
            </button>
          </div>

          <p className="text-xs" style={{ color: 'var(--ink-faint)' }}>
            Their levels {plan.levels.theirs.join(', ')} · yours {plan.levels.yours.length ? plan.levels.yours.join(', ') : 'not recorded'}
            {plan.levels.note ? ` · ${plan.levels.note}` : ''}
          </p>

          <ul className="mt-3 space-y-2">
            {plan.threats.map((threat) => (
              <li key={threat.slot} className="rounded border p-2.5" style={{ borderColor: 'var(--line)' }}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{threat.name}</span>
                  <span className="font-mono text-xs">L{threat.level}</span>
                  {threat.types.map((t) => (<TypeChip key={t} type={t} size="sm" />))}
                  {threat.ability ? <Pill>{titleise(threat.ability)}</Pill> : null}
                  {threat.held_item ? <Pill>{titleise(threat.held_item)}</Pill> : null}
                </div>
                <p className="mt-1 text-xs" style={{ color: 'var(--ink-muted)' }}>
                  Moves: {threat.moves.length ? threat.moves.map(titleise).join(', ') : 'not recorded'}
                </p>
                {threat.our_best_move ? (
                  <p className="mt-1 text-xs">
                    Your best type matchup: <strong>{titleise(threat.our_best_move.move)}</strong> from{' '}
                    {titleise(threat.our_best_move.pokemon)} at <Multiplier value={threat.our_best_move.multiplier} />
                  </p>
                ) : (
                  <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
                    Add moves to your team to see how they line up.
                  </p>
                )}
              </li>
            ))}
          </ul>

          {plan.team.length ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
                What your team takes
              </p>
              <ul className="mt-1 space-y-1 text-xs">
                {plan.team.map((member) => (
                  <li key={member.pokemon}>
                    <strong>{titleise(member.pokemon)}</strong>{' '}
                    {member.note ? (
                      <span style={{ color: 'var(--ink-faint)' }}>{member.note}</span>
                    ) : member.takes_super_effective?.length ? (
                      <span>
                        takes {member.takes_super_effective.map((entry) => `${titleise(entry.move)} (${entry.multiplier}×)`).join(', ')}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--known)' }}>takes nothing super effective from their recorded moves</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {plan.resources.shop_items.length ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
                Supplies you can reach ({plan.resources.counts.reachable ?? 0} of {plan.resources.shop_items.length})
              </p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {plan.resources.shop_items.map((entry) => (
                  <li key={`${entry.shop_id}:${entry.item}`}>
                    <VerdictChip
                      status={entry.derived.status}
                      label={`${entry.item_name}${entry.price ? ` ₽${entry.price}` : ''}`}
                      title={`${VERDICT_LABEL[entry.derived.status]} · ${entry.name}`}
                    />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <AssumptionList assumptions={envelope.assumptions} />
        </Card>
      )}
    </QueryBoundary>
  )
}

function Bosses({ game, playthrough }: { game: string; playthrough: Playthrough }) {
  const [selected, setSelected] = useState<string | null>(null)
  const { state, refetch } = useEnvelope<BattleSummary[]>(useKey(game, 'battles'), () => api.battles(game))
  return (
    <div className="space-y-3">
      <Card>
        <SectionHeading>Reviewed battles</SectionHeading>
        <QueryBoundary
          state={state}
          onRetry={() => refetch()}
          skeletonRows={2}
          noClaimTitle={`No reviewed boss rosters for ${titleise(game)}`}
          emptyTitle={`No boss rosters reviewed for ${titleise(game)} yet`}
          emptyHint="Rosters are curated per battle with reference URLs. Emerald's first gym is reviewed; every other battle in every game is still a gap in the reviewed data."
        >
          {(battles) => (
            <ul className="flex flex-wrap gap-1.5">
              {battles.map((battle) => (
                <li key={battle.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(battle.id.split(':').pop() ?? battle.id)}
                    className="btn btn-sm"
                  >
                    {battle.name}
                    {battle.location ? (
                      <span className="ml-1.5 text-xs" style={{ color: 'var(--ink-faint)' }}>{titleise(battle.location)}</span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>
      </Card>
      {selected ? <Preparation game={game} playthrough={playthrough} battle={selected} /> : null}
    </div>
  )
}

export function JourneyScreen() {
  const { game, playthrough } = useGameContext()
  const unpin = usePlaythroughs((s) => s.unpinPlan)

  if (!playthrough) {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-extrabold tracking-tight">{titleise(game)} journey</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          You are browsing {titleise(game)} in reference mode. Start a playthrough to track milestones, keep a team and get
          preparation advice — it stays in this browser and never touches your other saves.
        </p>
        <div className="mt-3 flex gap-2">
          <Link to="/playthroughs" className="btn btn-sm">
            Start a playthrough
          </Link>
          <Link to={`/g/${game}/dex`} className="btn btn-sm">
            Browse the Pokédex
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-extrabold tracking-tight">Journey · {playthrough.name}</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        {titleise(playthrough.game)}
        {playthrough.currentLocation ? ` · ${titleise(playthrough.currentLocation)}` : ''} ·{' '}
        {playthrough.completedMilestones.length} milestones ticked
      </p>

      {playthrough.pinnedPlans.length ? (
        <Card className="mt-4">
          <SectionHeading>Pinned plans</SectionHeading>
          <ul className="space-y-1">
            {playthrough.pinnedPlans.map((plan) => (
              <li key={plan.id} className="flex items-center justify-between gap-2 text-sm">
                <span>{plan.label}</span>
                <button type="button" onClick={() => unpin(playthrough.id, plan.id)} className="text-xs underline underline-offset-2" style={{ color: 'var(--ink-muted)' }}>
                  Unpin
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <Checklist game={game} playthrough={playthrough} />
        <ProgressControls playthrough={playthrough} />
      </div>

      <div className="mt-3">
        <Bosses game={game} playthrough={playthrough} />
      </div>
    </div>
  )
}
