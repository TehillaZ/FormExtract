import { defineConfig, devices } from '@playwright/test'
import { API_PORT, API_URL, UI_PORT } from './e2e/env'

// Browser tests run the real frontend against the real API, but on their own ports with an in-memory database
// and a scripted vision model (backend/e2e/server.py), so they never touch real data or spend API quota.
const python = process.platform === 'win32' ? String.raw`.venv\Scripts\python.exe` : '.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,          // one shared in-memory database: tests take turns
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${UI_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'he-IL',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `${python} -m uvicorn e2e.server:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `${API_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --port ${UI_PORT} --strictPort`,
      env: { API_PROXY_TARGET: API_URL },
      url: `http://localhost:${UI_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
