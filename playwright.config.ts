import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  // The public-site spec needs the production bundle; it runs under playwright.pages.config.ts.
  testIgnore: 'pages-site.spec.ts',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: "sh -c 'PY=python; [ -x .venv/bin/python ] && PY=.venv/bin/python; \"$PY\" scripts/bootstrap_fixture_repo.py && \"$PY\" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8765'",
      url: 'http://127.0.0.1:8765/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      url: 'http://127.0.0.1:4173',
      // Proxy to the API started above, not the default dev API on 43174.
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8765' },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
