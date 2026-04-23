import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
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
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
