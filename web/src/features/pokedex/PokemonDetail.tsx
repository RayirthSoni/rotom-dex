/**
 * One Pokémon in one game.
 *
 * The card, its evolution family, its learnset and its acquisition routes. When a playthrough is
 * active the prerequisite trees and move access are evaluated against it; otherwise they render as
 * plain requirements, because nothing has been decided.
 */

import { useParams, Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList, CoverageStrip, EvidenceList } from '@/components/Provenance'
import { Card, SectionHeading } from '@/components/primitives'
import { useGameContext } from '@/state/useGame'
import { usePlaythroughs, toContext, MAX_TEAM } from '@/state/playthroughs'
import { titleise } from '@/domain/conditions'
import type { EvolutionChain, LearnsetData, PokemonCard } from '@/api/types'
import { AbilitiesPanel, AcquisitionPanel, EvolutionPanel, IdentityPanel, LearnsetPanel, StatsPanel, TypeHeader } from './panels'

export function PokemonDetail() {
  const { pokemon = '' } = useParams<{ pokemon: string }>()
  const { game, playthrough } = useGameContext()
  const addMember = usePlaythroughs((s) => s.addMember)
  const context = playthrough ? toContext(playthrough) : null

  const card = useEnvelope<PokemonCard>(useKey(game, 'card', pokemon), () => api.pokemon(game, pokemon, 'acquisition,evolution'))
  const chain = useEnvelope<EvolutionChain>(useKey(game, 'chain', pokemon), () => api.evolutionChain(game, pokemon))

  // With a playthrough, the learnset comes back annotated with access; without one, plain.
  // Always ask for access, even with no playthrough: "eligible, access unknown" is the answer that
  // makes the distinction visible, and a bare game context produces exactly that.
  const accessContext = context ?? { game }
  const learnset = useEnvelope<LearnsetData>(
    useKey(game, 'learnset', pokemon, JSON.stringify(accessContext)),
    () => api.moveAccess(accessContext, pokemon),
    { gcTime: 1000 * 60 * 10 },
  )

  const onTeam = playthrough?.team.some((member) => member.pokemon === pokemon) ?? false
  const teamFull = (playthrough?.team.length ?? 0) >= MAX_TEAM

  return (
    <div className="mx-auto max-w-4xl">
      <Link to={`/g/${game}/dex`} className="text-xs underline underline-offset-2" style={{ color: 'var(--ink-muted)' }}>
        ← Back to the Pokédex
      </Link>

      <div className="mt-2">
        <QueryBoundary
          state={card.state}
          onRetry={() => card.refetch()}
          skeletonRows={6}
          noClaimTitle={`${titleise(pokemon)} is not recorded for ${titleise(game)}`}
        >
          {(data, envelope) => (
            <>
              <TypeHeader card={data} coverageStatus={envelope.coverage_status} />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <CoverageStrip coverage={envelope.coverage} />
                {playthrough ? (
                  <button
                    type="button"
                    disabled={onTeam || teamFull}
                    onClick={() => addMember(playthrough.id, data.form.slug)}
                    className="rounded border px-2.5 py-1 text-xs font-medium disabled:opacity-40"
                    style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
                    title={teamFull ? `A team holds at most ${MAX_TEAM}` : onTeam ? 'Already on your team' : undefined}
                  >
                    {onTeam ? 'On your team' : `Add to ${playthrough.name}`}
                  </button>
                ) : null}
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <StatsPanel card={data} />
                <div className="space-y-3">
                  <AbilitiesPanel card={data} />
                  <IdentityPanel card={data} game={game} />
                </div>
              </div>

              <div className="mt-3">
                <QueryBoundary state={chain.state} onRetry={() => chain.refetch()} skeletonRows={3} noClaimTitle="No evolution data for this game">
                  {(chainData) => <EvolutionPanel chain={chainData} game={game} />}
                </QueryBoundary>
              </div>

              <div className="mt-3">
                <QueryBoundary state={learnset.state} onRetry={() => learnset.refetch()} skeletonRows={6} noClaimTitle="No learnset recorded for this game">
                  {(learnsetData, learnsetEnvelope) => (
                    <>
                      <LearnsetPanel data={learnsetData} />
                      <AssumptionList assumptions={learnsetEnvelope.assumptions} dense />
                    </>
                  )}
                </QueryBoundary>
              </div>

              <div className="mt-3">
                {data.acquisition ? (
                  <AcquisitionPanel data={data.acquisition} playthroughActive={Boolean(playthrough)} />
                ) : (
                  <Card>
                    <SectionHeading>How to obtain</SectionHeading>
                    <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
                      No acquisition routes are recorded for this Pokémon in {titleise(game)}. That is not a claim it cannot be
                      obtained.
                    </p>
                  </Card>
                )}
              </div>

              <AssumptionList assumptions={envelope.assumptions} />
              <EvidenceList evidence={envelope.evidence} />
            </>
          )}
        </QueryBoundary>
      </div>
    </div>
  )
}
