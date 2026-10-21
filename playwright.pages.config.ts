import { defineConfig } from '@playwright/test';

// The public production bundle must work without a local API or saved projects.
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'pages-site.spec.ts',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4182/AlephTav/',
    channel: process.env.ALEPHTAV_PLAYWRIGHT_CHANNEL,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4182',
    url: 'http://127.0.0.1:4182/AlephTav/',
    env: { VITE_PUBLIC_SITE: 'true' },
    reuseExistingServer: false,
  },
});
