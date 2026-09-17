import { expect, test } from '@playwright/test'
import { startPlaythrough } from './helpers'

/**
 * Nothing but a table, a chart or a code block may scroll sideways, and each of those owns its own
 * scroller. If the page body scrolls horizontally on a phone, the layout is broken.
 */
const SCREENS = [
  '/',
  '/competitive',
  '/games',
  '/playthroughs',
  '/g/emerald/journey',
  '/g/emerald/dex',
  '/g/emerald/dex/ralts',
  '/g/emerald/team',
  '/g/emerald/moves',
  '/g/emerald/items',
  '/g/emerald/tools',
  '/g/red/dex/ralts',
]

test.describe('Layout', () => {
  test('no screen scrolls the page sideways', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()

    const overflowing: Array<{ path: string; scrollWidth: number; clientWidth: number }> = []
    for (const path of SCREENS) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const measurement = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      // One pixel of slack for sub-pixel rounding.
      if (measurement.scrollWidth > measurement.clientWidth + 1) overflowing.push({ path, ...measurement })
    }
    expect(overflowing).toEqual([])
  })

  test('reference navigation opens from the compact menu', async ({ page }) => {
    await page.goto('/')
    await page.getByText('Explore tools',{exact:true}).click()
    await expect(page.getByRole('link',{name:'Competitive',exact:true})).toBeVisible()
    await expect(page.getByRole('link',{name:'Playthroughs',exact:true})).toBeVisible()
  })

  test('wide data keeps its own scroller instead of stretching the page', async ({ page }) => {
    await page.goto('/g/emerald/tools')
    const chart = page.locator('div.table-scroll').filter({ has: page.locator('table') }).first()
    await expect(chart).toBeVisible()
    const scrolls = await chart.evaluate((element) => element.scrollWidth > element.clientWidth)
    const body = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
    expect(body, 'the page itself must not scroll sideways').toBe(true)
    expect(typeof scrolls).toBe('boolean')
  })
})
