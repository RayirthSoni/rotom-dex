import { expect, test } from '@playwright/test'

test.describe('Lookup', () => {
  test('a game is chosen by its exact version', async ({ page }) => {
    await page.goto('/games')
    await expect(page.getByRole('heading', { name: 'Choose a game' })).toBeVisible()

    const emerald = page.getByRole('button', { name: /^Emerald/ })
    await expect(emerald).toContainText('Generation 3')
    await expect(page.getByRole('link',{name:'View detailed data coverage'})).toBeVisible()

    await emerald.click()
    await expect(page).toHaveURL(/\/g\/emerald\//)
  })

  test('a Pokemon shows stats, abilities, evolution, learnset and acquisition', async ({ page }) => {
    await page.goto('/g/emerald/dex')
    await page.getByPlaceholder('Name or National number…').fill('ralts')
    await page.getByRole('link', { name: /Ralts/ }).first().click()

    await expect(page.getByRole('heading', { name: 'Ralts' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Base stats' })).toBeVisible()
    await expect(page.getByText('Total 198')).toBeVisible()
    await expect(page.getByText('Synchronize')).toBeVisible()

    // The family keeps members this game does not have, and says why.
    await expect(page.getByRole('heading', { name: 'Evolution family' })).toBeVisible()
    await expect(page.getByText('Gallade', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('not in this game').first()).toBeVisible()

    await expect(page.getByRole('heading', { name: 'Moves it can learn' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Tutor \d+/ })).toBeVisible()

    await expect(page.getByText(/How to obtain · \d+ routes/)).toBeVisible()
    // An unreviewed gate is shown verbatim, never summarised away.
    await expect(page.getByText(/Not reviewed:/).first()).toBeVisible()
  })

  test('eligibility is reported separately from access to the method', async ({ page }) => {
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: /^Tutor \d+/ }).click()
    const accessCells = page.locator('[data-verdict]')
    await expect(accessCells.first()).toBeVisible()
    // The source has no tutor locations at all, so access must be unknown, never denied.
    await expect(page.getByText('Access unknown').first()).toBeVisible()
  })

  test('the type chart is the one for the game generation', async ({ page }) => {
    await page.goto('/g/red/tools')
    await expect(page.getByText('Generation 1 · 15 types')).toBeVisible()
    await expect(page.getByTitle('Ghost against Psychic: no effect')).toBeVisible()
    await expect(page.getByText('Natures are absent as a mechanic in red.')).toBeVisible()
  })
})
