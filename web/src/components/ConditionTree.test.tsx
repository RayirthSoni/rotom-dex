import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConditionTree } from './ConditionTree'
import type { Condition, Verdict } from '@/api/types'

const route: Condition = {
  op: 'and',
  args: [
    { op: 'milestone', value: 'stone-badge' },
    { op: 'unknown', reason: 'Progression gates have not been reviewed.' },
  ],
}

describe('the condition tree', () => {
  it('shows requirements with no verdict when nothing has been evaluated', () => {
    const { container } = render(<ConditionTree condition={route} />)
    expect(screen.getByText('After Stone Badge')).toBeInTheDocument()
    expect(screen.getByText('Progression gates have not been reviewed.')).toBeInTheDocument()
    // Browsing without a playthrough decides nothing, so no tick or cross may appear.
    expect(container.textContent).not.toMatch(/[✓✗]/)
    expect(screen.queryByText('Met by your recorded progress')).not.toBeInTheDocument()
  })

  it('marks only the leaves the service actually named', () => {
    const verdict: Verdict = {
      status: 'locked',
      evaluation: false,
      blocked_by: [{ op: 'milestone', value: 'stone-badge' }],
      unknown_because: [],
    }
    const { container } = render(<ConditionTree condition={route} verdict={verdict} />)
    expect(container.textContent).toContain('✗')
    expect(screen.getByText('Not met')).toBeInTheDocument()
  })

  it('marks an unresolved leaf as undetermined, not as failed', () => {
    const verdict: Verdict = {
      status: 'unknown',
      evaluation: null,
      blocked_by: [],
      unknown_because: [{ op: 'unknown', reason: 'Progression gates have not been reviewed.' }],
    }
    const { container } = render(<ConditionTree condition={route} verdict={verdict} />)
    expect(container.textContent).toContain('?')
    expect(container.textContent).not.toContain('✗')
    expect(screen.getByText('Not determined')).toBeInTheDocument()
  })

  it('labels the combinator so "all of" is never read as "any of"', () => {
    render(<ConditionTree condition={{ op: 'or', args: [{ op: 'has_pokemon', value: 'ralts' }, { op: 'has_pokemon', value: 'kirlia' }] }} />)
    expect(screen.getByText('Any of')).toBeInTheDocument()
  })

  it('renders an unrecognised operator rather than omitting it', () => {
    render(<ConditionTree condition={{ op: 'future_mechanic', value: 'something' }} />)
    expect(screen.getByText(/Future Mechanic/)).toBeInTheDocument()
  })
})
