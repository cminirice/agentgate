import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests', timeout: 30_000, fullyParallel: false,
  webServer: [
    { command: 'python3 -m uvicorn agentgate.server.application:app --host 127.0.0.1 --port 8000', port: 8000, reuseExistingServer: true, env: { ...process.env, AGENTGATE_DB: '/tmp/agentgate-playwright.db', PYTHONPATH: '../src' } },
    { command: 'npm run dev -- --host 127.0.0.1', port: 5173, reuseExistingServer: true },
  ],
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})
