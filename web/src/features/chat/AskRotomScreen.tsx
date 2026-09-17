/**
 * Ask Rotom.
 *
 * The transcript lives here and is deliberately *not* part of the saved playthrough: chat history
 * supplements the profile, it is never the authoritative record of progress. Everything the answer
 * proposes is a button; nothing is applied until the player presses it, and the server never writes.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/endpoints'
import { ApiError } from '../../api/client'
import type { ChatAction, ChatAnswer, ChatCard, ChatStatus, ChatTurn, Envelope } from '../../api/types'
import { Card, Label, Pill, SectionHeading, VerdictChip } from '../../components/primitives'
import { AssumptionList, EvidenceList } from '../../components/Provenance'
import { ErrorState } from '../../components/states'
import { toContext, usePlaythroughs } from '../../state/playthroughs'
import { useGameContext } from '../../state/useGame'

interface Exchange {
  id: string
  question: string
  answer?: ChatAnswer
  envelope?: Envelope<ChatAnswer | null>
  error?: ApiError
}

const REASON_LABEL: Record<string, string> = {
  missing_data: 'no reviewed data',
  unrecorded_progress: 'progress not recorded',
  untracked_mechanic: 'mechanic not tracked',
  open_world: 'nothing vouched for',
  spoiler_filter: 'spoiler preference',
  unreviewed_web: 'unreviewed web source',
}

function AnswerCard({ card }: { card: ChatCard }) {
  return (
    <Card>
      <SectionHeading hint={card.kind}>{card.title}</SectionHeading>
      <dl className="mt-2 grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-1 text-sm">
        {card.rows.map((row, index) => (
          <div key={index} className="contents">
            <dt className="text-muted">{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function Actions({ actions, onApply }: { actions: ChatAction[]; onApply: (action: ChatAction) => string | null }) {
  const [done, setDone] = useState<Record<number, string>>({})
  if (actions.length === 0) return null
  return (
    <div className="mt-3">
      <Label>Suggested actions</Label>
      <p className="text-xs text-muted">Nothing changes until you choose it. Rotom never edits your save.</p>
      <ul className="mt-2 flex flex-col gap-2">
        {actions.map((action, index) => (
          <li key={index} className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn"
              disabled={Boolean(done[index])}
              onClick={() => setDone((d) => ({ ...d, [index]: onApply(action) ?? 'Applied' }))}
              data-testid="chat-action"
            >
              {action.label || action.kind}
            </button>
            {done[index] ? <span className="text-xs text-muted">{done[index]}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Answer({ exchange, onApply }: { exchange: Exchange; onApply: (action: ChatAction) => string | null }) {
  if (exchange.error) return <ErrorState error={exchange.error} />
  const answer = exchange.answer
  if (!answer) return null
  return (
    <div data-testid="chat-answer" data-abstained={answer.abstained ? 'true' : 'false'}>
      <p className="whitespace-pre-wrap">{answer.prose}</p>

      {answer.recommendations.length > 0 && (
        <div className="mt-3">
          <Label>Recommendations</Label>
          <ul className="mt-1 flex flex-col gap-2">
            {answer.recommendations.map((rec, index) => (
              <li key={index} className="flex flex-wrap items-baseline gap-2 text-sm" data-testid="chat-recommendation">
                <VerdictChip status={rec.status} label={rec.status} title={`Checked against your recorded progress: ${rec.status}`} />
                <span>{rec.text}</span>
                <span className="text-xs text-muted">{rec.rationale}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.cards.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          {answer.cards.map((card, index) => (
            <AnswerCard key={index} card={card} />
          ))}
        </div>
      )}

      {answer.facts.length > 0 && (
        <div className="mt-3">
          <Label>Facts, with evidence</Label>
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {answer.facts.map((fact, index) => (
              <li key={index} data-testid="chat-fact">
                {fact.claim} <span className="text-xs text-muted">({fact.tool})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.assumptions.length > 0 && (
        <div className="mt-3">
          <Label>Assumptions</Label>
          <ul className="mt-1 flex flex-col gap-1 text-sm text-muted">
            {answer.assumptions.map((assumption, index) => (
              <li key={index}>
                <Pill>{REASON_LABEL[assumption.because] ?? assumption.because}</Pill> {assumption.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.references.some((r) => r.kind === 'web') && (
        <div className="mt-3" data-testid="chat-web-sources">
          <Label>Researched on the web — not reviewed</Label>
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {answer.references
              .filter((r) => r.kind === 'web')
              .map((ref) => (
                <li key={ref.id}>
                  <a href={ref.url} target="_blank" rel="noreferrer noopener">
                    {ref.title || ref.url}
                  </a>{' '}
                  <span className="text-xs text-muted">unreviewed; may not describe this exact game</span>
                </li>
              ))}
          </ul>
        </div>
      )}

      <Actions actions={answer.actions} onApply={onApply} />

      {exchange.envelope ? (
        <div className="mt-3">
          <AssumptionList assumptions={exchange.envelope.assumptions} dense />
          <EvidenceList evidence={exchange.envelope.evidence} />
        </div>
      ) : null}

      {answer.limits_reached.length > 0 && (
        <p className="mt-2 text-xs text-muted">Rotom stopped early: it reached {answer.limits_reached.join('; ')}.</p>
      )}
    </div>
  )
}

export function AskRotomScreen() {
  const { game, playthrough } = useGameContext()
  const store = usePlaythroughs()
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [statusError, setStatusError] = useState<ApiError | null>(null)
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    api
      .chatStatus()
      .then((s) => !cancelled && setStatus(s))
      .catch((e) => !cancelled && setStatusError(e instanceof ApiError ? e : new ApiError('server', 0, String(e))))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [exchanges.length])

  function applyAction(action: ChatAction): string | null {
    if (!playthrough) return 'No playthrough selected'
    const payload = action.payload as Record<string, string | number>
    switch (action.kind) {
      case 'pin_plan':
        store.pinPlan(playthrough.id, { kind: 'boss', battle: String(payload.battle ?? ''), label: action.label, note: '' })
        return 'Pinned'
      case 'add_team_member':
        store.addMember(playthrough.id, String(payload.pokemon ?? ''))
        return 'Added to team'
      case 'mark_milestone':
        store.toggleMilestone(playthrough.id, String(payload.milestone ?? ''))
        return 'Progress updated'
      case 'set_current_location':
        store.update(playthrough.id, { currentLocation: String(payload.location ?? '') })
        return 'Location updated'
      default:
        return 'Not supported yet'
    }
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault()
    const question = message.trim()
    if (!question || !playthrough || pending) return
    const id = `${Date.now()}`
    setExchanges((list) => [...list, { id, question }])
    setMessage('')
    setPending(true)
    const history: ChatTurn[] = exchanges.flatMap((e) =>
      e.answer ? [{ role: 'user' as const, text: e.question }, { role: 'assistant' as const, text: e.answer.prose }] : [],
    )
    try {
      const envelope = await api.chat(toContext(playthrough), question, history.slice(-10))
      setExchanges((list) => list.map((e) => (e.id === id ? { ...e, envelope, answer: envelope.data ?? undefined } : e)))
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError('server', 0, String(error))
      setExchanges((list) => list.map((e) => (e.id === id ? { ...e, error: apiError } : e)))
    } finally {
      setPending(false)
    }
  }

  if (!playthrough) {
    return (
      <Card>
        <SectionHeading>Ask Rotom</SectionHeading>
        <p className="mt-2 text-sm">
          Rotom answers about the game you are playing, so start a playthrough for <strong>{game}</strong> first. The Dex, Moves and
          Items screens work without one.
        </p>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1>Ask Rotom</h1>
        <p className="text-sm text-muted">
          Answers use your game, team, progress and spoiler preference. Facts carry evidence; advice is checked against what your
          progress actually settles.
        </p>
      </div>

      {statusError ? <ErrorState error={statusError} /> : null}
      {status && !status.enabled ? (
        <Card>
          <div data-testid="chat-unavailable" role="status">
            <SectionHeading hint="not configured">Rotom is not available</SectionHeading>
            <p className="mt-2 text-sm">{status.reason}</p>
          </div>
        </Card>
      ) : null}

      <ol className="flex flex-col gap-4">
        {exchanges.map((exchange) => (
          <li key={exchange.id}>
            <Card>
              <p className="font-medium" data-testid="chat-question">
                {exchange.question}
              </p>
              <div className="mt-2 border-t pt-2">
                {exchange.answer || exchange.error ? (
                  <Answer exchange={exchange} onApply={applyAction} />
                ) : (
                  <p className="text-sm text-muted" aria-busy="true">
                    Rotom is checking the database…
                  </p>
                )}
              </div>
            </Card>
          </li>
        ))}
      </ol>
      <div ref={endRef} />

      <form onSubmit={ask} className="flex flex-col gap-2">
        <label htmlFor="rotom-question" className="sr-only">
          Ask Rotom a question about {game}
        </label>
        <textarea
          id="rotom-question"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={status?.limits.max_message_chars ?? 2000}
          rows={2}
          placeholder="Who can I catch before the next gym?"
          disabled={status ? !status.enabled : false}
          data-testid="chat-input"
        />
        <div className="flex items-center gap-2">
          <button type="submit" className="btn" disabled={pending || !message.trim() || (status ? !status.enabled : false)} data-testid="chat-send">
            {pending ? 'Asking…' : 'Ask'}
          </button>
          <span className="text-xs text-muted">Spoiler level: {playthrough.spoilerLevel}</span>
        </div>
      </form>
    </div>
  )
}
