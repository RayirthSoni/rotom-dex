/**
 * Phrasing for the typed condition AST.
 *
 * One entry per operator in `rotom_dex/domain/conditions.py`. An operator this build does not know
 * still renders, verbatim — omitting an unrecognised prerequisite would make a route look easier
 * than it is, which is the one mistake this product must not make.
 *
 * `unknown` reasons are never paraphrased: they are the project's own abstention text.
 */

import type { Condition, ConditionLeaf } from '@/api/types'

export type Phrase = { text: string; value?: string; kind: 'requirement' | 'unknown' | 'always' }

const TITLE_EXCEPTIONS: Record<string, string> = { tm: 'TM', hm: 'HM', tr: 'TR', pp: 'PP', hp: 'HP' }

export function titleise(slug: string | number | undefined | null): string {
  if (slug === undefined || slug === null) return ''
  return String(slug)
    .split(/[-_]/)
    .map((part) => TITLE_EXCEPTIONS[part] ?? part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

const LEAF_PHRASES: Record<string, (value: string) => string> = {
  always: () => 'No prerequisite recorded',
  trade: () => 'Must be traded',
  overworld_rain: () => 'While it is raining in the overworld',
  device_upside_down: () => 'With the console held upside down',
  level_at_least: (v) => `At least level ${v}`,
  happiness_at_least: (v) => `Friendship at least ${v}`,
  beauty_at_least: (v) => `Beauty at least ${v}`,
  affection_at_least: (v) => `Affection at least ${v}`,
  has_pokemon: (v) => `You have ${titleise(v)}`,
  has_item: (v) => `You have ${titleise(v)}`,
  use_item: (v) => `Use ${titleise(v)} on it`,
  held_item: (v) => `Holding ${titleise(v)}`,
  knows_move: (v) => `Knows ${titleise(v)}`,
  knows_move_type: (v) => `Knows a ${titleise(v)}-type move`,
  party_has_pokemon: (v) => `${titleise(v)} is in your party`,
  party_has_type: (v) => `A ${titleise(v)}-type is in your party`,
  trade_for_pokemon: (v) => `Trade for ${titleise(v)}`,
  at_location: (v) => `At ${titleise(v)}`,
  in_region: (v) => `In ${titleise(v)}`,
  milestone: (v) => `After ${titleise(v)}`,
  encounter_condition: (v) => `Encounter condition: ${titleise(v)}`,
  encounter_pokemon: (v) => `After encountering ${titleise(v)}`,
  time_of_day: (v) => `During ${v}`,
  gender: (v) => `${titleise(v)} only`,
  stat_relation: (v) => `Attack and Defense: ${v}`,
}

export function phraseLeaf(leaf: ConditionLeaf): Phrase {
  if (leaf.op === 'unknown') {
    return { text: leaf.reason ?? 'Not determined.', kind: 'unknown' }
  }
  if (leaf.op === 'always') return { text: LEAF_PHRASES.always!(''), kind: 'always' }
  const render = LEAF_PHRASES[leaf.op]
  const value = leaf.value === undefined ? '' : String(leaf.value)
  if (!render) {
    // Unknown to this build, but real to the server. Show it plainly rather than hide it.
    return { text: `${titleise(leaf.op)}${value ? `: ${titleise(value)}` : ''}`, value, kind: 'requirement' }
  }
  return { text: render(value), value, kind: leaf.op === 'always' ? 'always' : 'requirement' }
}

export function isCombinator(condition: Condition): condition is { op: 'and' | 'or'; args: Condition[] } {
  return (condition.op === 'and' || condition.op === 'or') && Array.isArray((condition as { args?: unknown }).args)
}

export function isTrivial(condition: Condition | null | undefined): boolean {
  return !condition || condition.op === 'always'
}

/** Flat list of every leaf, for summaries and counts. */
export function flattenLeaves(condition: Condition): ConditionLeaf[] {
  if (isCombinator(condition)) return condition.args.flatMap(flattenLeaves)
  return [condition as ConditionLeaf]
}

export function countUnknown(condition: Condition | null | undefined): number {
  if (!condition) return 0
  return flattenLeaves(condition).filter((leaf) => leaf.op === 'unknown').length
}

export const VERDICT_LABEL: Record<string, string> = {
  reachable: 'Reachable',
  locked: 'Blocked',
  unknown: 'Not determined',
  'not-applicable': 'Not in this game',
}

export const VERDICT_EXPLANATION: Record<string, string> = {
  reachable: 'Every prerequisite you have vouched for is met.',
  locked: 'Something you have recorded as complete is missing a prerequisite.',
  unknown: 'Rotom cannot tell from what has been reviewed and what you have recorded. This is not a claim that it is unobtainable.',
  'not-applicable': 'This rule cannot fire in this game.',
}
