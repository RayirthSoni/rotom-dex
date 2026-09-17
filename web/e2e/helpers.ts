import { expect, type Page } from '@playwright/test'

/** Create a playthrough through the UI and land on its Journey screen. */
export async function startPlaythrough(page: Page, game: string, name: string) {
  await page.goto('/playthroughs')
  await page.getByLabel('Game').selectOption(game)
  await page.getByLabel('Name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Start' }).click()
  await expect(page).toHaveURL(new RegExp(`/g/${game}/journey`))
  await expect(page.getByRole('heading', { name: `Journey · ${name}` })).toBeVisible()
}

export async function tickMilestone(page: Page, label: string | RegExp) {
  await page.getByRole('checkbox', { name: label }).check()
}

/** The persisted document, unwrapped from zustand's `{ state, version }` envelope. */
export async function readStorage(page: Page): Promise<{
  version: number
  activeId: string | null
  playthroughs: Record<string, any>
}> {
  return page.evaluate(() => {
    const raw = localStorage.getItem('rotom-dex.playthroughs')
    if (!raw) return { version: 0, activeId: null, playthroughs: {} }
    return JSON.parse(raw).state
  })
}
