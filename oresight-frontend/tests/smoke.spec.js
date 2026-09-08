import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const BACKEND_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000';
const PROJECT_ROOT = path.dirname(fileURLToPath(import.meta.url)) + '/..';

const ROUTES = ['/', '/map', '/reports', '/simulator', '/field-intake', '/settings', '/site/1', '/site/2', '/site/3', '/login', '/nope'];
const REDIRECTS = [
  ['/timeline', '/reports'],
  ['/recommendations', '/reports'],
  ['/data-input', '/field-intake'],
];

async function fetchScenarioTypeEnum(request) {
  const openapi = await (await request.get(`${BACKEND_URL}/openapi.json`)).json();
  const scenarioType = openapi.components?.schemas?.SimulateRequest?.properties?.scenario_type;
  expect(scenarioType?.enum, 'Could not find SimulateRequest.scenario_type.enum in the live backend OpenAPI schema -- has the schema moved?').toBeTruthy();
  return scenarioType.enum;
}

// Fails loudly, before the rest of the suite runs, if the app isn't actually
// exercising the live backend contract these tests depend on. This is the
// exact failure mode that shipped once already: mock-by-default plus a
// CORS-blocked dev port meant "the app looks fine" while every real request
// silently failed or never happened.
test.describe('startup preflight', () => {
  test('VITE_USE_MOCK is not explicitly true in tracked env files', () => {
    for (const file of ['.env', '.env.local', '.env.example']) {
      const filePath = path.join(PROJECT_ROOT, file);
      if (!existsSync(filePath)) continue;
      const match = readFileSync(filePath, 'utf-8').match(/^VITE_USE_MOCK\s*=\s*(\S+)/m);
      if (match) {
        expect(match[1], `${file} sets VITE_USE_MOCK=${match[1]} -- mock is the offline/venue-wifi fallback, not the default. It should be false (or the line should be absent).`).not.toBe('true');
      }
    }
  });

  test('the backend is reachable directly', async ({ request }) => {
    let response;
    try {
      response = await request.get(`${BACKEND_URL}/sites`);
    } catch (err) {
      throw new Error(`Backend not reachable at ${BACKEND_URL} -- is docker compose up and the FastAPI app running? (${err.message})`);
    }
    expect(response.ok(), `GET ${BACKEND_URL}/sites returned ${response.status()}`).toBeTruthy();
  });

  test('the frontend origin is allowed by the backend CORS policy, and mock is actually off', async ({ page }) => {
    const backendRequests = [];
    const corsConsoleErrors = [];
    page.on('console', (msg) => { if (msg.type() === 'error' && msg.text().toLowerCase().includes('cors')) corsConsoleErrors.push(msg.text()); });
    page.on('requestfinished', async (req) => {
      if (req.url().startsWith(BACKEND_URL)) {
        const res = await req.response();
        backendRequests.push({ url: req.url(), status: res?.status() ?? null });
      }
    });

    await page.goto('/');
    await page.waitForTimeout(1500);

    expect(corsConsoleErrors, `Browser console reported CORS errors -- add this dev server's origin to oresight-backend/.env's CORS_ORIGINS:\n${corsConsoleErrors.join('\n')}`).toHaveLength(0);
    expect(backendRequests.length, 'Zero requests reached the backend on first paint. If CORS were the problem the console check above would have caught it -- this means VITE_USE_MOCK is true (mock mode never calls fetch at all).').toBeGreaterThan(0);

    const failed = backendRequests.filter((r) => !r.status || r.status >= 400);
    expect(failed, `Some backend requests failed:\n${JSON.stringify(failed, null, 2)}`).toHaveLength(0);
  });
});

test.describe('routing', () => {
  for (const route of ROUTES) {
    test(`${route} mounts without a page error`, async ({ page }) => {
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      await page.goto(route);
      await page.waitForTimeout(800);
      expect(errors, `Uncaught error(s) on ${route}:\n${errors.join('\n')}`).toHaveLength(0);
      const bodyText = await page.locator('body').innerText();
      expect(bodyText.length, `${route} rendered no visible content`).toBeGreaterThan(0);
    });
  }

  for (const [from, to] of REDIRECTS) {
    test(`${from} redirects to ${to}`, async ({ page }) => {
      await page.goto(from);
      await page.waitForTimeout(500);
      expect(new URL(page.url()).pathname).toBe(to);
    });
  }
});

test.describe('scenario simulator contract', () => {
  test('dropdown options exactly match the live backend scenario_type enum', async ({ page, request }) => {
    const backendEnum = await fetchScenarioTypeEnum(request);
    await page.goto('/simulator');
    const optionValues = await page.locator('select[data-testid="select-scenario"] option').evaluateAll((opts) => opts.map((o) => o.value));
    expect(new Set(optionValues), `Simulator options ${JSON.stringify(optionValues)} don't match the live backend's scenario_type enum ${JSON.stringify(backendEnum)} -- this is exactly the drift that once made every manual simulation run 422.`).toEqual(new Set(backendEnum));
  });

  test('runs successfully for every real scenario_type value', async ({ page, request }) => {
    const backendEnum = await fetchScenarioTypeEnum(request);
    for (const scenarioType of backendEnum) {
      await page.goto('/simulator');
      await page.selectOption('select[data-testid="select-scenario"]', scenarioType);
      await page.click('button[data-testid="button-run-simulation"]');
      await page.waitForTimeout(1500);
      const body = await page.locator('body').innerText();
      expect(body, `scenario_type=${scenarioType} did not complete:\n${body.slice(0, 400)}`).toContain('Complete');
    }
  });
});

test.describe('causal graph contract', () => {
  test('Nagpur (site 2) equipment-down demo path resolves the real neo4j graph, not the fallback', async ({ page }) => {
    let graphBody = null;
    page.on('response', async (res) => {
      if (/\/risk-events\/\d+\/causal-graph/.test(res.url())) graphBody = await res.json().catch(() => null);
    });

    await page.goto('/site/2?tab=graph');
    await page.waitForTimeout(2000);

    expect(graphBody, 'No /risk-events/{id}/causal-graph response was observed for the Nagpur site page').toBeTruthy();
    expect(graphBody.graph_source, `Expected the Nagpur equipment-down demo path to resolve a real Neo4j graph; got graph_source="${graphBody.graph_source}" instead. This is the exact bug pickPrimaryRisk() in api/client.js was written to fix (it used to just take risks[0]).`).toBe('neo4j');
  });
});
