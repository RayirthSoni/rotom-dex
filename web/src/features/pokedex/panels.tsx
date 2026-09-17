/** The panels of a Pokémon card: stats, abilities, evolution, learnset, acquisition. */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import type {
  AcquisitionData, AcquisitionRoute, EvolutionChain, LearnsetData, LearnsetMove, PokemonCard, Verdict,
} from '@/api/types'
import { ConditionTree } from '@/components/ConditionTree'
import { Card, CoverageChip, Multiplier, Pill, SectionHeading, Stat, TypeChip, VerdictChip } from '@/components/primitives'
import { VERDICT_EXPLANATION, VERDICT_LABEL, titleise } from '@/domain/conditions'

const STAT_LABEL: Record<string, string> = {
  hp: 'HP',
  attack: 'Attack',
  defense: 'Defense',
  'special-attack': 'Sp. Atk',
  'special-defense': 'Sp. Def',
  special: 'Special',
  speed: 'Speed',
}

export function StatsPanel({ card }: { card: PokemonCard }) {
  const total = card.stats.reduce((sum, stat) => sum + stat.base_stat, 0)
  const single = card.stats.some((stat) => stat.stat === 'special')
  return (
    <Card>
      <SectionHeading hint={single ? 'This generation uses a single Special stat rather than separate Sp. Atk and Sp. Def.' : undefined}>
        Base stats
      </SectionHeading>
      <ul className="space-y-1.5">
        {card.stats.map((stat) => (
          <li key={stat.stat} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs" style={{ color: 'var(--ink-muted)' }}>
              {STAT_LABEL[stat.stat] ?? titleise(stat.stat)}
            </span>
            <span className="w-8 shrink-0 text-right font-mono text-sm">{stat.base_stat}</span>
            <span className="h-2 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--surface-sunken)' }}>
              <span
                className="block h-full rounded-full"
                style={{ width: `${Math.min(100, (stat.base_stat / 180) * 100)}%`, backgroundColor: 'var(--accent)' }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
        Total {total} · {card.stats.length} stats in this generation
      </p>
    </Card>
  )
}

export function AbilitiesPanel({ card }: { card: PokemonCard }) {
  return (
    <Card>
      <SectionHeading>Abilities</SectionHeading>
      {card.abilities_note ? (
        <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
          {card.abilities_note}
        </p>
      ) : card.abilities.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
          No ability slots recorded for this form in this generation.
        </p>
      ) : (
        <ul className="space-y-1">
          {card.abilities.map((ability) => (
            <li key={ability.slot} className="flex items-center gap-2 text-sm">
              <span className="font-medium">{ability.name}</span>
              {ability.is_hidden ? <Pill>Hidden</Pill> : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function IdentityPanel({ card, game }: { card: PokemonCard; game: string }) {
  const national = card.dex_numbers.find((entry) => entry.pokedex === 'national')
  return (
    <Card>
      <SectionHeading>Identity</SectionHeading>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="National" value={national ? `#${String(national.number).padStart(3, '0')}` : '—'} />
        <Stat label="Species" value={card.form.species_name} />
        <Stat label="Height" value={card.form.height_dm ? `${(card.form.height_dm / 10).toFixed(1)} m` : '—'} />
        <Stat label="Weight" value={card.form.weight_hg ? `${(card.form.weight_hg / 10).toFixed(1)} kg` : '—'} />
        <Stat label="Capture rate" value={card.species.capture_rate ?? '—'} />
        <Stat label="Growth" value={card.species.growth_rate ? titleise(card.species.growth_rate) : '—'} />
        <Stat label="Egg groups" value={card.egg_groups.length ? card.egg_groups.map(titleise).join(', ') : '—'} />
        <Stat
          label="Held in the wild"
          value={
            card.held_items.length
              ? card.held_items.map((item) => `${item.name} (${item.rarity}%)`).join(', ')
              : 'None recorded'
          }
        />
      </dl>
      {card.other_forms.length ? (
        <p className="mt-3 text-xs" style={{ color: 'var(--ink-faint)' }}>
          Other forms:{' '}
          {card.other_forms.map((form, index) => (
            <span key={form.id}>
              {index > 0 ? ', ' : ''}
              {form.presence ? (
                <Link to={`/g/${game}/dex/${form.slug}`} className="underline underline-offset-2">
                  {form.name}
                </Link>
              ) : (
                <span title="Not in this game's data">{form.name}</span>
              )}
            </span>
          ))}
        </p>
      ) : null}
    </Card>
  )
}

export function EvolutionPanel({ chain, game }: { chain: EvolutionChain; game: string }) {
  if (!chain.nodes.length) {
    return (
      <Card>
        <SectionHeading>Evolution</SectionHeading>
        <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
          No evolution chain is recorded for this Pokémon.
        </p>
      </Card>
    )
  }
  return (
    <Card>
      <SectionHeading hint="Rules that cannot fire in this game are kept and labelled, so a family member missing here is explained rather than hidden.">
        Evolution family
      </SectionHeading>
      <ul className="flex flex-wrap gap-2">
        {chain.nodes.map((node) => (
          <li key={node.form_id}>
            {node.presence ? (
              <Link
                to={`/g/${game}/dex/${node.slug}`}
                className="inline-flex items-center gap-1.5 rounded border px-2 py-1 text-sm"
                style={{ borderColor: 'var(--line-strong)' }}
              >
                {node.name}
                {node.types.map((t) => (
                  <TypeChip key={t} type={t} size="sm" />
                ))}
              </Link>
            ) : (
              <span
                className="inline-flex items-center gap-1.5 rounded border border-dashed px-2 py-1 text-sm"
                style={{ borderColor: 'var(--line)', color: 'var(--ink-faint)' }}
                title="Not present in this game's data. That is not a claim it is unobtainable."
              >
                {node.name} <span className="text-[10px] uppercase">not in this game</span>
              </span>
            )}
          </li>
        ))}
      </ul>
      <ul className="mt-3 space-y-3">
        {chain.edges.map((edge) => (
          <li key={edge.id} className="rounded border p-2.5" style={{ borderColor: 'var(--line)' }}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">
                {titleise(edge.from_pokemon)} → {titleise(edge.to_pokemon)}
              </span>
              <Pill>{titleise(edge.trigger)}</Pill>
              {edge.applicability === 'not-applicable' ? (
                <VerdictChip status="not-applicable" label="Not in this game" title={edge.reason ?? undefined} />
              ) : edge.applicability === 'unknown' ? (
                <VerdictChip status="unknown" label="Applicability unknown" title={edge.reason ?? undefined} />
              ) : null}
            </div>
            {edge.reason ? (
              <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
                {edge.reason}
              </p>
            ) : null}
            <div className="mt-1.5">
              <ConditionTree condition={edge.conditions} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RouteRow({ route }: { route: AcquisitionRoute }) {
  const verdict: Verdict | undefined = route.derived
  const levels = route.min_level
    ? route.max_level && route.max_level !== route.min_level
      ? `L${route.min_level}–${route.max_level}`
      : `L${route.min_level}`
    : null
  return (
    <li className="rounded border p-2.5" style={{ borderColor: 'var(--line)' }} data-testid="acquisition-route">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{titleise(route.method)}</span>
        {route.location ? <Pill>{route.location_name ?? titleise(route.location)}</Pill> : null}
        {route.location_area ? (
          <span className="text-xs" style={{ color: 'var(--ink-faint)' }}>
            {route.location_area_name ?? titleise(route.location_area)}
          </span>
        ) : null}
        {levels ? <span className="font-mono text-xs">{levels}</span> : null}
        {route.chance_percent ? <span className="font-mono text-xs">{route.chance_percent}%</span> : null}
        {verdict ? (
          <VerdictChip status={verdict.status} label={VERDICT_LABEL[verdict.status] ?? verdict.status} title={VERDICT_EXPLANATION[verdict.status]} />
        ) : null}
      </div>
      {route.note ? (
        <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
          {route.note}
        </p>
      ) : null}
      <div className="mt-1.5">
        <ConditionTree condition={route.prerequisites} verdict={verdict} />
      </div>
      {route.encounter_conditions ? (
        <div className="mt-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
            Encounter conditions
          </p>
          <ConditionTree condition={route.encounter_conditions} />
        </div>
      ) : null}
    </li>
  )
}

export function AcquisitionPanel({ data, playthroughActive }: { data: AcquisitionData; playthroughActive: boolean }) {
  const [method, setMethod] = useState('')
  const methods = Object.keys(data.route_counts)
  const routes = method ? data.routes.filter((route) => route.method === method) : data.routes
  return (
    <Card>
      <SectionHeading
        hint={
          playthroughActive
            ? 'Verdicts are derived from your recorded progress. Anything you have not vouched for stays undetermined.'
            : 'Start a playthrough to have these prerequisites checked against your progress.'
        }
      >
        How to obtain · {data.routes.length} routes
      </SectionHeading>
      {methods.length > 1 ? (
        <div className="mb-3 flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setMethod('')}
            className="rounded-full border px-2 py-0.5 text-xs"
            style={{ borderColor: method === '' ? 'var(--accent)' : 'var(--line)', color: method === '' ? 'var(--accent)' : 'var(--ink-muted)' }}
          >
            All {data.routes.length}
          </button>
          {methods.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setMethod(name)}
              className="rounded-full border px-2 py-0.5 text-xs"
              style={{ borderColor: method === name ? 'var(--accent)' : 'var(--line)', color: method === name ? 'var(--accent)' : 'var(--ink-muted)' }}
            >
              {titleise(name)} {data.route_counts[name]}
            </button>
          ))}
        </div>
      ) : null}
      <ul className="space-y-2">
        {routes.slice(0, 40).map((route) => (
          <RouteRow key={route.id} route={route} />
        ))}
      </ul>
      {routes.length > 40 ? (
        <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
          Showing the first 40 of {routes.length} routes.
        </p>
      ) : null}
    </Card>
  )
}

const ACCESS_LABEL: Record<string, string> = {
  reachable: 'Available',
  locked: 'Not yet',
  unknown: 'Access unknown',
  'not-applicable': 'Not in this game',
}

export function LearnsetPanel({ data }: { data: LearnsetData }) {
  const methods = Object.keys(data.method_counts)
  const [method, setMethod] = useState(methods.includes('level-up') ? 'level-up' : (methods[0] ?? ''))
  const moves = data.moves.filter((move) => move.method === method)
  const annotated = moves.some((move) => move.access)
  return (
    <Card>
      <SectionHeading hint="A row means this Pokémon can learn the move here. Whether you can reach the machine, tutor or breeding partner is a separate question, shown on the right.">
        Moves it can learn
      </SectionHeading>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {methods.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setMethod(name)}
            className="rounded-full border px-2 py-0.5 text-xs"
            style={{ borderColor: method === name ? 'var(--accent)' : 'var(--line)', color: method === name ? 'var(--accent)' : 'var(--ink-muted)' }}
          >
            {titleise(name)} {data.method_counts[name]}
          </button>
        ))}
      </div>
      <div className="table-scroll">
        <table className="grid w-full min-w-[34rem] border-collapse text-sm">
          <thead>
            <tr style={{ color: 'var(--ink-faint)' }}>
              {method === 'level-up' ? (
                <th scope="col" className="w-12 py-1 text-left text-xs font-medium">
                  Lv
                </th>
              ) : null}
              <th scope="col" className="py-1 text-left text-xs font-medium">
                Move
              </th>
              <th scope="col" className="py-1 text-left text-xs font-medium">
                Type
              </th>
              <th scope="col" className="py-1 text-right text-xs font-medium">
                Pow
              </th>
              <th scope="col" className="py-1 text-right text-xs font-medium">
                Acc
              </th>
              {annotated ? (
                <th scope="col" className="py-1 text-right text-xs font-medium">
                  Access
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {moves.map((move: LearnsetMove) => (
              <tr key={`${move.method}:${move.move}:${move.level}`}>
                {method === 'level-up' ? <td className="py-1 font-mono text-xs">{move.level || '—'}</td> : null}
                <td className="py-1">
                  {move.move_name}
                  {move.machine_item ? (
                    <span className="ml-1.5 text-[11px] uppercase" style={{ color: 'var(--ink-faint)' }}>
                      {move.machine_kind}
                      {move.machine_number}
                    </span>
                  ) : null}
                </td>
                <td className="py-1">
                  <TypeChip type={move.type} size="sm" />
                </td>
                <td className="py-1 text-right font-mono text-xs">{move.power ?? '—'}</td>
                <td className="py-1 text-right font-mono text-xs">{move.accuracy ?? '—'}</td>
                {annotated ? (
                  <td className="py-1 text-right">
                    {move.access ? (
                      <VerdictChip status={move.access.status} label={ACCESS_LABEL[move.access.status] ?? move.access.status} title={move.access.reason} />
                    ) : null}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.machine_rules.tm_reusable === 0 ? (
        <p className="mt-2 text-xs" style={{ color: 'var(--ink-faint)' }}>
          TMs are consumed when used in this game, so one copy teaches one Pokémon.
        </p>
      ) : null}
    </Card>
  )
}

export function TypeHeader({ card, coverageStatus }: { card: PokemonCard; coverageStatus: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <h1 className="text-xl font-bold tracking-tight">{card.form.name}</h1>
      {card.types.map((entry) => (
        <TypeChip key={entry.slot} type={entry.type} />
      ))}
      <CoverageChip status={coverageStatus as 'complete'} />
      {card.presence.presence === 'unknown' ? <Pill>Presence unverified</Pill> : null}
    </div>
  )
}

export function MultiplierRow({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5" style={{ backgroundColor: 'var(--surface-sunken)' }}>
      <TypeChip type={label} size="sm" />
      <Multiplier value={value} />
    </span>
  )
}
