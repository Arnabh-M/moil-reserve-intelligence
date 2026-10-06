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
    const optionValues = await page.locator('select[data-testid="select-condition-type-0"] option').evaluateAll((opts) => opts.map((o) => o.value));
    expect(new Set(optionValues), `Simulator options ${JSON.stringify(optionValues)} don't match the live backend's scenario_type enum ${JSON.stringify(backendEnum)} -- this is exactly the drift that once made every manual simulation run 422.`).toEqual(new Set(backendEnum));
  });

  test('runs successfully for every real scenario_type value', async ({ page, request }) => {
    const backendEnum = await fetchScenarioTypeEnum(request);
    for (const scenarioType of backendEnum) {
      await page.goto('/simulator');
      await page.selectOption('select[data-testid="select-condition-type-0"]', scenarioType);
      await page.click('button[data-testid="button-run-simulation"]');
      await page.waitForTimeout(1500);
      const body = await page.locator('body').innerText();
      expect(body, `scenario_type=${scenarioType} did not complete:\n${body.slice(0, 400)}`).toContain('Simulation results');
    }
  });
});

// Task 6: the Equipment tab on Site Intelligence, backed by
// GET /equipment/metrics. These pin the things that are easy to break
// silently -- tab order, the deliberately-blank utilisation column, keyboard
// operability, and the window toggle actually re-fetching rather than
// re-sorting stale data.
test.describe('equipment performance panel', () => {
  // Opens the tab and waits for the live metrics table, so no test below
  // races the fetch. Returns the first row's machine id.
  async function openEquipmentTab(page, site = 1) {
    await page.goto(`/site/${site}?tab=equipment`);
    await page.waitForSelector('[data-testid="table-equipment-metrics"] tbody tr', { timeout: 15000 });
    await page.waitForTimeout(300);
  }

  test('Equipment tab sits between Production and Reserve', async ({ page }) => {
    await page.goto('/site/1');
    await page.waitForSelector('.tabs .tab');
    const tabs = await page.locator('.tabs .tab').allInnerTexts();
    expect(tabs, `Site tab order drifted: ${JSON.stringify(tabs)}`).toEqual(['Overview', 'Production', 'Equipment', 'Reserve', 'Recommendations', 'Graph']);

    // ?tab=equipment must actually resolve to the panel, not fall through to
    // an empty tab body the way an unregistered tab value would.
    await openEquipmentTab(page);
    await expect(page.locator('[data-testid="tab-site-equipment"]')).toHaveClass(/active/);
  });

  test('utilisation column renders an em dash for every row, never a number', async ({ page }) => {
    await openEquipmentTab(page);
    const cells = await page.locator('[data-testid^="utilisation-"]').allInnerTexts();
    expect(cells.length, 'No utilisation cells found -- did the column get renamed or dropped?').toBeGreaterThan(0);
    for (const cell of cells) {
      // The backend has no hour-meter data, so utilisation_pct is null by
      // contract. A number here means someone started deriving it.
      expect(cell.trim(), `Utilisation rendered "${cell}" -- it must always be "—". utilisation_pct is null by contract (no hour-meter data exists); showing a number would be invented data.`).toBe('—');
      expect(cell, `Utilisation cell "${cell}" contains a digit`).not.toMatch(/\d/);
    }
    // The explanation has to be reachable, not just blank.
    await expect(page.locator('[data-testid^="utilisation-"]').first()).toHaveAttribute('title', /hour-meter/i);
  });

  test('column headers sort by keyboard alone, and report aria-sort', async ({ page }) => {
    await openEquipmentTab(page);
    const namesBefore = await page.locator('[data-testid^="button-equipment-detail-"]').allInnerTexts();

    // Focus the header without clicking it -- sorting must not be mouse-only.
    await page.focus('[data-testid="sort-name"]');
    expect(await page.evaluate(() => document.activeElement?.getAttribute('data-testid')), 'The Equipment column header did not take keyboard focus -- it must be a real <button>, not a click handler on <th>.').toBe('sort-name');

    await page.keyboard.press('Enter');
    await expect(page.locator('th', { has: page.locator('[data-testid="sort-name"]') })).toHaveAttribute('aria-sort', 'ascending');
    const namesAsc = await page.locator('[data-testid^="button-equipment-detail-"]').allInnerTexts();
    expect(namesAsc, 'Rows did not reorder after an Enter press on the Equipment header').toEqual([...namesBefore].sort((a, b) => a.localeCompare(b)));

    await page.keyboard.press('Enter');
    await expect(page.locator('th', { has: page.locator('[data-testid="sort-name"]') })).toHaveAttribute('aria-sort', 'descending');
    const namesDesc = await page.locator('[data-testid^="button-equipment-detail-"]').allInnerTexts();
    expect(namesDesc, 'Second Enter press did not flip the sort direction').toEqual([...namesAsc].reverse());
  });

  test('machine detail drawer opens, exposes a dialog, and returns focus on Escape', async ({ page }) => {
    await openEquipmentTab(page);
    const trigger = page.locator('[data-testid^="button-equipment-detail-"]').first();
    const triggerId = await trigger.getAttribute('data-testid');

    await trigger.click();
    const drawer = page.locator('[data-testid="panel-equipment-metrics-detail"]');
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveAttribute('role', 'dialog');
    await expect(drawer).toHaveAttribute('aria-modal', 'true');

    // Focus must move into the drawer, or a keyboard user is stranded behind it.
    expect(await page.evaluate(() => document.activeElement?.getAttribute('data-testid')), 'Opening the drawer left focus outside it').toBe('button-close-equipment-detail');

    await page.waitForSelector('[data-testid="chart-equipment-weekly"]', { timeout: 10000 });

    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    expect(await page.evaluate(() => document.activeElement?.getAttribute('data-testid')), 'Closing the drawer dropped focus (to <body>) instead of returning it to the row that opened it.').toBe(triggerId);
  });

  test('window toggle re-fetches: 90d and 30d disagree in the table and the drawer', async ({ page }) => {
    await openEquipmentTab(page);

    // Pick a machine that actually has downtime history, otherwise every
    // window looks identical and this test would pass vacuously.
    const rowWithHistory = page.locator('[data-testid="table-equipment-metrics"] tbody tr').filter({ hasNot: page.locator('td:nth-child(8):text-is("0")') }).first();
    const machineId = (await rowWithHistory.locator('[data-testid^="button-equipment-detail-"]').getAttribute('data-testid')).replace('button-equipment-detail-', '');

    const caption90 = await page.locator('[data-testid="text-equipment-metrics-caption"]').innerText();
    const downtime90 = await rowWithHistory.locator('td').nth(7).innerText();

    await page.click(`[data-testid="button-equipment-detail-${machineId}"]`);
    await page.waitForSelector('[data-testid="chart-equipment-weekly"]');
    const events90 = await page.locator('[data-testid="panel-equipment-metrics-detail"] .eq-history-item').count();
    const bars90 = await page.locator('[data-testid="chart-equipment-weekly"] .recharts-bar-rectangle').count();
    await page.keyboard.press('Escape');

    await page.click('[data-testid="button-eqmetrics-window-30"]');
    await page.waitForTimeout(1200);

    const caption30 = await page.locator('[data-testid="text-equipment-metrics-caption"]').innerText();
    expect(caption30, `The window caption did not change when switching to 30d -- the toggle is re-rendering stale data instead of re-fetching.\n90d: ${caption90}\n30d: ${caption30}`).not.toBe(caption90);
    expect(caption30, `30d window should report 744 h (31 inclusive days); got: ${caption30}`).toContain('744');

    const downtime30 = await page.locator(`[data-testid="button-equipment-detail-${machineId}"]`).locator('xpath=ancestor::tr').locator('td').nth(7).innerText();
    expect(Number(downtime30.replace(/,/g, '')), `A 30-day window must report no more downtime than the 90-day window for the same machine (90d=${downtime90}, 30d=${downtime30}).`).toBeLessThanOrEqual(Number(downtime90.replace(/,/g, '')));

    await page.click(`[data-testid="button-equipment-detail-${machineId}"]`);
    await page.waitForSelector('[data-testid="chart-equipment-weekly"]');
    const bars30 = await page.locator('[data-testid="chart-equipment-weekly"] .recharts-bar-rectangle').count();
    const events30 = await page.locator('[data-testid="panel-equipment-metrics-detail"] .eq-history-item').count();

    expect(bars30, `The drawer's weekly chart showed ${bars30} bars for a 30-day window vs ${bars90} for 90 days -- it must re-fetch with the panel's window, not keep the old series.`).toBeLessThan(bars90);
    expect(events30, `The drawer's event list did not shrink with the window (90d=${events90}, 30d=${events30}).`).toBeLessThanOrEqual(events90);
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

  // The test above only covers the Site Intelligence graph tab. The Map zone
  // panel (ZoneDetailPanel) used to choose a site's risk event with its own
  // logic and landed on Drill NAG-1's postgres_fallback for Nagpur. It now
  // delegates to api.getSitePrimaryRisk, the same helper getSiteWorkspace
  // uses. ZoneDetailPanel has no URL/state hook to open it without a WebGL
  // canvas click, so drive its exact resolution path (zone-level id first,
  // then getSitePrimaryRisk) against the live backend instead. Relies on the
  // Vite dev server (playwright.config.js webServer) serving /src.
  test('Map zone panel resolves a Nagpur reserve zone to the neo4j graph, not the fallback', async ({ page }) => {
    await page.goto('/map');
    const resolved = await page.evaluate(async () => {
      const { api } = await import('/src/api/client.js');
      const zones = (await api.getReserveZones(2)).features || [];
      const zone = zones.find((z) => Number(z.properties?.site_id) === 2) || zones[0];
      const directId = zone?.properties?.risk_event_id || zone?.properties?.risk_id;
      const eventId = directId || (await api.getSitePrimaryRisk(2))?.id || null;
      const graph = eventId ? await api.getCausalGraph(eventId) : null;
      return { hasZone: Boolean(zone), eventId, graphSource: graph?.graph_source ?? null };
    });

    expect(resolved.hasZone, 'GET /reserve-zones?site_id=2 returned no zones to exercise the panel path against').toBe(true);
    expect(resolved.eventId, 'The Nagpur zone panel resolution path produced no risk event id').toBeTruthy();
    expect(resolved.graphSource, `A Nagpur reserve zone must resolve to the HT-302 neo4j causal graph; got graph_source="${resolved.graphSource}" for risk ${resolved.eventId}. "postgres_fallback" means the Map zone panel has drifted back to picking Drill NAG-1 instead of sharing getSitePrimaryRisk with the site page.`).toBe('neo4j');
  });
});
