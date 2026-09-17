import { expect, test } from '@playwright/test'
import { readStorage, startPlaythrough } from './helpers'

const STATUS_ON = {
  enabled: true,
  provider: 'scripted',
  model: 'scripted',
  research_enabled: false,
  reason: '',
  limits: { max_message_chars: 2000, max_history_turns: 12, max_tool_calls: 8, deadline_s: 45 },
}

function envelope(answer: Record<string, unknown>) {
  return {
    game: { id: 9, slug: 'emerald', name: 'Emerald', version_group: 'emerald', generation: 3, support_tier: 'validated' },
    snapshot_id: 'test',
    coverage_status: 'partial',
    coverage: [],
    assumptions: ['Facts are derived from the pinned source snapshot and reviewed packs.'],
    evidence: [{ id: 'abc123', sources: [{ source_id: 'pack:emerald', kind: 'game-pack', url: 'local:pack', review_status: 'reference-reviewed' }] }],
    data: {
      prose: 'Zigzagoon is catchable on the routes you have already opened.',
      abstained: false,
      facts: [{ claim: 'Zigzagoon is a Normal-type in Emerald', evidence_id: 'abc123', tool: 'dex_lookup' }],
      assumptions: [{ text: 'Milestones you have not ticked are treated as unknown.', because: 'open_world' }],
      recommendations: [
        { text: 'Catch a Zigzagoon on Route 102', rationale: 'Pickup is useful early', status: 'reachable', subject: 'zigzagoon' },
        { text: 'Catch a Tentacool', rationale: 'Water coverage', status: 'locked', subject: 'tentacool' },
      ],
      cards: [{ kind: 'pokemon', title: 'Zigzagoon', subject: 'zigzagoon', tool: 'dex_lookup', rows: [{ label: 'Types', value: 'normal' }] }],
      actions: [{ kind: 'add_team_member', label: 'Add Zigzagoon to your team', payload: { pokemon: 'zigzagoon' }, applied: false }],
      references: [{ kind: 'evidence', id: 'abc123', review_status: 'reference-reviewed' }],
      tools_used: [{ tool: 'check_reachability', arguments: {} }],
      spoiler_level: 'hint',
      limits_reached: [],
      verification_notes: [],
      ...answer,
    },
  }
}

test.describe('Ask Rotom', () => {
  test('without a configured provider the tab explains itself and everything else still works', async ({ page }) => {
    // No credential exists in this environment, so this is the real server behaviour, not a mock.
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('link', { name: 'Ask' }).first().click()
    await expect(page.getByTestId('chat-unavailable')).toContainText('not available')
    await expect(page.getByTestId('chat-send')).toBeDisabled()

    // The promise that matters: the rest of the application does not depend on the model.
    await page.goto('/g/emerald/dex')
    await page.getByLabel('Search by name or number').fill('ralts')
    await expect(page.getByRole('link', { name: /Ralts/ }).first()).toBeVisible()
    await page.goto('/g/emerald/team')
    await expect(page.getByRole('heading', { name: /Team/ })).toBeVisible()
    await page.goto('/g/emerald/journey')
    await expect(page.getByText('Progress checklist')).toBeVisible()
  })

  test('an answer shows evidence, checked advice and actions that do nothing until chosen', async ({ page, context }) => {
    await context.route('**/api/chat/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATUS_ON) }))
    await context.route('**/api/chat', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(envelope({})) }))

    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('link', { name: 'Ask' }).first().click()
    await page.getByTestId('chat-input').fill('Who can I catch right now?')
    await page.getByTestId('chat-send').click()

    await expect(page.getByTestId('chat-answer')).toContainText('Zigzagoon is catchable')
    await expect(page.getByTestId('chat-fact')).toContainText('Normal-type')
    // Advice carries the verdict the server checked, not the model's opinion.
    const verdicts = page.getByTestId('chat-recommendation')
    await expect(verdicts.first()).toContainText('reachable')
    await expect(verdicts.nth(1)).toContainText('locked')
    // Evidence is behind a disclosure, the same one every other screen uses.
    await page.getByRole('group').filter({ hasText: /Evidence:/ }).getByText(/Evidence:/).click()
    await expect(page.getByText('local:pack')).toBeVisible()

    // The action has not been applied yet.
    const before = await readStorage(page)
    expect(Object.values(before.playthroughs)[0].team).toHaveLength(0)

    await page.getByTestId('chat-action').click()
    const after = await readStorage(page)
    expect(Object.values(after.playthroughs)[0].team).toHaveLength(1)
    expect(Object.values(after.playthroughs)[0].team[0].pokemon).toBe('zigzagoon')
  })

  test('an abstention is shown as an answer, not as an error', async ({ page, context }) => {
    await context.route('**/api/chat/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATUS_ON) }))
    await context.route('**/api/chat', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          envelope({
            prose: 'No boss rosters have been reviewed for this game, so no preparation can be offered.',
            abstained: true,
            facts: [],
            recommendations: [],
            cards: [],
            actions: [],
          }),
        ),
      }),
    )
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('link', { name: 'Ask' }).first().click()
    await page.getByTestId('chat-input').fill('How do I beat the eighth gym?')
    await page.getByTestId('chat-send').click()

    await expect(page.getByTestId('chat-answer')).toHaveAttribute('data-abstained', 'true')
    await expect(page.getByTestId('chat-answer')).toContainText('no preparation can be offered')
    await expect(page.locator('[data-error-kind]')).toHaveCount(0)
  })

  test('a provider outage mid-session is reported and the saved work survives', async ({ page, context }) => {
    await context.route('**/api/chat/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATUS_ON) }))
    await context.route('**/api/chat', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'The chat provider is unavailable.' }) }),
    )
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ }).check()
    await page.getByRole('link', { name: 'Ask' }).first().click()
    await page.getByTestId('chat-input').fill('anything')
    await page.getByTestId('chat-send').click()

    await expect(page.locator('[data-error-kind]').first()).toBeVisible()
    await page.getByRole('link', { name: 'Journey' }).first().click()
    await expect(page.getByText('1 milestones ticked')).toBeVisible()
  })
})
