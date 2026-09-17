/** Searchable items, with per-game availability and the provenance of every price. */

import { useEffect, useState } from 'react'
import { api } from '@/api/endpoints'
import { useEnvelope } from '@/api/queries'
import { useKey } from '@/api/SnapshotProvider'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AssumptionList, EvidenceList } from '@/components/Provenance'
import { Card, Pill, SectionHeading, Stat, VerdictChip } from '@/components/primitives'
import { ConditionTree } from '@/components/ConditionTree'
import { useGameContext } from '@/state/useGame'
import { toContext } from '@/state/playthroughs'
import { VERDICT_LABEL, titleise } from '@/domain/conditions'
import type { ItemDetail, ItemListRow, ReachabilityResult, Vocabulary } from '@/api/types'
import { ItemSprite } from '@/components/Sprite'

const PAGE = 40

const PROVENANCE_NOTE: Record<string, string> = {
  'version-group': 'Price recorded for this version group.',
  'default-cost': "The source's generic cost, not a value verified for this game.",
  unknown: 'No price recorded.',
}

function ItemCard({ game, slug, onClose }: { game: string; slug: string; onClose: () => void }) {
  const { playthrough } = useGameContext()
  const context = playthrough ? toContext(playthrough) : null
  const detail = useEnvelope<ItemDetail>(useKey(game, 'item', slug), () => api.item(game, slug))
  const reach = useEnvelope<ReachabilityResult>(
    useKey(game, 'item-reach', slug, context ? JSON.stringify(context) : 'none'),
    () => (context ? api.reachability(context, [], [slug]) : Promise.resolve({ data: null } as never)),
    { enabled: Boolean(context), gcTime: 1000 * 60 * 10 },
  )
  const verdicts =
    reach.state.kind === 'ready' ? (reach.state.data.items[0]?.routes ?? []) : []

  return (
    <Card className="mt-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <ItemSprite slug={slug} size={40} />
          <SectionHeading>{titleise(slug)}</SectionHeading>
        </div>
        <button type="button" onClick={onClose} className="text-xs underline underline-offset-2" style={{ color: 'var(--ink-muted)' }}>
          Close
        </button>
      </div>
      <QueryBoundary state={detail.state} onRetry={() => detail.refetch()} skeletonRows={4} noClaimTitle={`${titleise(slug)} is not indexed for ${titleise(game)}`}>
        {(item, envelope) => (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Pill>{titleise(item.category)}</Pill>
              <Pill>{titleise(item.pocket)}</Pill>
              {item.holdable ? <Pill tone="accent">Holdable</Pill> : null}
              {item.machine ? (
                <Pill tone="accent">
                  {item.machine.kind.toUpperCase()}{item.machine.machine_number} · {item.machine.move_name}
                </Pill>
              ) : null}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat label="Buy" value={item.purchase_price ?? '—'} />
              <Stat label="Sell" value={item.sell_price ?? '—'} />
              <Stat label="Price source" value={<span title={PROVENANCE_NOTE[item.price_provenance]}>{titleise(item.price_provenance)}</span>} />
            </dl>
            <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>
              {PROVENANCE_NOTE[item.price_provenance]}
            </p>
            {item.effect?.short_effect ? <p className="mt-3 text-sm">{item.effect.short_effect}</p> : null}
            {item.flavor_text ? (
              <p className="mt-2 text-sm italic" style={{ color: 'var(--ink-muted)' }}>“{item.flavor_text}”</p>
            ) : null}

            <div className="mt-4">
              <SectionHeading hint={context ? undefined : 'Start a playthrough to have these checked against your progress.'}>
                Where to get it in {titleise(game)}
              </SectionHeading>
              {item.acquisition.length === 0 && item.shops.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--ink-muted)' }}>
                  No routes recorded. Item locations are largely absent from the pinned source; this is not a claim the item is
                  unobtainable here.
                </p>
              ) : (
                <ul className="space-y-2">
                  {item.acquisition.map((route) => {
                    const verdict = verdicts.find((entry) => entry.id === route.id)?.derived
                    return (
                      <li key={route.id} className="rounded border p-2.5" style={{ borderColor: 'var(--line)' }}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">{titleise(route.method)}</span>
                          {route.location ? <Pill>{route.location_name ?? titleise(route.location)}</Pill> : null}
                          {verdict ? <VerdictChip status={verdict.status} label={VERDICT_LABEL[verdict.status] ?? verdict.status} /> : null}
                        </div>
                        {route.note ? <p className="mt-1 text-xs" style={{ color: 'var(--ink-faint)' }}>{route.note}</p> : null}
                        <div className="mt-1.5"><ConditionTree condition={route.prerequisites} verdict={verdict} /></div>
                      </li>
                    )
                  })}
                  {item.shops.map((shop) => (
                    <li key={shop.id} className="rounded border p-2.5" style={{ borderColor: 'var(--line)' }}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium">{shop.name}</span>
                        {shop.location ? <Pill>{titleise(shop.location)}</Pill> : null}
                        {shop.price ? <span className="font-mono text-xs">₽{shop.price}</span> : null}
                      </div>
                      <div className="mt-1.5"><ConditionTree condition={shop.prerequisites} /></div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {item.held_by.length ? (
              <p className="mt-3 text-xs" style={{ color: 'var(--ink-faint)' }}>
                Held in the wild by {item.held_by.map((holder) => `${holder.name} (${holder.rarity}%)`).join(', ')}.
              </p>
            ) : null}
            <AssumptionList assumptions={envelope.assumptions} dense />
            <EvidenceList evidence={envelope.evidence} />
          </>
        )}
      </QueryBoundary>
    </Card>
  )
}

export function ItemsScreen() {
  const { game } = useGameContext()
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(term.trim()); setOffset(0) }, 220)
    return () => clearTimeout(timer)
  }, [term])

  const vocabulary = useEnvelope<Vocabulary>(useKey(game, 'vocabulary'), () => api.vocabulary(game))
  const list = useEnvelope<ItemListRow[]>(useKey(game, 'items', query, category, offset), () =>
    api.items(game, { q: query || undefined, category: category || undefined, limit: PAGE, offset }),
  )
  const pockets = vocabulary.state.kind === 'ready' ? vocabulary.state.data.item_pockets : []

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-extrabold tracking-tight">{titleise(game)} items</h1>
      <p className="mt-1 text-sm" style={{ color: 'var(--ink-muted)' }}>
        Items indexed for this generation, with effects and whatever the source records about price and availability.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <label className="flex-1 min-w-[12rem]">
          <span className="sr-only">Search items</span>
          <input type="search" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Item name…"
            className="field w-full" />
        </label>
        <label>
          <span className="sr-only">Filter by pocket</span>
          <select value={category} onChange={(event) => { setCategory(event.target.value); setOffset(0) }}
            className="field">
            <option value="">All pockets</option>
            {pockets.map((pocket) => (<option key={pocket} value={pocket}>{titleise(pocket)}</option>))}
          </select>
        </label>
      </div>

      {selected ? <ItemCard game={game} slug={selected} onClose={() => setSelected(null)} /> : null}

      <div className="mt-4">
        <QueryBoundary state={list.state} onRetry={() => list.refetch()} skeletonRows={8}
          noClaimTitle={`No item data for ${titleise(game)}`} emptyTitle="No items match">
          {(rows, envelope) => (
            <>
              <p className="text-xs" style={{ color: 'var(--ink-faint)' }}>
                {envelope.pagination ? `${rows.length} of ${envelope.pagination.total}` : `${rows.length} items`}
              </p>
              <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                {rows.map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => setSelected(item.slug)}
                      className="flex w-full items-center gap-2.5 rounded-[var(--r-card)] border px-2.5 py-1.5 text-left transition-colors hover:border-[var(--accent)]"
                      style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface-raised)' }}>
                      <ItemSprite slug={item.slug} size={30} />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.name}</span>
                      <span className="shrink-0 text-[11px]" style={{ color: 'var(--ink-faint)' }}>{titleise(item.pocket)}</span>
                      {item.purchase_price ? (
                        <span className="shrink-0 font-mono text-xs" title={PROVENANCE_NOTE[item.price_provenance]}>₽{item.purchase_price}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
              {envelope.pagination && envelope.pagination.total > PAGE ? (
                <div className="mt-4 flex items-center justify-between">
                  <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}
                    className="btn">Previous</button>
                  <button type="button" disabled={offset + PAGE >= envelope.pagination.total} onClick={() => setOffset(offset + PAGE)}
                    className="btn">Next</button>
                </div>
              ) : null}
              <AssumptionList assumptions={envelope.assumptions} dense />
            </>
          )}
        </QueryBoundary>
      </div>
    </div>
  )
}
