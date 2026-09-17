import { expect, test } from '@playwright/test'
import { startPlaythrough } from './helpers'

test.describe('Backend unavailable', () => {
  test('an unreachable API is reported without losing saved work', async ({ page, context }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ }).check()

    await context.route('**/api/**', (route) => route.abort('failed'))
    await context.route('**/health', (route) => route.abort('failed'))
    await page.reload()

    await expect(page.getByTestId('backend-banner')).toContainText('Rotom is disconnected')
    await expect(page.locator('[data-error-kind="offline"]').first()).toBeVisible()
    // Local work is untouched by the outage.
    await expect(page.getByText('1 milestones ticked')).toBeVisible()

    await context.unroute('**/api/**')
    await context.unroute('**/health')
    await page.reload()
    await expect(page.getByTestId('backend-banner')).toHaveCount(0)
    await expect(page.getByText('Progress checklist')).toBeVisible()
  })

  test('a missing database explains how to build one', async ({ page, context }) => {
    await context.route('**/health', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Database not found' }) }),
    )
    await context.route('**/api/**', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Database not found' }) }),
    )
    await page.goto('/g/emerald/dex')
    await expect(page.getByTestId('backend-banner')).toContainText('rotom import')
    await expect(page.locator('[data-error-kind="database_missing"]').first()).toBeVisible()
  })
})
