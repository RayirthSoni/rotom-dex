import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { startPlaythrough } from './helpers'

/**
 * Accessibility is checked on every screen, in both the desktop and phone projects, because the
 * layout differs between them and so do the failures. Only serious and critical violations fail the
 * build: the lower severities are advisory and would make this a noise generator.
 */
const SCREENS = [
  { path: '/', name: 'chat home' },
  { path: '/competitive', name: 'competitive workshop' },
  { path: '/games', name: 'game selector' },
  { path: '/playthroughs', name: 'playthroughs' },
  { path: '/g/emerald/journey', name: 'journey' },
  { path: '/g/emerald/dex', name: 'dex search' },
  { path: '/g/emerald/dex/ralts', name: 'pokemon detail' },
  { path: '/g/emerald/team', name: 'team' },
  { path: '/g/emerald/ask', name: 'ask rotom' },
  { path: '/g/emerald/moves', name: 'moves' },
  { path: '/g/emerald/items', name: 'items' },
  { path: '/g/emerald/tools', name: 'tools' },
]

test.describe('Accessibility', () => {
  for (const path of ['/', '/competitive']) {
    test(`light theme has no serious accessibility violations at ${path}`,async({page})=>{
      await page.goto(path)
      await page.getByRole('button',{name:'Toggle light or dark theme'}).click()
      await page.waitForLoadState('networkidle')
      const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze()
      expect(results.violations.filter(v=>v.impact==='serious'||v.impact==='critical')).toEqual([])
    })
  }
  for (const screen of SCREENS) {
    test(`${screen.name} has no serious accessibility violations`, async ({ page }) => {
      await startPlaythrough(page, 'emerald', 'Hoenn run')
      await page.goto(screen.path)
      await page.waitForLoadState('networkidle')

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()

      const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
      // Name the offending elements: a count alone tells you nothing about what to fix.
      const described = serious.map((v) => {
        const nodes = v.nodes
          .slice(0, 4)
          .map((n) => `      ${n.target.join(' ')} — ${n.failureSummary?.replace(/\s+/g, ' ').slice(0, 180)}`)
          .join('\n')
        return `${v.id} (${v.impact}) on ${v.nodes.length} node(s): ${v.help}\n${nodes}`
      })
      expect(described, `${screen.name}:\n${described.join('\n')}`).toEqual([])
    })
  }
})
