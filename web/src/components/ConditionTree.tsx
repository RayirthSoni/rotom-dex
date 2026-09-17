/**
 * Renders the typed prerequisite AST.
 *
 * A leaf shows a tri-state mark only when a service has actually evaluated it. Browsing the Dex
 * without a playthrough shows requirements plainly, with no verdict, because nothing has been
 * decided.
 */

import type { Condition, ConditionLeaf, Verdict } from '@/api/types'
import { isCombinator, phraseLeaf } from '@/domain/conditions'

type Mark = 'met' | 'unmet' | 'undetermined' | 'none'

function markFor(leaf: ConditionLeaf, verdict?: Verdict): Mark {
  if (!verdict) return 'none'
  const same = (other: ConditionLeaf) => other.op === leaf.op && String(other.value ?? '') === String(leaf.value ?? '')
  if (verdict.blocked_by.some(same)) return 'unmet'
  if (leaf.op === 'unknown' || verdict.unknown_because.some(same)) return 'undetermined'
  if (verdict.evaluation === true) return 'met'
  return 'none'
}

const MARK_GLYPH: Record<Mark, string> = { met: '✓', unmet: '✗', undetermined: '?', none: '' }
const MARK_COLOUR: Record<Mark, string> = {
  met: 'var(--known)',
  unmet: 'var(--blocked)',
  undetermined: 'var(--unknown)',
  none: 'transparent',
}
const MARK_TITLE: Record<Mark, string> = {
  met: 'Met by your recorded progress',
  unmet: 'Not met',
  undetermined: 'Not determined',
  none: '',
}

function Leaf({ leaf, verdict }: { leaf: ConditionLeaf; verdict?: Verdict }) {
  const phrase = phraseLeaf(leaf)
  const mark = markFor(leaf, verdict)
  const isUnknown = phrase.kind === 'unknown'
  return (
    <li className="flex items-start gap-2 py-0.5" data-condition-op={leaf.op}>
      {mark !== 'none' ? (
        <span aria-hidden="true" className="mt-px w-3 shrink-0 text-center text-xs font-bold" style={{ color: MARK_COLOUR[mark] }}>
          {MARK_GLYPH[mark]}
        </span>
      ) : (
        <span aria-hidden="true" className="mt-px w-3 shrink-0" />
      )}
      <span className="sr-only">{MARK_TITLE[mark]}</span>
      <span className={isUnknown ? 'text-xs italic' : 'text-sm'} style={{ color: isUnknown ? 'var(--ink-faint)' : 'var(--ink)' }}>
        {isUnknown ? <span className="not-italic font-medium">Not reviewed: </span> : null}
        {phrase.text}
      </span>
    </li>
  )
}

export function ConditionTree({
  condition,
  verdict,
  depth = 0,
}: {
  condition: Condition
  verdict?: Verdict
  depth?: number
}) {
  if (isCombinator(condition)) {
    const label = condition.op === 'and' ? 'All of' : 'Any of'
    return (
      <div className={depth > 0 ? 'mt-1' : ''}>
        <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-faint)' }}>
          {label}
        </p>
        <ul className="ml-2 border-l pl-3" style={{ borderColor: 'var(--line)' }}>
          {condition.args.map((arg, index) =>
            isCombinator(arg) ? (
              <li key={index}>
                <ConditionTree condition={arg} verdict={verdict} depth={depth + 1} />
              </li>
            ) : (
              <Leaf key={index} leaf={arg as ConditionLeaf} verdict={verdict} />
            ),
          )}
        </ul>
      </div>
    )
  }
  return (
    <ul>
      <Leaf leaf={condition as ConditionLeaf} verdict={verdict} />
    </ul>
  )
}
