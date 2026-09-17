import { expect, test } from '@playwright/test'
import { startPlaythrough } from './helpers'

test.describe('Preparation', () => {
  test('a reviewed boss produces a plan that never predicts an outcome', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/dex/marshtomp')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()
    await page.goto('/g/emerald/team')
    await page.getByLabel('Level').fill('16')
    await page.getByRole('button', { name: 'Water Gun', exact: true }).click()

    await page.goto('/g/emerald/journey')
    await page.getByRole('button', { name: /Leader Roxanne/ }).click()

    const plan = page.locator('section', { hasText: 'Leader Roxanne' }).last()
    await expect(plan.getByText('Preparation, not a prediction').first()).toBeVisible()
    await expect(plan.getByText('Their levels 12, 12, 15')).toBeVisible()
    await expect(plan.getByText('Nosepass')).toBeVisible()
    // Water Gun is 4x on Geodude (Rock/Ground).
    await expect(plan.getByText(/Your best type matchup:/).first()).toContainText('Water Gun')
    await expect(plan.getByText(/Supplies you can reach/)).toBeVisible()

    await plan.getByRole('button', { name: 'Pin plan' }).click()
    await expect(page.getByText('Pinned plans')).toBeVisible()
    await page.reload()
    await expect(page.getByText('Pinned plans')).toBeVisible()
  })

  test('closed-world flags are the only lever between blocked and undetermined', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/items')
    await page.getByPlaceholder('Item name…').fill('tm39')
    await page.getByRole('button', { name: /TM39/ }).first().click()

    const card = page.locator('section', { hasText: 'Where to get it in Emerald' })
    // Nothing vouched for yet, so the route is undetermined rather than blocked.
    await expect(card.locator('[data-verdict="unknown"]').first()).toBeVisible()

    await page.goto('/g/emerald/journey')
    await page.getByRole('checkbox', { name: 'My completed-milestone list is complete' }).check()
    await page.goto('/g/emerald/items')
    await page.getByPlaceholder('Item name…').fill('tm39')
    await page.getByRole('button', { name: /TM39/ }).first().click()
    await expect(card.locator('[data-verdict="locked"]').first()).toBeVisible()

    // Earn the badge and the same route becomes reachable.
    await page.goto('/g/emerald/journey')
    await page.getByRole('checkbox', { name: /Stone Badge/ }).check()
    await page.goto('/g/emerald/items')
    await page.getByPlaceholder('Item name…').fill('tm39')
    await page.getByRole('button', { name: /TM39/ }).first().click()
    await expect(card.locator('[data-verdict="reachable"]').first()).toBeVisible()
  })

  test('a game with no reviewed roster abstains usefully', async ({ page }) => {
    await startPlaythrough(page, 'red', 'Kanto run')
    await expect(page.getByText(/No milestones reviewed for Red yet/)).toBeVisible()
    await expect(page.getByText(/No boss rosters reviewed for Red yet/)).toBeVisible()
    await expect(page.getByText(/gap in the reviewed data/).first()).toBeVisible()
    await expect(page.locator('[data-state="error"]')).toHaveCount(0)
  })
})
