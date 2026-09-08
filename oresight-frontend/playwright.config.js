import { defineConfig } from '@playwright/test';

// The backend (Postgres/Neo4j/FastAPI on :8000) is NOT started by this
// config -- these are live-contract smoke tests, not unit tests against a
// mock. Start `docker compose up` + the FastAPI app yourself before running
// `npm run test:smoke`; tests fail fast with a clear message if it's down.
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
    env: {
      // These tests assert the app runs live against the real backend, not
      // mock fixtures -- see tests/smoke.spec.js's preflight check, which
      // fails loudly if this is wrong.
      VITE_USE_MOCK: 'false',
      VITE_API_BASE_URL: 'http://localhost:8000',
    },
  },
});
