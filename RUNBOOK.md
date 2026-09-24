# RUNBOOK: start the MOIL / OreSight stack (Windows; run from the repo root unless noted)

Ports: Postgres 5432 · Neo4j 7474/7687 · API 8000 · frontend 5173.
Use curl.exe in PowerShell (plain curl is an alias). Quick start was executed end to end on 2026-09-23 (Windows 11,
PowerShell); timings below are measured. Lines marked **INFERRED** were NOT executed or found documented; double-check them.

## Quick start (already set up once)

```powershell
cd oresight-backend
docker compose up -d          # Postgres + Neo4j + api container; ~33 s from stopped to /health ok, ~1 s if already up
docker compose ps             # wait until postgres and neo4j show (healthy); api answers /health ~3 s after start
```
```powershell
# Only if the demo DB is empty/dirty (after tests, or first run). ~32 s
# (includes seeding blast_events and the equipment_status_log backfill; no separate step)
venv\Scripts\python -m scripts.rebuild_demo_db
```
```powershell
# Only after backend code changed: the api container does NOT pick up code by itself
docker compose build api      # ~4 s with cached layers, ~40 s after code/dependency changes
docker compose up -d --no-deps api   # recreates the container with the new image; ~3 s (build alone does NOT swap it)
```
```powershell
# Alternative to the api container: local API with reload (frees port 8000 first)
docker compose stop api       # both bind 8000; stopping is a precaution (a clash with the running container was not tested)
venv\Scripts\uvicorn app.main:app --reload --port 8000   # healthy ~4 s; stop with Ctrl+C. A plain process kill leaves the
                              # reload worker holding 127.0.0.1:8000; if so: taskkill /PID <pid> /T /F
# back to the container afterwards: docker compose start api
```
```powershell
cd ..\oresight-frontend
pnpm dev                      # http://localhost:5173, ready in ~5 s; blocks this terminal (use its own); real API by default
```

## First-time setup (fresh clone)

```powershell
git clone https://github.com/Arnabh-M/moil-reserve-intelligence.git   # then: cd moil-reserve-intelligence
cd oresight-backend
python -m venv venv           # Python 3.11 (Dockerfile / tested 3.11.9)
venv\Scripts\activate
pip install -r requirements.txt       # backend deps; ~2-3 min (INFERRED)
copy .env.example .env        # backend env (defaults already match docker-compose.yml)
docker compose up -d --build  # builds the Postgres+PostGIS+pgvector image and api; several min first time
docker compose ps             # wait for (healthy)
python -m scripts.rebuild_demo_db                  # alembic + seeds + Neo4j load + scenarios + blast events + equipment history; ~32 s (measured on an existing DB)
cd ..\oresight-frontend
pnpm install                  # Node v24 / pnpm 12.3.4 (packageManager pin); ~1 min (INFERRED)
pnpm dev
```

## Verify it's working

```powershell
curl.exe http://localhost:8000/health          # {"status":"ok",...,"db":"connected","neo4j":"connected"}
curl.exe http://localhost:8000/sites           # 3 sites; centroids = data/moil_sites.json box midpoints
curl.exe http://localhost:8000/reserve-zones   # GeoJSON, 12 features, each with confidence_score
curl.exe http://localhost:8000/equipment/metrics?site_id=1   # 200 = api image is current (stale image lacks it)
docker exec -it oresight-postgres psql -U oresight -d oresight -c "\dx"   # postgis + vector installed
```
- Neo4j Browser: http://localhost:7474 · Swagger: http://localhost:8000/docs
- Frontend: open http://localhost:5173, then /map (zones + heatmap) and /site/1. Verified: the page calls
  `GET /sites` and `GET /reserve-zones` on :8000 (both 200), 12 zones, no page errors, no mock.
- Optional end-to-end check (needs api + `pnpm dev` up; ~1.5 min): `cd oresight-frontend; pnpm test:smoke` (21 tests)

## Env vars (names only)

- `oresight-backend/.env` (template `.env.example`): `APP_ENV`, `DATABASE_URL`, `NEO4J_URI`, `NEO4J_USER`,
  `NEO4J_PASSWORD`, `CORS_ORIGINS`, `PRODUCTION_EDIT_WINDOW_HOURS`, `EQUIPMENT_FLAP_WINDOW_HOURS`, `EQUIPMENT_FLAP_THRESHOLD`.
- `oresight-frontend/.env.local` (template `.env.example`; optional, defaults are the real API): `VITE_API_BASE_URL`, `VITE_USE_MOCK`.
  `VITE_USE_MOCK=false` (default) hits the real backend; `true` is an offline fallback with mock data.
- `gee_pipeline/.env` (template `.env.example`, GEE steps only): `EE_PROJECT`, `EE_SERVICE_ACCOUNT_JSON`.

## Other commands

```powershell
cd oresight-backend; venv\Scripts\python -m pytest -q        # full suite (~25 s, 246 passed, 1 xfailed); WRITES to demo DB
cd oresight-frontend; pnpm typecheck; pnpm build             # tsc + vite build (~40 s)
```

## Optional, data regeneration only (not needed to run the app)

GEE / satellite / prospectivity / tiles (`gee_pipeline/`, `prospectivity/`, `gis/`): see HANDOFF.md, section "GEE setup".

## Known gotchas

- The API image needs `docker compose build api` (+ recreate) after backend code changes, or it serves stale routes.
- The backend test suite dirties the demo DB: run `rebuild_demo_db` afterwards (it now includes the equipment-history
  backfill; rebuild before too, if a previous run left flip history behind). `scripts.export_contract` dirties it too.
  Note rebuild does NOT delete `blast_events` rows it did not seed (hand-entered or leaked-test rows stay).
- `pnpm typecheck` needs `pnpm install` first (typescript is now a devDependency).
- GEE steps need `gee_pipeline/.env` with `EE_PROJECT` and `EE_SERVICE_ACCOUNT_JSON`; keep the key file OUTSIDE git.
- Zone confidence scores (~0.20-0.41) are correct and intentionally low; see HANDOFF.md.
