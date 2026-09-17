import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end against the real stack: a real SQLite snapshot, the real FastAPI server, and the built
 * bundle served from the same origin — the production arrangement, not a mocked one.
 *
 * The database is the two-game build (Emerald and Red), which imports in about two seconds and is
 * deliberately the pair that exercises the honesty paths: Emerald has the only reviewed progression
 * and boss roster, Red has neither, and no Abilities, Natures, held items or breeding.
 */
const PORT = 8111
const BASE_URL = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
  ],
  webServer: {
    command: 'npm run e2e:server',
    url: `${BASE_URL}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
