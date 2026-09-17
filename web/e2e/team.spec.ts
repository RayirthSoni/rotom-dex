import { expect, test } from '@playwright/test'
import { startPlaythrough } from './helpers'

test.describe('Team editing', () => {
  test('a team is built and analysed from its actual moves', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()
    await page.goto('/g/emerald/team')

    await page.getByLabel('Level').fill('14')
    // The picker only offers moves this Pokemon can learn in this game.
    await page.getByRole('button', { name: 'Confusion', exact: true }).click()
    await expect(page.getByText('Moves (1/4)')).toBeVisible()

    await expect(page.getByRole('heading', { name: 'Defensive profile' })).toBeVisible()
    const defence = page.locator('section', { hasText: 'Defensive profile' })
    await expect(defence.getByText('Weak to')).toBeVisible()

    const offence = page.locator('section', { hasText: 'Offensive coverage' })
    await expect(offence.getByText('Super effective against')).toBeVisible()
    // Confusion is Psychic: 2x on Fighting and Poison, 0x on Dark.
    await expect(offence.getByText('No move affects')).toBeVisible()
    await expect(offence.getByRole('cell', { name: 'Confusion (Ralts)' }).first()).toBeVisible()
  })

  test('the team is capped and each member is capped at four moves', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()
    await page.goto('/g/emerald/team')

    for (const move of ['Growl', 'Confusion', 'Double Team', 'Teleport']) {
      await page.getByRole('button', { name: move, exact: true }).click()
    }
    await expect(page.getByText('Moves (4/4)')).toBeVisible()
    // A fifth is refused rather than silently replacing one.
    await expect(page.getByRole('button', { name: 'Calm Mind', exact: true }).first()).toBeDisabled()
  })

  test('status moves are listed but excluded from coverage', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()
    await page.goto('/g/emerald/team')
    await page.getByRole('button', { name: 'Growl', exact: true }).click()

    const offence = page.locator('section', { hasText: 'Offensive coverage' })
    await expect(offence.getByText('Not counted')).toBeVisible()
    await expect(offence.getByText(/Growl — Status moves deal no damage/)).toBeVisible()
  })
})
