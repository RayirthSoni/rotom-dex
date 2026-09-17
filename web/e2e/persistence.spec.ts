import { expect, test } from '@playwright/test'
import { startPlaythrough, readStorage } from './helpers'

test.describe('Persistence', () => {
  test('state survives a reload', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ }).check()
    await page.reload()
    await expect(page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ })).toBeChecked()
    await expect(page.getByText('1 milestones ticked')).toBeVisible()
  })

  test('export and import round-trips', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.getByRole('checkbox', { name: /Arrive in Littleroot Town/ }).check()
    await page.goto('/g/emerald/dex/ralts')
    await page.getByRole('button', { name: 'Add to Hoenn run' }).click()

    await page.goto('/playthroughs')
    const download = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /Export 1 playthrough/ }).click(),
    ]).then(([event]) => event)
    const path = await download.path()
    expect(path).toBeTruthy()

    const before = await readStorage(page)

    // Clear everything, then restore from the file.
    await page.evaluate(() => localStorage.clear())
    await page.reload()
    await expect(page.getByText('None yet.')).toBeVisible()

    await page.getByTestId('import-input').setInputFiles(path!)
    await expect(page.getByTestId('import-notice')).toContainText('Imported 1 new')
    const after = await readStorage(page)
    expect(after.playthroughs).toEqual(before.playthroughs)
  })

  test('a malformed file is refused with a field path and changes nothing', async ({ page }) => {
    await startPlaythrough(page, 'emerald', 'Hoenn run')
    await page.goto('/playthroughs')
    const before = await readStorage(page)

    await page.getByTestId('import-input').setInputFiles({
      name: 'broken.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{ "schema": "rotom-dex/playthroughs", "version": 1, "exportedAt": "x", "playthroughs": [{ "id": "a" }] }'),
    })
    const problems = page.getByTestId('import-problems')
    await expect(problems).toBeVisible()
    await expect(problems).toContainText('Nothing was imported')
    await expect(problems).toContainText('playthroughs.0.name')

    expect(await readStorage(page)).toEqual(before)
  })

  test('a file from a newer build is refused rather than coerced', async ({ page }) => {
    await page.goto('/playthroughs')
    await page.getByTestId('import-input').setInputFiles({
      name: 'future.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{ "schema": "rotom-dex/playthroughs", "version": 99, "exportedAt": "x", "playthroughs": [] }'),
    })
    await expect(page.getByTestId('import-problems')).toContainText('written by a newer version')
  })

  test('a file that is not an export at all is refused', async ({ page }) => {
    await page.goto('/playthroughs')
    await page.getByTestId('import-input').setInputFiles({
      name: 'other.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"some":"other tool"}'),
    })
    await expect(page.getByTestId('import-problems')).toContainText('Expected a Rotom Dex export')
  })
})
