import { defineConfig } from '@playwright/test';

// Authored browser fixtures only: no corpus bootstrap, API, model, or network source.
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: ['greek-study.spec.ts', 'arrangement-sources.spec.ts', 'comparison-rows.spec.ts', 'briefing-sources.spec.ts', 'loading-feedback.spec.ts'],
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4181', trace: 'retain-on-failure',
    channel: process.env.ALEPHTAV_PLAYWRIGHT_CHANNEL,
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4181',
    url: 'http://127.0.0.1:4181',
    reuseExistingServer: !process.env.CI,
  },
});
