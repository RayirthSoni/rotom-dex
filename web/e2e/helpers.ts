import { expect, type Page } from '@playwright/test'
import type { Playthrough } from '../src/state/schema'

/** Create a playthrough through the UI and land on its Journey screen. */
export async function startPlaythrough(page: Page, game: string, name: string) {
  await page.goto('/playthroughs')
  await page.getByLabel('Game').selectOption(game)
  await page.getByLabel('Name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Start' }).click()
  await expect(page).toHaveURL(new RegExp(`/g/${game}/journey`))
  await expect(page.getByRole('heading', { name: `Journey · ${name}` })).toBeVisible()
}

/**
 * Sprites are hotlinked from PokéAPI at runtime. The gates wait for the network to go idle, so they
 * abort those fetches: the run does not depend on GitHub, and the fallback backdrop is what axe sees.
 */
export async function blockSprites(page: Page) {
  await page.route('**/raw.githubusercontent.com/**', (route) => route.abort())
}

export async function tickMilestone(page: Page, label: string | RegExp) {
  await page.getByRole('checkbox', { name: label }).check()
}

/** The persisted document, unwrapped from zustand's `{ state, version }` envelope. */
export async function readStorage(page: Page): Promise<{
  version: number
  activeId: string | null
  playthroughs: Record<string, Playthrough>
}> {
  return page.evaluate(() => {
    const raw = localStorage.getItem('rotom-dex.playthroughs')
    if (!raw) return { version: 0, activeId: null, playthroughs: {} }
    return JSON.parse(raw).state
  })
}
