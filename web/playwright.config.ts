import { defineConfig, devices } from '@playwright/test'
import os from 'os'
import path from 'path'

const testDatabase = path.join(os.tmpdir(), `agentgate-playwright-${process.pid}.db`)

export default defineConfig({
  testDir: './tests', timeout: 30_000, fullyParallel: false,
  webServer: [
    { command: 'python -m uvicorn agentgate.server.application:app --host 127.0.0.1 --port 18000', port: 18000, reuseExistingServer: false, env: { ...process.env, AGENTGATE_DB: testDatabase, PYTHONPATH: '../src' } },
    { command: 'npm run dev -- --host 127.0.0.1 --port 15173', port: 15173, reuseExistingServer: false, env: { ...process.env, AGENTGATE_API_TARGET: 'http://127.0.0.1:18000' } },
  ],
  use: { baseURL: 'http://127.0.0.1:15173', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
  ],
})
