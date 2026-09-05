/**
 * Route-mount smoke test.
 *
 * ─────────────────────────────────────────────────────────────────────
 * REQUIRES THE BACKEND RUNNING ON http://localhost:8000 FIRST:
 *
 *     cd oresight-backend
 *     ./venv/Scripts/python -m uvicorn app.main:app --port 8000
 *
 * Then, from oresight-frontend/:
 *
 *     npm run test:smoke
 * ─────────────────────────────────────────────────────────────────────
 *
 * Mounts every route declared in src/App.jsx in a real browser against the
 * live API and fails the build if any of them:
 *
 *   - throws an uncaught error (the class of bug that white-screened
 *     /reports twice, both times from a merge conflict no build step could
 *     catch — a page that crashes on render still compiles fine);
 *   - logs a console error;
 *   - renders the literal text "undefined" or "NaN";
 *   - trips the ErrorBoundary;
 *   - falls back to bundled sample data (which would otherwise let this
 *     whole suite pass green with the backend switched off).
 *
 * Routes are parsed out of App.jsx rather than listed here, so a new
 * <Route> is covered the moment it is added.
 *
 * The test serves the app on port 5173 specifically: the backend's default
 * CORS_ORIGINS allows that origin, and an origin it does not allow makes
 * every request fail and silently drops the app onto mock data. Note that
 * CORS_ORIGINS is about the FRONTEND's origin and is independent of whichever
 * port the backend itself binds to.
 *
 * The build runs with no VITE_API_URL, so the app under test uses client.js's
 * compiled default origin. Set SMOKE_API_URL to point both the health check
 * and the build at a different backend.
 */

import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { chromium } from 'playwright';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

// Unset by default on purpose. The build below then gets no VITE_API_URL and
// falls through to client.js's own compiled default, so this suite actually
// exercises the shipped default origin. Injecting the URL unconditionally
// would make the suite pass even if that default had drifted to another port.
const API_URL_OVERRIDE = process.env.SMOKE_API_URL || null;
const API_URL = API_URL_OVERRIDE || 'http://localhost:8000';
const PORT = Number(process.env.SMOKE_PORT || 5173);
const ORIGIN = `http://localhost:${PORT}`;

// Stand-in values for dynamic segments, so ":id" routes get mounted too.
const ROUTE_PARAM_SAMPLES = { id: 'balaghat' };

// Text the client shows when a live call failed and it served bundled
// sample data instead (see announceMockFallback in src/api/client.js).
const MOCK_FALLBACK_MARKER = /Live API unreachable/i;

// Every wait is bounded so one misbehaving page cannot hang the suite.
const NAV_TIMEOUT_MS = 20_000;
const IDLE_TIMEOUT_MS = 8_000;
const SETTLE_MS = 2_000;

function log(msg) {
  process.stdout.write(`${msg}\n`);
}

function run(args, opts = {}) {
  return spawn(process.execPath, [resolve(ROOT, 'node_modules/vite/bin/vite.js'), ...args], {
    cwd: ROOT,
    stdio: 'pipe',
    ...opts,
  });
}

/** Every `path` in an App.jsx <Route>, with params filled in. */
function routesFromApp() {
  const src = readFileSync(resolve(ROOT, 'src/App.jsx'), 'utf8');
  const paths = [...src.matchAll(/<Route\s[^>]*path="([^"]+)"/g)].map((m) => m[1]);
  if (paths.length === 0) {
    throw new Error('No <Route path="..."> found in src/App.jsx — has the router changed shape?');
  }
  return [...new Set(paths)].map((p) =>
    p.replace(/:(\w+)/g, (_, name) => {
      const sample = ROUTE_PARAM_SAMPLES[name];
      if (!sample) throw new Error(`Route param ":${name}" has no sample in ROUTE_PARAM_SAMPLES`);
      return sample;
    }),
  );
}

async function assertBackendUp() {
  let body;
  try {
    const res = await fetch(`${API_URL}/health`);
    body = await res.json();
  } catch {
    throw new Error(
      `Backend is not reachable at ${API_URL}.\n` +
        `Start it first:  cd oresight-backend && ./venv/Scripts/python -m uvicorn app.main:app --port 8000`,
    );
  }
  if (body.db !== 'connected') {
    throw new Error(`Backend at ${API_URL} is up but its database is "${body.db}" — bring the Docker stack up first.`);
  }
  log(`  backend  ${API_URL} — db ${body.db}, neo4j ${body.neo4j}`);
}

function build() {
  return new Promise((ok, fail) => {
    const env = { ...process.env };
    if (API_URL_OVERRIDE) env.VITE_API_URL = API_URL_OVERRIDE;
    else delete env.VITE_API_URL;
    const proc = run(['build'], { env });
    let out = '';
    proc.stdout.on('data', (d) => (out += d));
    proc.stderr.on('data', (d) => (out += d));
    proc.on('exit', (code) =>
      code === 0 ? ok() : fail(new Error(`vite build failed (exit ${code}):\n${out}`)),
    );
  });
}

/**
 * Start `vite preview` and wait until it actually answers HTTP.
 *
 * Deliberately polls the port instead of scraping the child's stdout for its
 * "Local: http://localhost:PORT" banner. Vite colourises that line, so the
 * raw bytes are "localhost:<ESC>[1m5173<ESC>[22m" and the port is not
 * textually adjacent to the colon -- a matcher over that output has to carry
 * an escape sequence around to work. Polling does not care how it is printed.
 */
function serve() {
  return new Promise((ok, fail) => {
    const proc = run(['preview', '--port', String(PORT), '--strictPort']);
    let err = '';
    let settled = false;

    proc.stderr.on('data', (d) => (err += d));
    proc.on('exit', (code) => {
      if (settled) return;
      settled = true;
      fail(new Error(`vite preview exited early (code ${code}):\n${err.trim()}`));
    });

    const deadline = Date.now() + 30_000;
    (async () => {
      while (!settled) {
        try {
          const res = await fetch(ORIGIN, { signal: AbortSignal.timeout(1000) });
          if (res.ok) {
            settled = true;
            return ok(proc);
          }
        } catch {
          // not listening yet
        }
        if (Date.now() > deadline) {
          settled = true;
          proc.kill();
          return fail(new Error(`vite preview did not answer on ${ORIGIN} within 30s`));
        }
        await new Promise((r) => setTimeout(r, 250));
      }
    })();
  });
}

async function checkRoute(context, route) {
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  page.on('pageerror', (e) => pageErrors.push(e.message));

  const failures = [];
  try {
    await page.goto(ORIGIN + route, { waitUntil: 'load', timeout: NAV_TIMEOUT_MS });
    // Best-effort settle for pages that fetch on mount. Not fatal on its own:
    // /map streams tiles continuously and never reaches a true network idle,
    // so a timeout here must not hang or fail the suite.
    await page.waitForLoadState('networkidle', { timeout: IDLE_TIMEOUT_MS }).catch(() => {});
    await page.waitForTimeout(SETTLE_MS);

    const { text, rootLength, boundaryTripped } = await page.evaluate(() => ({
      text: document.body.innerText,
      rootLength: document.getElementById('root')?.innerHTML.length ?? 0,
      boundaryTripped: /failed to render|failed to start/i.test(document.body.innerText),
    }));

    if (rootLength < 200) failures.push(`rendered almost nothing (${rootLength} chars) — likely a crash`);
    if (boundaryTripped) failures.push('ErrorBoundary was tripped');
    if (MOCK_FALLBACK_MARKER.test(text)) {
      failures.push(`fell back to sample data — the page never reached ${API_URL}`);
    }

    const undef = (text.match(/\bundefined\b/gi) || []).length;
    const nan = (text.match(/\bNaN\b/g) || []).length;
    if (undef) failures.push(`rendered "undefined" ${undef}x`);
    if (nan) failures.push(`rendered "NaN" ${nan}x`);

    for (const e of pageErrors) failures.push(`uncaught error: ${e}`);
    for (const e of consoleErrors) failures.push(`console error: ${e}`);
  } catch (err) {
    failures.push(`navigation failed: ${err.message}`);
  } finally {
    await page.close();
  }
  return failures;
}

async function main() {
  log('\nRoute-mount smoke test\n');
  await assertBackendUp();

  const routes = routesFromApp();
  log(`  routes   ${routes.length} parsed from src/App.jsx`);

  log('  building against the live API…');
  await build();

  const server = await serve();
  // An interrupted run must not leave the preview server holding the port —
  // the next run would fail to bind and look like a broken test.
  const reap = () => server.kill();
  process.once('exit', reap);
  process.once('SIGINT', () => { reap(); process.exit(130); });
  process.once('SIGTERM', () => { reap(); process.exit(143); });
  log(`  serving  ${ORIGIN}\n`);

  const browser = await chromium.launch({ channel: 'chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });

  const broken = [];
  try {
    for (const route of routes) {
      const failures = await checkRoute(context, route);
      log(`  ${failures.length ? 'FAIL' : 'ok  '}  ${route}`);
      for (const f of failures) log(`          ${f}`);
      if (failures.length) broken.push(route);
    }
  } finally {
    await browser.close();
    server.kill();
  }

  if (broken.length) {
    log(`\n${broken.length}/${routes.length} routes failed: ${broken.join(', ')}\n`);
    process.exitCode = 1;
  } else {
    log(`\nAll ${routes.length} routes clean.\n`);
  }
}

main().catch((err) => {
  log(`\n${err.message}\n`);
  process.exitCode = 1;
});
