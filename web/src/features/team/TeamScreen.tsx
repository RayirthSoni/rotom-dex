/**
 * The team editor and its analysis.
 *
 * Mechanics gate the form: a game without Natures has no nature field, and says why rather than
 * offering an input that cannot mean anything. The move picker only offers moves this Pokémon is
 * eligible for in this version group.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList } from '@/components/Provenance'
import { Card, Multiplier, Pill, SectionHeading, TypeChip } from '@/components/primitives'
import { MAX_MOVES, MAX_TEAM, toContext, usePlaythroughs } from '@/state/playthroughs'
import { useGameContext } from '@/state/useGame'
import { titleise } from '@/domain/conditions'
import type { LearnsetData, Nature, PokemonListRow, TeamAnalysis, Vocabulary } from '@/api/types'
import type { TeamMember } from '@/state/schema'

function AddMember({ game, playthroughId, disabled }: { game: string; playthroughId: string; disabled: boolean }) {
  const [term, setTerm] = useState('')
  const addMember = usePlaythroughs((s) => s.addMember)
  const results = useEnvelope<PokemonListRow[]>(useKey(game, 'team-search', term), () => api.pokemonSearch(game, { q: term, limit: 6 }), {
    enabled: term.trim().length >= 2,
  })
  const rows = results.state.kind === 'ready' ? results.state.data : []
  return (
    <div>
      <label className="block">
        <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>
          {disabled ? `A team holds at most ${MAX_TEAM} Pokémon.` : 'Add a Pokémon'}
        </span>
        <input
          type="search"
          value={term}
          disabled={disabled}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="Search by name…"
          className="w-full max-w-sm rounded border px-3 py-2 text-sm disabled:opacity-40"
          style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}
        />
      </label>
      {rows.length ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {rows.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => { addMember(playthroughId, row.slug); setTerm('') }}
                className="rounded border px-2 py-1 text-sm"
                style={{ borderColor: 'var(--line-strong)' }}
              >
                {row.name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function MemberEditor({
  member, game, playthroughId, mechanics, natures,
}: {
  member: TeamMember
  game: string
  playthroughId: string
  mechanics: Record<string, number>
  natures: Nature[]
}) {
  const update = usePlaythroughs((s) => s.updateMember)
  const remove = usePlaythroughs((s) => s.removeMember)
  const learnset = useEnvelope<LearnsetData>(useKey(game, 'learnset-plain', member.pokemon), () => api.learnset(game, member.pokemon))
  const card = useEnvelope<import('@/api/types').PokemonCard>(useKey(game, 'core', member.pokemon), () => api.pokemon(game, member.pokemon))

  // One entry per move. A move learnable both by level-up and by TM is still one move to pick.
  const available = useMemo(() => {
    const rows = learnset.state.kind === 'ready' ? learnset.state.data.moves : []
    const byMove = new Map<string, { move: string; name: string; ways: string[] }>()
    for (const row of rows) {
      const entry = byMove.get(row.move) ?? { move: row.move, name: row.move_name, ways: [] }
      entry.ways.push(row.method === 'level-up' ? `level ${row.level}` : titleise(row.method))
      byMove.set(row.move, entry)
    }
    return [...byMove.values()]
  }, [learnset.state])
  const abilities = card.state.kind === 'ready' ? card.state.data.abilities : []
  const hasAbilities = mechanics.abilities === 1
  const hasNatures = mechanics.natures === 1
  const hasHeldItems = mechanics.held_items === 1
  const unverified = (key: string) => mechanics[key] === undefined

  const toggleMove = (slug: string) => {
    const has = member.moves.includes(slug)
    if (!has && member.moves.length >= MAX_MOVES) return
    update(playthroughId, member.id, { moves: has ? member.moves.filter((m) => m !== slug) : [...member.moves, slug] })
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <Link to={`/g/${game}/dex/${member.pokemon}`} className="text-base font-semibold underline underline-offset-2">
            {titleise(member.pokemon)}
          </Link>
          {card.state.kind === 'ready' ? card.state.data.types.map((t) => <TypeChip key={t.slot} type={t.type} size="sm" />) : null}
        </div>
        <button type="button" onClick={() => remove(playthroughId, member.id)} className="text-xs underline underline-offset-2" style={{ color: 'var(--alert)' }}>
          Remove
        </button>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Nickname</span>
          <input
            type="text" maxLength={24} value={member.nickname ?? ''}
            onChange={(event) => update(playthroughId, member.id, { nickname: event.target.value || null })}
            className="w-full rounded border px-2 py-1.5 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Level</span>
          <input
            type="number" min={1} max={100} value={member.level ?? ''}
            onChange={(event) => update(playthroughId, member.id, { level: event.target.value ? Number(event.target.value) : null })}
            className="w-full rounded border px-2 py-1.5 text-sm"
            style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }} />
        </label>

        {hasAbilities ? (
          <label className="text-sm">
            <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Ability</span>
            <select value={member.ability ?? ''} onChange={(event) => update(playthroughId, member.id, { ability: event.target.value || null })}
              className="w-full rounded border px-2 py-1.5 text-sm"
              style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}>
              <option value="">Not set</option>
              {abilities.map((ability) => (<option key={ability.slot} value={ability.ability}>{ability.name}{ability.is_hidden ? ' (hidden)' : ''}</option>))}
            </select>
          </label>
        ) : (
          <p className="text-xs" style={{ color: 'var(--ink-faint)' }} data-testid="no-abilities">
            <span className="mb-1 block">Ability</span>
            {unverified('abilities') ? `Whether ${titleise(game)} has Abilities is unverified, so the field is not offered.` : `${titleise(game)} has no Abilities.`}
          </p>
        )}

        {hasNatures ? (
          <label className="text-sm">
            <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Nature</span>
            <select value={member.nature ?? ''} onChange={(event) => update(playthroughId, member.id, { nature: event.target.value || null })}
              className="w-full rounded border px-2 py-1.5 text-sm"
              style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }}>
              <option value="">Not set</option>
              {natures.map((nature) => (
                <option key={nature.id} value={nature.slug}>
                  {nature.name}{nature.neutral ? ' (neutral)' : ` (+${titleise(nature.increased_stat)} −${titleise(nature.decreased_stat)})`}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="text-xs" style={{ color: 'var(--ink-faint)' }} data-testid="no-natures">
            <span className="mb-1 block">Nature</span>
            {unverified('natures') ? `Whether ${titleise(game)} has Natures is unverified, so the field is not offered.` : `${titleise(game)} has no Natures.`}
          </p>
        )}

        {hasHeldItems ? (
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block text-xs" style={{ color: 'var(--ink-faint)' }}>Held item (slug)</span>
            <input type="text" value={member.heldItem ?? ''} placeholder="oran-berry"
              onChange={(event) => update(playthroughId, member.id, { heldItem: event.target.value.trim().toLowerCase() || null })}
              className="w-full rounded border px-2 py-1.5 text-sm"
              style={{ borderColor: 'var(--line-strong)', backgroundColor: 'var(--surface-raised)', color: 'var(--ink)' }} />
          </label>
        ) : (
          <p className="text-xs sm:col-span-2" style={{ color: 'var(--ink-faint)' }} data-testid="no-held-items">
            <span className="mb-1 block">Held item</span>
            {unverified('held_items') ? `Whether ${titleise(game)} has held items is unverified.` : `${titleise(game)} has no held items.`}
          </p>
        )}
      </div>

      <div className="mt-3">
        <p className="mb-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
          Moves ({member.moves.length}/{MAX_MOVES}) · only moves this Pokémon can learn in {titleise(game)}
        </p>
        <div className="max-h-44 overflow-y-auto rounded border p-2" style={{ borderColor: 'var(--line)' }}>
          {available.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--ink-faint)' }}>No learnset recorded.</p>
          ) : (
            <ul className="flex flex-wrap gap-1">
              {available.map((move) => {
                const chosen = member.moves.includes(move.move)
                const full = !chosen && member.moves.length >= MAX_MOVES
                return (
                  <li key={move.move}>
                    <button type="button" disabled={full} aria-pressed={chosen} onClick={() => toggleMove(move.move)}
                      className="rounded border px-1.5 py-0.5 text-[11px] disabled:opacity-30"
                      style={{ borderColor: chosen ? 'var(--accent)' : 'var(--line)', color: chosen ? 'var(--accent)' : 'var(--ink-muted)' }}
                      title={`Learned by ${move.ways.join(', ')}`}>
                      {move.name}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </Card>
  )
}

function Analysis({ context }: { context: Record<string, unknown> }) {
  const [withAbilities, setWithAbilities] = useState(true)
  const { state, refetch } = useEnvelope<TeamAnalysis>(useKey('team-analyze', JSON.stringify(context)), () => api.teamAnalyze(context), {
    gcTime: 1000 * 60 * 10,
  })
  return (
    <div className="space-y-3">
      <QueryBoundary state={state} onRetry={() => refetch()} skeletonRows={6} noClaimTitle="No analysis for this game">
        {(analysis, envelope) => {
          const anyAbilityLayer = analysis.team.some((member) => (member.defence?.ability?.modifiers?.length ?? 0) > 0)
          return (
            <>
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <SectionHeading hint="Type multipliers from this generation's chart.">Defensive profile</SectionHeading>
                  {anyAbilityLayer ? (
                    <label className="flex items-center gap-2 text-xs">
                      <input type="checkbox" checked={withAbilities} onChange={(event) => setWithAbilities(event.target.checked)} />
                      Apply reviewed ability modifiers
                    </label>
                  ) : null}
                </div>
                {anyAbilityLayer && withAbilities ? (
                  <p className="mb-2 text-xs" style={{ color: 'var(--blocked)' }} data-testid="ability-layer-note">
                    Showing the ability-adjusted layer. This is a curated overlay, not a fact from the source, and it covers only
                    type-based modifiers.
                  </p>
                ) : null}
                <ul className="space-y-3">
                  {analysis.team.map((member) => {
                    const layer = withAbilities && member.defence?.ability?.weaknesses ? member.defence.ability : member.defence?.basic
                    return (
                      <li key={member.pokemon}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold">{member.nickname || titleise(member.pokemon)}</span>
                          {member.types.map((t) => (<TypeChip key={t} type={t} size="sm" />))}
                          {member.level ? <span className="font-mono text-xs" style={{ color: 'var(--ink-faint)' }}>L{member.level}</span> : null}
                          {member.ability ? <Pill>{titleise(member.ability)}</Pill> : null}
                        </div>
                        {member.note ? (
                          <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>{member.note}</p>
                        ) : layer ? (
                          <div className="mt-1.5 space-y-1 text-xs">
                            <p><span style={{ color: 'var(--alert)' }}>Weak to</span> {layer.weaknesses?.length ? layer.weaknesses.map((t) => <TypeChip key={t} type={t} size="sm" />) : '—'}</p>
                            <p><span style={{ color: 'var(--spark)' }}>Resists</span> {layer.resistances?.length ? layer.resistances.map((t) => <TypeChip key={t} type={t} size="sm" />) : '—'}</p>
                            <p><span style={{ color: 'var(--known)' }}>Immune to</span> {layer.immunities?.length ? layer.immunities.map((t) => <TypeChip key={t} type={t} size="sm" />) : '—'}</p>
                          </div>
                        ) : null}
                      </li>
                    )
                  })}
                </ul>
              </Card>

              {analysis.coverage ? (
                <Card>
                  <SectionHeading hint="Computed from the moves you have actually recorded, not from what the team could learn.">
                    Offensive coverage
                  </SectionHeading>
                  {analysis.coverage.attacking_moves.length === 0 ? (
                    <p className="text-sm" style={{ color: 'var(--ink-muted)' }} data-testid="no-attacking-moves">
                      None of your team's recorded moves deal damage yet, so there is no coverage to report. Add attacking moves
                      to see what this team can hit.
                    </p>
                  ) : (
                  <div className="space-y-2 text-xs">
                    <p>
                      <span style={{ color: 'var(--known)' }}>Super effective against</span>{' '}
                      {analysis.coverage.super_effective_against.length
                        ? analysis.coverage.super_effective_against.map((t) => <TypeChip key={t} type={t} size="sm" />)
                        : 'nothing yet'}
                    </p>
                    <p>
                      <span style={{ color: 'var(--blocked)' }}>Only neutral against</span>{' '}
                      {analysis.coverage.neutral_at_best_against.map((t) => <TypeChip key={t} type={t} size="sm" />)}
                    </p>
                    {analysis.coverage.resisted_against.length ? (
                      <p>
                        <span style={{ color: 'var(--alert)' }}>Resisted by</span>{' '}
                        {analysis.coverage.resisted_against.map((t) => <TypeChip key={t} type={t} size="sm" />)}
                      </p>
                    ) : null}
                    {analysis.coverage.no_effect_against.length ? (
                      <p>
                        <span style={{ color: 'var(--alert)' }}>No move affects</span>{' '}
                        {analysis.coverage.no_effect_against.map((t) => <TypeChip key={t} type={t} size="sm" />)}
                      </p>
                    ) : null}
                  </div>
                  )}
                  {analysis.coverage.excluded_moves.length ? (
                    <div className="mt-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
                        Not counted
                      </p>
                      <ul className="mt-1 space-y-0.5 text-xs" style={{ color: 'var(--ink-faint)' }}>
                        {analysis.coverage.excluded_moves.map((move) => (
                          <li key={`${move.pokemon}:${move.move}`}>{titleise(move.move)} — {move.reason}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {analysis.coverage.attacking_moves.length ? (
                  <div className="mt-3 table-scroll">
                    <table className="grid w-full min-w-[30rem] border-collapse text-xs">
                      <thead>
                        <tr style={{ color: 'var(--ink-faint)' }}>
                          <th scope="col" className="py-1 text-left font-medium">Against</th>
                          <th scope="col" className="py-1 text-left font-medium">Best</th>
                          <th scope="col" className="py-1 text-left font-medium">Move</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis.coverage.by_type.map((row) => (
                          <tr key={row.defense}>
                            <td className="py-1"><TypeChip type={row.defense} size="sm" /></td>
                            <td className="py-1"><Multiplier value={row.multiplier} /></td>
                            <td className="py-1" style={{ color: 'var(--ink-muted)' }}>
                              {row.moves.length ? `${titleise(row.moves[0]!.move)} (${titleise(row.moves[0]!.pokemon)})` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  ) : null}
                </Card>
              ) : null}
              <AssumptionList assumptions={envelope.assumptions} />
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}

export function TeamScreen() {
  const { game, playthrough } = useGameContext()
  const vocabulary = useEnvelope<Vocabulary>(useKey(game, 'vocabulary'), () => api.vocabulary(game))
  const naturesQuery = useEnvelope<Nature[]>(useKey(game, 'natures'), () => api.natures(game))
  const mechanics = vocabulary.state.kind === 'ready' ? vocabulary.state.data.mechanics : {}
  const natures = naturesQuery.state.kind === 'ready' ? naturesQuery.state.data : []

  if (!playthrough) {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="text-xl font-bold tracking-tight">Team · {titleise(game)}</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--ink-muted)' }}>
          A team belongs to a playthrough, so that switching games never overwrites another save.
        </p>
        <Link to="/playthroughs" className="mt-3 inline-block rounded border px-3 py-1.5 text-sm" style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}>
          Start a playthrough for {titleise(game)}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-bold tracking-tight">Team · {playthrough.name}</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Up to {MAX_TEAM} Pokémon, {MAX_MOVES} moves each. Saved in this browser only.
      </p>

      <div className="mt-4">
        <AddMember game={game} playthroughId={playthrough.id} disabled={playthrough.team.length >= MAX_TEAM} />
      </div>

      <div className="mt-4 grid gap-3">
        {playthrough.team.map((member) => (
          <MemberEditor key={member.id} member={member} game={game} playthroughId={playthrough.id} mechanics={mechanics} natures={natures} />
        ))}
      </div>

      {playthrough.team.length ? (
        <div className="mt-6">
          <h2 className="mb-3 text-lg font-semibold">Analysis</h2>
          <Analysis context={toContext(playthrough)} />
        </div>
      ) : null}
    </div>
  )
}
