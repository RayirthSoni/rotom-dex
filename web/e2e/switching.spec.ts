import { expect, test } from '@playwright/test'
import { startPlaythrough, readStorage } from './helpers'

test.describe('Game switching', () => {
  test('missing data reads as not recorded, never as unobtainable', async ({ page }) => {
    await page.goto('/g/red/dex/ralts')
    await expect(page.locator('[data-state="no-claim"]')).toBeVisible()
    await expect(page.getByText(/does not by itself prove the Pok.mon is unobtainable/)).toBeVisible()
    // It must not be presented as an error.
    await expect(page.locator('[data-state="error"]')).toHaveCount(0)
  })

  test('switching games rescopes every query without touching another save', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ }).check()
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()
    await expect(page.getByRole('button', { name: 'On your team' })).toBeVisible()

    const before = await readStorage(page)

    // Browsing another game must not write to the active playthrough.
    await page.goto('/g/red/tools')
    await expect(page.getByText(/Your active playthrough is/)).toContainText('Hoenn run')
    await expect(page.getByRole('link', { name: /Start a playthrough for Red/ })).toBeVisible()

    const during = await readStorage(page)
    expect(during).toEqual(before)

    // A second playthrough for a second game leaves the first intact.
    await startPlaythrough(page, 'red', 'Kanto run')
    await page.goto('/g/emerald/team')
    await expect(page.getByRole('heading', { name: 'Team · Hoenn run' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Ralts' })).toBeVisible()

    const after = await readStorage(page)
    const hoenn = Object.values(after.playthroughs).find(p => p.name === 'Hoenn run')!
    expect(hoenn.team).toHaveLength(1)
    expect(hoenn.completedMilestones).toEqual(['littleroot-arrival'])
    expect(Object.keys(after.playthroughs)).toHaveLength(2)
  })

  test('mechanics absent from a game are explained, not silently omitted', async ({ page }) => {
    await startPlaythrough(page, 'red', 'Kanto run')
    await page.goto('/g/red/dex/pikachu')
    await page.getByRole('button', { name: 'Add to Kanto run' }).click()
    await page.goto('/g/red/team')

    await expect(page.getByTestId('no-abilities')).toContainText('Red has no Abilities')
    await expect(page.getByTestId('no-natures')).toContainText('Red has no Natures')
    await expect(page.getByTestId('no-held-items')).toContainText('Red has no held items')
    // Generation I keeps a single Special stat.
    await page.goto('/g/red/dex/pikachu')
    await expect(page.getByText('Special', { exact: true })).toBeVisible()
    await expect(page.getByText('5 stats in this generation')).toBeVisible()
  })
})
