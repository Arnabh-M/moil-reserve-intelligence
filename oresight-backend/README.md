# OreSight Backend

Backend API for **OreSight** — a mine reserve intelligence prototype built for
**SIH26009** (MOIL manganese mining). FastAPI + PostgreSQL/PostGIS +
Neo4j.

## Stack

- Python 3.11, FastAPI, Pydantic v2 / pydantic-settings
- SQLAlchemy 2.0 (ORM style) + GeoAlchemy2, Alembic migrations
- PostgreSQL 16 + PostGIS 3.4 (spatial data: mine boundaries, deposit
  geometries, blast zones)
- Neo4j 5 Community (equipment / site / ore-zone relationship graph)
- APScheduler (background ingestion jobs)

## One-command dev start

If Postgres + Neo4j are already up once (see [Setup](#setup) below for the
first-time steps: venv, `pip install`, `.env`), this is everything needed to
go from a stopped stack to a running, seeded API:

```bash
docker compose up -d && alembic upgrade head && python -m app.seed_dev && python -m scripts.import_p2_data && uvicorn app.main:app --reload
```

## Setup

```bash
# 1. Clone and enter the backend directory
git clone <repo-url>
cd oresight-backend

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config (defaults already match docker-compose.yml)
cp .env.example .env            # Windows (Git Bash) / macOS / Linux
# copy .env.example .env        # Windows cmd.exe

# 5. Start Postgres + Neo4j
docker compose up -d

# 6. Wait for both containers to report healthy
docker compose ps

# 7. Apply database migrations
alembic upgrade head

# 8. Load starter data (3 sites, zones, equipment, 60 days of synthetic
#    production, risk events) so nothing in the app ever renders empty
python -m app.seed_dev

# 8b. Replace the synthetic equipment & production numbers from step 8 with
#     P2's real datasets, and refresh reserve-zone stats from real deposit
#     data. See "Real data import" below for what this does and doesn't touch.
python -m scripts.import_p2_data

# 9. Run the API with auto-reload
uvicorn app.main:app --reload
```

The API is now running at **http://localhost:8000**.

### Real data import (`scripts/import_p2_data.py`)

`app/seed_dev.py` (step 8) invents its own synthetic sites, equipment, and
production numbers so the app never renders empty. `scripts/import_p2_data.py`
(step 8b) replaces the equipment and production data with the real thing from
P2's datasets, and upgrades reserve-zone stats with real numbers too:

| Source | Goes to | How |
|---|---|---|
| `data/production_history.csv` | `production_records` | Full replace per site — every existing row for the 3 sites is deleted and reinserted from the CSV |
| `data/equipment_downtime_log.csv` + `seed_graph.cypher` | `equipment` | Full replace. The roster (id/name/type/site) comes from `seed_graph.cypher` — the CSV alone has no type/name columns, only downtime events for units that went down. Status/`last_status_change` are derived from the CSV's real downtime windows |
| `data/deposit_ground_truth.csv` | `reserve_zones` (attributes only) | Each point deposit is assigned to the nearest of `seed_dev.py`'s 4 zone boxes per site; `confidence_score`/`estimated_grade_pct`/`estimated_depth_m` are recomputed from the real, assigned deposits. Zone **geometry** still comes from `seed_dev.py` — none of P2's CSVs carry zone polygons |

**Supplements, doesn't replace, `seed_dev.py`:** run `seed_dev.py` first, then
`import_p2_data.py`. `import_p2_data.py` bootstraps sites/zones itself (reusing
`seed_dev.py`'s helpers) so it *can* run standalone on a fresh DB, but it
deliberately does not touch `risk_events` — that still only comes from
`seed_dev.py`. Running `import_p2_data.py` after `seed_dev.py` means the two
`risk_events` rows that reference a specific equipment id
(`source_entity_id`) will point at a row that no longer exists, since
`import_p2_data.py` deletes and reinserts all equipment with fresh ids. The
risk events themselves still display fine (severity/description/etc. are
unaffected) — only that dangling FK-ish reference goes stale. Not fixed here;
reconciling `risk_events` seeding to the real equipment roster is a
reasonable follow-up once `risk_events` itself moves off synthetic data.

**Destructive by design:** unlike `seed_dev.py` (which skips rows that
already exist, so it never clobbers manual edits), `import_p2_data.py` fully
deletes and reinserts `equipment` and `production_records` for the 3 sites on
every run. Any status change made via `POST /equipment/{id}/status` or record
added via `POST /production` since the last import is discarded. Don't
re-run it mid-demo expecting it to leave manual test data alone — that's
exactly what it resets.

**Equipment status will show all "up".** Every window in
`equipment_downtime_log.csv` is closed as of the data's latest date
(2026-08-30), so nothing imports as currently down — `seed_dev.py`'s 2
hardcoded "down" units are gone. If a demo scenario needs a visibly-down
unit, set one explicitly with `POST /equipment/{id}/status` after importing.

Run it any time after `alembic upgrade head` with:

```bash
python -m scripts.import_p2_data
```

### Verifying the stack

```bash
curl http://localhost:8000/health
```

A healthy response looks like:

```json
{"status": "ok", "service": "oresight-api", "db": "connected", "neo4j": "connected"}
```

`db` / `neo4j` will report `"unavailable"` instead of failing the request if
either database isn't reachable — the endpoint itself always returns `200`.

### PostGIS extension

The `postgis/postgis:16-3.4` image automatically runs
`CREATE EXTENSION postgis;` (plus `postgis_topology`, `fuzzystrmatch`, and
`postgis_tiger_geocoder`) against the database named by `POSTGRES_DB`
(`oresight`) the **first time** the container initializes an empty data
volume. You do not need to run this manually — and the initial Alembic
migration also runs `CREATE EXTENSION IF NOT EXISTS postgis;` itself as a
safety net, so `alembic upgrade head` works even against a bare (non-postgis)
Postgres instance. You can confirm the extension is installed with:

```bash
docker exec -it oresight-postgres psql -U oresight -d oresight -c "\dx"
```

### Running tests

```bash
pytest
```

- `tests/test_health.py` — `/health` shape, no DB required.
- `tests/test_migrations.py` — Alembic upgrade/downgrade correctness against
  disposable throwaway databases (never touches the dev DB). Skips if
  Postgres isn't reachable.
- `tests/test_smoke.py` — every endpoint against the real seeded dev
  database: every GET returns a non-empty payload, `POST
  /equipment/{id}/status` with `status=down` opens a risk event, duplicate
  `POST /production` returns 409, `POST /simulate` moves `after` away from
  `before`. Cleans up anything it writes. Skips if Postgres isn't reachable.

Run a single file with `pytest tests/test_smoke.py -v`.

### Creating a new migration

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

### Exporting the API contract

```bash
python -m scripts.export_contract
```

Starts the app in-process (real seeded DB, no separate server needed),
actually calls every endpoint, and regenerates:

- `docs/openapi.json` — the raw OpenAPI 3.1 schema
- `docs/API_CONTRACT.md` — a human-readable contract with real captured
  example responses, grouped by feature area

Re-run this after adding or changing a route so the docs stay in sync. The
two write endpoints it exercises (equipment status, production create) are
cleaned up automatically so the seeded demo dataset is untouched afterward.

### Background scheduler

`app/services/scheduler.py` runs an APScheduler `BackgroundScheduler`,
started/stopped via the FastAPI lifespan (safe to call more than once in the
same process, so it never double-starts under `uvicorn --reload`). Two jobs
are registered today, both no-op placeholders that just log a timestamp:

| Job | Interval | Becomes real on |
|---|---|---|
| `ingest_satellite_data` | every 6h | Day 3 — Google Earth Engine ingestion |
| `run_watcher` | every 5min | Day 3 — ML teammate's Watcher agent |

Check `GET /admin/jobs` any time to prove the scheduler is alive and see
each job's next run time and last run status.

## Project layout

```
app/
  main.py       FastAPI app factory, CORS, error handlers, /health
  config.py     pydantic-settings Settings (.env)
  db.py         SQLAlchemy engine/session/Base + get_db() dependency
  seed_dev.py   Idempotent dev seed data
  models/       SQLAlchemy ORM models
  schemas/      Pydantic request/response schemas
  routers/      API route modules
  services/     Business logic: geo/GeoJSON helpers, scheduler, lookups
alembic/        Database migrations
scripts/        One-off dev tooling (API contract export)
docs/           Generated API contract (openapi.json, API_CONTRACT.md)
tests/          pytest test suite
```

## API endpoints

Full parameter details and **real captured example responses** for every
endpoint live in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) (regenerate
with `python -m scripts.export_contract`). Interactive docs are always
available at `/docs` (Swagger UI) and `/redoc`.

### What's real vs stubbed today

| Method | Path | Status |
|---|---|---|
| GET | `/sites`, `/sites/{id}`, `/sites/{id}/geojson` | **Live** |
| GET | `/equipment` | **Live** |
| POST | `/equipment/{id}/status` | **Live** — also opens a risk event when marked `down` |
| GET | `/production` | **Live** |
| POST | `/production` | **Live** — 409 on duplicate `(site_id, date)` |
| GET | `/risk-events` | **Live** |
| GET | `/reserve-zones` | **Live** (real DB query, not a mock) |
| GET | `/kpi/summary` | **Live** |
| GET | `/admin/jobs` | **Live** (scheduler introspection) |
| GET | `/risk-events/{id}/causal-graph` | **STUB** — hardcoded 5-node graph, replaced Day 3 with a live Neo4j traversal |
| GET | `/recommendations` | **STUB** — hand-authored options, replaced Day 4 with the real recommendation engine |
| POST | `/simulate` | **STUB** — deterministic formula (grounded in real per-site data, perturbed by scenario type + duration), replaced Day 4-5 with the real simulation engine |

## Troubleshooting

**Port 5432 already in use** — something else on your machine (a local
Postgres install, or another project's docker-compose) is already bound to
5432.
- Find it: `netstat -ano | findstr 5432` (Windows) or `lsof -i :5432`
  (macOS/Linux), then stop that process/container.
- Or keep both running: change the `postgres` service's port mapping in
  `docker-compose.yml` to e.g. `"5433:5432"` and update `DATABASE_URL` in
  `.env` to use port `5433`.

**PostGIS extension missing** — this should be rare since both the Docker
image and the initial migration create it automatically, but if you ever see
`function st_makepoint(...) does not exist` or similar:
- Confirm you're running `postgis/postgis:16-3.4` (not a plain `postgres`
  image) in `docker-compose.yml`.
- If you switched images after the volume already existed, the image's
  first-boot init script won't rerun. Fix: `docker compose down -v` (wipes
  the `oresight_postgres_data` volume) then `docker compose up -d` again,
  or just run `alembic upgrade head`, which also issues
  `CREATE EXTENSION IF NOT EXISTS postgis;` itself.

**Neo4j auth failure** (`/health` shows `"neo4j": "unavailable"`, or
`Neo.ClientError.Security.Unauthorized`) — Neo4j sets its admin password
from `NEO4J_AUTH` only on the **first** container boot with an empty data
volume; editing `NEO4J_PASSWORD` in `.env` afterward does not change it.
- Either set `.env`'s `NEO4J_PASSWORD` back to whatever it was on first
  boot (default: `oresight123`), or
- Reset it: `docker compose down`, remove the `oresight_neo4j_data` volume
  (`docker volume rm oresight-backend_oresight_neo4j_data`), then
  `docker compose up -d` to reinitialize with the current `.env` value.

## Agent layer (`app/agents/`)

Watcher, Simulator, and Planner — see each file's module docstring for the
full design rationale. Quick facts:

- **Watcher** (`watcher.py`) polls Postgres for new equipment-down /
  production-shortfall signals, dedupes against unresolved `risk_events`,
  and writes a linked row + Neo4j `RiskEvent` node (`external_ref` ties
  them together) for anything genuinely new.
- **Simulator** (`simulator.py`) runs the trained shortfall model
  (`models/shortfall_forecaster.pkl` — see below) on real Postgres state,
  before vs. after a hypothetical scenario, plus a live ≤3-hop Neo4j
  traversal. Strictly read-only. This is what `app/routers/simulate.py`'s
  stub gets replaced with.
- **Planner** (`planner.py`) searches for redeploy/reschedule/adjust-plan
  candidates and scores each with a real `SimulatorAgent` call rather than
  a hand-authored number. Replaces `app/routers/recommendations.py`'s stub.

**Both replacement routers need a reshape, not just a stub swap** — the
agents return the *real* `SimulateResponse`/`RecommendationOut` shapes
(`affected_graph_path`, `production_forecast_tonnes`, per-option
`confidence`, etc.), not the shape in the original Day 3 task doc, which
predated reading this repo's actual schemas/stubs. See the "INTEGRATION
NOTE" comments at the top of `simulator.py` and `planner.py` for exactly
what differs and why.

**Before running any agent**, train the shortfall model — from the repo
root (one level up), not from here:

```bash
cd ..
python train_shortfall_model.py
```

This reads `data/production_history.csv` / `data/equipment_downtime_log.csv`
(Day 1) and writes `oresight-backend/models/shortfall_forecaster.pkl` +
`feature_columns.json`. Both are gitignored (`*.pkl` under "Model
artefacts") — every clone needs to run this once locally.

Each agent has a `__main__` block that runs it against your local stack and
prints the result — good for checking things work before wiring in FastAPI:

```bash
python -m app.agents.watcher
python -m app.agents.simulator
python -m app.agents.planner
```

**Resolved:** the Postgres/Neo4j equipment taxonomy split described in
earlier versions of this doc is fixed by `scripts/import_p2_data.py` (see
"Real data import" below) — Postgres equipment is now sourced from the same
`seed_graph.cypher` roster Neo4j uses, so `app/agents/_bridge.py`'s
(site, normalized type) match succeeds for every row. `haul_truck`/`crusher`
no longer exist in Postgres, because they never existed in Neo4j's fleet
either — if MOIL's real equipment roster needs those types, that's a content
gap in `seed_graph.cypher` to raise with P2, not a mapping bug here. This
only applies once `import_p2_data.py` has been run — a DB seeded with only
`app/seed_dev.py` still has the old invented fleet.

**Known model limitation:** the trained shortfall model's response to
`rolling_7day_downtime_pct` and `schedule_pressure` is weak or
counter-intuitive (pushing downtime to its max barely moves the
prediction; higher `schedule_pressure` actually predicts *less* shortfall)
— an honest consequence of 6 months of synthetic data with few severe
downtime events and no true backlog dynamics behind `schedule_pressure`,
not a bug in the agents. `rainfall_proxy`/seasonality dominates and behaves
intuitively. See the top of `train_shortfall_model.py` for detail. Worth
revisiting if `equipment_down`/`delay_blasting` scenarios need to look more
dramatic for a demo.

**2026-08-31 note:** this dev machine already had an unrelated project's
Postgres container bound to host port 5432, so local testing here used
`docker-compose.local.yml` (postgres remapped to `5433`, gitignored,
untracked) instead of `docker-compose.yml` directly. A fresh machine
doesn't need this — just follow Setup above as written.

## For frontend teammates

- **Base URL:** `http://localhost:8000`
- **Interactive API docs (Swagger UI):** `http://localhost:8000/docs`
  (also available as ReDoc at `/redoc`)
- **Full contract with real examples:** [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- **Is the backend up?** `GET /health` — check `status == "ok"`. It also
  tells you whether Postgres and Neo4j are currently reachable, which is
  useful when debugging "why is data missing" issues.
- CORS is already configured for `http://localhost:5173` and
  `http://localhost:3000` (Vite / CRA defaults). If your dev server runs on
  a different port, add it to `CORS_ORIGINS` in `.env` (it's a JSON array)
  and restart the server.
- New endpoints will be added under `app/routers/` and show up in `/docs`
  automatically — no separate API spec to keep in sync.
- Every error response has the same shape:
  `{"detail": "...", "error_code": "NOT_FOUND" | "CONFLICT" | "VALIDATION_ERROR" | "INTERNAL_ERROR" | ...}`.
