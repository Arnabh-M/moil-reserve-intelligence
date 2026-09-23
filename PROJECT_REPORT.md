# OreSight / MANGANEX — MOIL Reserve Intelligence Platform

**Problem Statement:** SIH26009 — AI/ML-driven reserve estimation and production
intelligence for MOIL manganese mining operations.

An end-to-end mine reserve intelligence platform that fuses **geospatial
prospectivity modelling**, a **causal knowledge graph**, **agentic what-if
simulation**, and a **live operations dashboard** across three MOIL mine sites:
**Balaghat**, **Nagpur**, and **Bhandara**.

---

## 1. Executive Summary

OreSight answers four questions a mine planner asks every day:

1. **Where is the ore likely to be?** — a Random Forest prospectivity classifier
   over Sentinel-2, DEM and structural-geology features; the per-cell ensemble score
   drives the map heatmap and each reserve zone's confidence is its mean.
2. **What is going wrong right now?** — a Watcher agent polls production and
   equipment telemetry, raises risk events, and mirrors them into a Neo4j causal
   graph.
3. **What happens if I do nothing?** — a Simulator agent runs trained
   shortfall-forecaster projections plus a real graph traversal to show the
   blast-plan → ore-zone → output ripple.
4. **What should I do instead?** — a Planner agent proposes reschedule / redeploy
   / adjust-plan options, each one scored by an actual simulation run, with a
   deterministic cascade (ripple-impact) analysis attached.

Every number surfaced in the UI is traceable to a specific model, query, or
graph path — explainability is a hard design constraint, not a feature.

---

## 2. Technology Stack

### 2.1 Backend — `oresight-backend/`

| Layer | Technology |
|---|---|
| Web framework | **FastAPI** (≥0.115), **Uvicorn** (standard/uvloop) ASGI server |
| Language | **Python 3.11+** (containerised on `python:3.11-slim`) |
| ORM / data access | **SQLAlchemy 2.0** (typed `Mapped[]` declarative models) |
| Spatial ORM | **GeoAlchemy2** + **Shapely 2.x** (geometry columns, WKB/WKT handling) |
| Relational DB | **PostgreSQL 16** with **PostGIS 3.4** and **pgvector** |
| Graph DB | **Neo4j 5 Community** (Bolt driver ≥5.25, **APOC** plugin enabled) |
| Migrations | **Alembic** (9 tracked revisions, merge revisions included) |
| Validation / config | **Pydantic v2** + **pydantic-settings** (`.env`-driven `Settings`) |
| Vector search | **pgvector** (256-dim cosine similarity over site notes) |
| Scheduling | **APScheduler** (background Watcher polling, job introspection endpoint) |
| ML inference | **XGBoost** ≥2.1, **scikit-learn**, **joblib**, **pandas**, **NumPy** |
| PDF ingestion | **pypdf** + **python-multipart** (survey-report upload & extraction) |
| External data | **httpx** → **Open-Meteo API** (real ECMWF/GFS/ICON weather) |
| Testing | **pytest** (≈152 tests across 14 suites) |
| Packaging | **Docker** + **docker-compose** (api / postgres / neo4j, healthchecked) |

### 2.2 Frontend — `oresight-frontend/`

| Layer | Technology |
|---|---|
| Framework | **React 18** + **TypeScript/JSX** hybrid |
| Build tool | **Vite** (env-driven `PORT` / `BASE_PATH`, `cross-env`) |
| Package manager | **pnpm 12** (workspace catalog protocol) |
| Routing | **react-router-dom v7** (+ `wouter` for the landing shell) |
| Mapping | **MapLibre GL v6** + **react-map-gl v8** (raster tiles, GeoJSON overlays) |
| Graph visualisation | **@xyflow/react** (React Flow v12) — causal-chain rendering |
| Charting | **Recharts** (KPI/time-series) and **Plotly.js** (cross-sections, surfaces) |
| Design system | **Tailwind CSS v4** + **shadcn/ui** over **Radix UI primitives** (~45 components) |
| Icons | **lucide-react**, **react-icons** |
| Forms & validation | **react-hook-form** + **zod** + `@hookform/resolvers` |
| State / data | **@tanstack/react-query**, custom `useAsync` hook |
| Animation | **framer-motion**, `tw-animate-css` |
| Utilities | `clsx`, `tailwind-merge`, `class-variance-authority`, `date-fns`, `react-window` (virtualised lists), `rc-slider` |
| Notifications | **sonner** toasts, Radix toast primitives |
| Theming | **next-themes** (light/dark) |
| E2E testing | **Playwright** (`pnpm test:smoke`) |
| Deployment | **Vercel** (`oresite.vercel.app`) |

### 2.3 Data Science / Geospatial Pipeline (repo root)

| Purpose | Technology |
|---|---|
| Classification | **scikit-learn** `RandomForestClassifier`, **XGBoost** `XGBClassifier` |
| Regression (forecasting) | **XGBoost** `XGBRegressor` (time-based split) |
| Geostatistics | **PyKrige** `OrdinaryKriging` (variogram model CV-selected) |
| Geospatial I/O | **GeoPandas**, **Rasterio**, **Shapely**, **pyproj** (UTM reprojection) |
| Numerics | **NumPy**, **SciPy**, **pandas** |
| Remote sensing | **Google Earth Engine API** (`gee_pipeline/`, `prospectivity/gee_features.py`) |
| Tiling | Custom raster → XYZ tile generation (`gis/generate_tiles.py`) |
| Model persistence | **joblib** `.pkl` artifacts + pinned feature-order JSON |
| Notebooks | **Jupyter** |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND — React + Vite (Vercel)                                    │
│  Dashboard · Reserve Map · Reports · Simulator · Field Intake        │
│  MapLibre GL  |  React Flow  |  Recharts / Plotly  |  shadcn/Radix   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  REST / JSON (CORS-guarded)
┌───────────────────────────────▼──────────────────────────────────────┐
│  API — FastAPI (16 routers, contract-documented, OpenAPI exported)   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ AGENT LAYER (app/agents/)                                      │  │
│  │  WatcherAgent   → detect & mirror risk signals (idempotent)    │  │
│  │  SimulatorAgent → what-if projection + causal traversal        │  │
│  │  PlannerAgent   → simulation-backed mitigation ranking         │  │
│  │  _bridge.py     → Postgres ↔ Neo4j entity reconciliation       │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │ SERVICE LAYER (app/services/)                                  │  │
│  │  cascade_service · dependency_derivation · embedding           │  │
│  │  extraction · geo · lookups · pdf_text · scheduler · weather   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────┬──────────────────────────┬─────────────────────┬──────────────┘
       │                          │                     │
┌──────▼───────────┐   ┌──────────▼──────────┐   ┌──────▼─────────────┐
│ PostgreSQL 16    │   │ Neo4j 5 (+APOC)     │   │ ML ARTIFACTS       │
│ + PostGIS 3.4    │   │ Causal knowledge    │   │ per-site rf/nb/xgb │
│ + pgvector       │   │ graph: MineSite,    │   │ shortfall XGBoost  │
│ Sites, equipment,│   │ Equipment, OreZone, │   │ rf_/xgb_ per-site  │
│ production, risk,│   │ BlastPlan, Weather, │   │ zone confidence    │
│ zones, notes,    │   │ RiskEvent + CAUSES/ │   │ surface (.npz)     │
│ blasts, weather  │   │ AFFECTS/DEPENDS_ON  │   │ NDVI/elev fields   │
└──────────────────┘   └─────────────────────┘   └────────────────────┘
```

### 3.1 Architectural decisions worth stating

- **Dual-store by design.** Postgres is the transactional system of record
  (rows, audit trails, spatial geometry, vectors). Neo4j holds *relationships* —
  the causal chains that make "why did output drop?" answerable in one traversal
  instead of six joins. `app/agents/_bridge.py` reconciles the two
  independently-seeded entity spaces and **refuses to guess** when an entity
  cannot be matched (logs a warning, omits the edge).
- **Plain-Python agents, not LangGraph.** All three agents are deterministic,
  straight-line `detect → query → perturb → predict → rank` pipelines with no
  branching LLM decisions. A graph-orchestration framework would add a
  dependency and boilerplate without earning it. Documented explicitly in each
  agent's module docstring.
- **Graceful degradation is a contract.** `compute_cascade` never raises — any
  failure yields `None`, logged with context, and never alters the
  recommendation it was computed for. Causal-graph endpoints fall back to a
  single-node graph tagged `graph_source='postgres_fallback'` when Neo4j has no
  matching node.
- **Typed error envelope.** Every error response is `{detail, error_code}` with
  codes mapped from HTTP status (`VALIDATION_ERROR`, `SERVICE_UNAVAILABLE`,
  `PAYLOAD_TOO_LARGE`, …). Postgres/Neo4j outages are classified as **503
  transient**, never 500 — distinguishing infra from bugs. 422 `detail` stays a
  *list* of human-readable per-field strings (`"field: value - message"`),
  generated generically so any new Pydantic constraint gets a readable message
  for free.
- **Local-first embeddings.** `HashingEmbedder` (256-dim, stemmed bag-of-words +
  bigrams, L2-normalised) is deterministic and needs no model download, API key,
  or network — swappable for sentence-transformers behind one `Embedder.embed()`
  interface, with the DB column width pinned to `EMBEDDING_DIM` by migration.

---

## 4. Features

### 4.1 Reserve Prospectivity & Mapping
- Per-site Random Forest / XGBoost / Naive Bayes classifiers over structural +
  remote-sensing features (5-fold spatial CV), scored on a 100 m grid.
- Reserve-zone confidence = mean of that same per-cell score inside each zone
  (`scripts/import_prospectivity_scores.py`); one source for heatmap and zones.
- GeoJSON reserve-zone export with per-cell `confidence_score` and `site_id`.
- Interactive MapLibre map: raster prospectivity overlay with opacity control,
  structural-lines GeoJSON, layer toggles, confidence legend, NDVI time slider,
  zone detail panel, prospectivity cell inspector, and a **cross-section drawer**.
- Per-site models (`rf_` / `xgb_` × `balaghat` / `nagpur` / `bhandara`) alongside
  the global one.

### 4.2 Production Shortfall Forecasting
- XGBoost regressor on `shortfall_pct = (target − actual) / target`, trained on a
  **time-based** (not random) split to avoid look-ahead leakage.
- Engineered features: `rolling_7day_downtime_pct`, `days_since_last_maintenance`
  (left as NaN — XGBoost handles missingness natively), `rainfall_proxy`
  (monsoon-weighted seasonal), `schedule_pressure` (lag-shifted trailing 14-day
  mean shortfall, so the current day never leaks into its own feature), plus
  cyclical `dow_sin/cos` and `month_sin/cos` encodings.
- Exact feature column order persisted for the Simulator agent to reuse.

### 4.3 Causal Knowledge Graph
- Neo4j schema with constraints plus seed data: 3 mine sites, 15 equipment
  units, ore zones, weather events, blast plans, and risk events.
- Relationship semantics reused, never redefined:
  `(Equipment)-[:DEPENDS_ON]->(BlastPlan)`, `(BlastPlan)-[:AFFECTS]->(OreZone)`,
  `(Weather|Equipment)-[:CAUSES]->(RiskEvent)`,
  `(BlastPlan)-[:SCHEDULED_ON]->(CalendarDate)`.
- `GET /risk-events/{id}/causal-graph` → up to 3-hop traversal, rendered in the
  UI with React Flow.
- Dependency-edge derivation script for inferring missing structural edges.

### 4.4 Agentic Intelligence
- **Watcher** — scheduled (5-min) poll for equipment-down and
  production-shortfall signals (>15% below target); idempotent dual-write into
  Postgres `risk_events` and Neo4j `RiskEvent` nodes with causal edges;
  `external_ref` links the two ID spaces.
- **Simulator** — three scenarios (`equipment_down`, `delay_blasting`,
  `rainfall_event`) over a configurable horizon; returns
  `production_forecast_tonnes`, before/after `reserve_confidence`, and the
  `affected_graph_path`.
- **Planner** — candidate search (3 fixed Cypher/SQL lookups) → simulate each →
  rank; every option carries a `confidence` and a simulation-derived
  `projected_impact` representing *risk avoided by acting now*.
- **Cascade / ripple-impact service** — deterministic traversal + rule evaluation
  producing `cascade_adjusted_impact`, with blocking / shifted / clear
  classification and date-collision detection on blast plans.

### 4.5 Field Intake (operator data capture)
Four tabs — **Production**, **Equipment**, **Geology**, **Blast Log** — each
lazy-loaded behind its own error boundary so one broken tab cannot take down the
router.
- **Production:** persisted records with a configurable **edit window**
  (`PRODUCTION_EDIT_WINDOW_HOURS`, default 48h) beyond which PATCH is refused;
  full audit trail via `production_record_audit`.
- **Equipment:** status changes written to `equipment_status_log`, with **flap
  detection** — more than `EQUIPMENT_FLAP_THRESHOLD` (4) status changes within
  `EQUIPMENT_FLAP_WINDOW_HOURS` (24) opens one `equipment_flapping` risk event.
- **Geology:** survey **PDF upload** → deterministic deposit extraction → Neo4j
  `OreZone` / `StructuralFeature` node creation, with server-declared upload
  limits exposed at `GET /config/upload-limits` so the client never hardcodes them.
- **Blast Log:** blast-event capture feeding the blast-plan graph and cascade checks.

### 4.6 Semantic Site Notes (RAG)
Free-text operator notes embedded into a 256-dim vector and stored in a pgvector
column; `GET /site-notes/search` ranks by cosine similarity — a query for
"monsoon flooding" surfaces a note about "heavy rain waterlogging the haul road".

### 4.7 Live Weather Integration
Open-Meteo (ECMWF/GFS/ICON) observations and forecasts sampled at each site
centroid and persisted to `weather_records`. Provenance, licensing, and the
~9–13 km model grid resolution limit are documented in-source rather than glossed
over.

### 4.8 Reporting, KPIs & Demo Tooling
- `GET /kpi/summary` — aggregate production, risk, and averaged reserve confidence.
- Reports & insights view with time-series and comparative charts.
- `GET /demo/scenarios` resolves seeded demo scenarios to their **current**
  risk-event IDs, so nothing in the demo path is ever hardcoded.
- `GET /admin/jobs` for scheduler introspection; seed/rebuild scripts for
  Scenario A and Scenario B walkthroughs.
- Offline fallback: `VITE_USE_MOCK=true` switches the frontend to bundled mock
  data for venue-Wi-Fi resilience.

---

## 5. MVP Scope

**In the MVP (working end-to-end):**

| Capability | Status |
|---|---|
| Three-site reserve map (trained-ensemble heatmap; zone confidence = heatmap mean) | Live |
| Prospectivity classifier + GeoJSON zone export | Live |
| Shortfall forecaster (XGBoost) | Live |
| Neo4j causal graph + 3-hop traversal endpoint | Live |
| Watcher / Simulator / Planner agent loop | Live |
| Cascade ripple-impact analysis | Live |
| Field intake (4 tabs) with audit trail + flap detection | Live |
| Survey-PDF extraction into the graph | Live |
| pgvector semantic note search | Live |
| Real weather ingestion (Open-Meteo) | Live |
| KPI summary + reports dashboard | Live |
| Dockerised 3-service stack with healthchecks | Live |

**Deliberately out of MVP scope (documented, not hidden):**
- **Authentication & RBAC** — the supervisor-override bypass on the production
  edit window is specified but unimplemented (Phase 8).
- **Real Earth Engine features** — `earthengine-api` is not provisioned; 9 of the
  10 features in `prospectivity/gee_features.py` are left as explicit `NaN` and
  marked pending. They are **never imputed or replaced with noise**.
- **Real MOIL operational data** — the demo runs on synthetic, GSI-styled data
  (see §7).
- **A learned reserve-confidence model** — the Simulator's `reserve_confidence`
  delta is an explicit decay heuristic scaled by duration, labelled as a
  placeholder in-source.

---

## 6. Repository Structure

```
AIML_Manganese_MOIL/
├── oresight-backend/              # FastAPI service
│   ├── app/
│   │   ├── main.py                # App factory, CORS, error handlers, health
│   │   ├── config.py              # Pydantic Settings (.env-driven)
│   │   ├── db.py / graph_db.py    # Postgres engine + Neo4j driver lifecycle
│   │   ├── models/                # 11 SQLAlchemy ORM models
│   │   │   ├── site.py  equipment.py  production_record.py
│   │   │   ├── production_record_audit.py  equipment_status_log.py
│   │   │   ├── reserve_zone.py  risk_event.py  blast_event.py
│   │   │   └── shift_plan_entry.py  site_note.py  weather_record.py
│   │   ├── schemas/               # 15 Pydantic request/response contracts
│   │   ├── routers/               # 16 API routers (see §6.1)
│   │   ├── services/              # cascade, dependency derivation, embedding,
│   │   │                          # extraction, geo, lookups, pdf_text,
│   │   │                          # scheduler, weather
│   │   ├── agents/                # watcher, simulator, planner, _bridge
│   │   └── constants/             # validation_limits.py (shared bounds)
│   ├── alembic/versions/          # 9 migrations (incl. merge revisions)
│   ├── scripts/                   # graph load, data import, demo seeding,
│   │                              # OpenAPI contract export
│   ├── tests/                     # 14 pytest suites (~152 tests)
│   ├── docs/API_CONTRACT.md       # Hand-written endpoint contract
│   ├── docs/openapi.json          # Exported OpenAPI schema
│   ├── Dockerfile · Dockerfile.postgres · docker-compose.yml
│   └── requirements.txt
│
├── oresight-frontend/             # React + Vite SPA
│   ├── src/
│   │   ├── App.jsx                # Shell, nav groups, routes, shared widgets
│   │   ├── api/                   # client.js · mockData.js · placeholders.js
│   │   ├── components/
│   │   │   ├── map/               # MineMap, LayerToggle, ConfidenceLegend,
│   │   │   │                      # ZoneDetailPanel, CrossSectionDrawer,
│   │   │   │                      # NdviTimeSlider, ProspectivityCellPanel
│   │   │   ├── field-intake/      # Production / Equipment / Geology / BlastLog
│   │   │   ├── ui/                # ~45 shadcn/Radix primitives
│   │   │   ├── CausalGraph.jsx    # React Flow causal-chain renderer
│   │   │   └── error-boundary.tsx
│   │   ├── pages/landing/         # MANGANEX marketing landing page
│   │   ├── hooks/ · lib/ · constants/
│   │   └── index.css
│   ├── public/                    # tiles/, prospectivity/, structural_lines.geojson,
│   │                              # MANGANEX emblems, favicon, robots.txt
│   └── vite.config.ts · package.json
│
├── prospectivity/                 # Per-site prospectivity pipeline
│   ├── grid.py  training_data.py  feature_selection.py
│   ├── gee_features.py  train_models.py  classify_export.py
│   └── METHODOLOGY.md             # Blockers-first methodology & known gaps
│
├── gis/                           # Raster & tiling utilities
│   ├── ndvi_pull.py  ndvi_timeseries.py  raster_utils.py  generate_tiles.py
│   └── tiles/
│
├── gee_pipeline/gee_prep.py       # Earth Engine preparation (mock branch today)
│
├── Root ML pipeline (run in order)
│   ├── generate_datasets.py        # Day 1 — synthetic production/downtime/ground truth
│   ├── geo_utils.py                # Shared geospatial helpers
│   ├── generate_features.py        # Part 1 — structural lines + training features
│   ├── prospectivity/              # Parts 2-4 — per-site models, map layers, zone-confidence source
│   ├── shortfall_features_wip.py   # Part 5 — shortfall feature engineering
│   ├── train_shortfall_model.py    # Day 3 — XGBoost shortfall forecaster
│   └── finalize_shortfall_model.py
│
├── seed_graph.cypher              # Neo4j constraints + seed data + verification queries
├── data/                          # Generated CSVs, GeoJSON, .npz surface
├── models/                        # .pkl artifacts (global + per-site)
├── methodology.md                 # Model metrics, validation, limitations
├── IMPLEMENTATION_NOTES.md        # Field Intake hardening phases & decisions
├── demo_script.md                 # Demo walkthrough
└── requirements.txt               # Data-science environment
```

### 6.1 API Surface (16 routers)

| Router | Prefix | Key endpoints |
|---|---|---|
| sites | `/sites` | list, detail, `/geojson`, `/{id}/geojson` |
| equipment | `/equipment` | list, detail, history, `POST /{id}/status` |
| production | `/production` | list, summary, `POST`, `PATCH /{id}` (edit-window guarded) |
| risk-events | `/risk-events` | list, `GET /{id}/causal-graph` |
| reserve-zones | `/reserve-zones` | confidence-scored zone polygons |
| recommendations | `/recommendations` | PlannerAgent output with cascade |
| simulate | `/simulate` | `GET` scenario metadata, `POST` run projection |
| kpi | `/kpi` | `/summary` |
| reports | `/reports` | `POST /upload` (survey PDF → graph) |
| site-notes | `/site-notes` | `POST`, `GET /search` (pgvector) |
| blast-events | `/blast-events` | list, detail, `POST`, `PATCH` |
| shift-plan | `/shift-plan` | `POST`, `GET` |
| weather | `/weather` | current, forecast / history |
| demo | `/demo` | `/scenarios` (dynamic ID resolution) |
| admin | `/admin` | `/jobs` scheduler introspection |
| config | `/config` | `/upload-limits` |
| meta | `/`, `/health` | service root + DB/Neo4j health |

### 6.2 Frontend Routes

`/` Dashboard · `/site/:id` Site detail · `/map` Reserve map · `/reports` Reports
& insights · `/simulator` Scenario simulator · `/field-intake` Field intake ·
`/settings` Settings · `/login` · landing page. Legacy paths (`/timeline`,
`/recommendations`, `/data-input`) redirect to their current equivalents.

---

## 7. Model Validation & Honest Limitations

**Reserve Prospectivity Classifier** (n = 40 labeled points, 4 features:
`dist_to_nearest_structure`, `structural_density`, `synthetic_ndvi`,
`synthetic_elevation`):

| Model | AUC-ROC | Precision | Recall | F1 |
|---|---|---|---|---|
| **RandomForest (selected)** | 0.875 | 0.800 | 1.000 | 0.889 |
| XGBoost | 0.875 | 0.750 | 0.750 | 0.750 |

Because an 8-point test fold is coarse, the result was additionally validated by
**5-fold stratified CV across 3 seeds** (RF mean AUC **0.773**; XGBoost 0.715)
and a **label-shuffle permutation test** (real 0.773 vs. shuffled null mean 0.49 /
p95 0.71 → **p = 0.005**). `dist_to_nearest_structure` dominates feature
importance (~0.45), matching the generative label rule (point-biserial
r = −0.57, p = 0.0001; `structural_density` r = +0.58, p = 0.0001).

**Stated limitations:**
- All production, downtime, and deposit data is **synthetic** and GSI-styled;
  none of it is real MOIL exploration or production data.
- The signal is deliberately *moderate*, not a near-perfect separator — CV folds
  swing between ~0.56 and ~1.0, and n = 40 keeps every estimate wide.
- In the shortfall forecaster, `rolling_7day_downtime_pct` **saturates** and
  `schedule_pressure` carries a **negative** learned relationship — an honest
  artifact of six months of synthetic data with isolated 5–10 day shortfall
  windows and no autocorrelated backlog dynamics. Consequently the
  `equipment_down` and `delay_blasting` scenarios show weak deltas, while
  `rainfall_event` behaves as expected. This is documented rather than masked.
- Weather is regional (9–13 km grid), not in-pit or bench-level microclimate.
- Open-Meteo's public API is non-commercial/educational; a production MOIL
  deployment requires a commercial plan or a self-hosted Open-Meteo / IMD instance.

Aligned with **Zhao et al. (2025)**, *Predicting Manganese Mineralization Using
Multi-Source Remote Sensing and Machine Learning: A Case Study from the Malkansu
Manganese Belt*, Minerals 15(2), 113 —
[DOI 10.3390/min15020113](https://doi.org/10.3390/min15020113).

---

## 8. Getting Started

### 8.1 Infrastructure (Docker — recommended)
```bash
cd oresight-backend
docker compose up -d --build     # postgres(+PostGIS+pgvector), neo4j(+APOC), api
```
Services: API `:8000` (interactive docs at `/docs`), Postgres `:5432`,
Neo4j `:7474` / `:7687`.

### 8.2 Backend (local)
```bash
cd oresight-backend
python -m venv venv && venv\Scripts\activate     # source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m scripts.load_graph                      # seed Neo4j
python -m scripts.rebuild_demo_db                 # seed demo scenarios
uvicorn app.main:app --reload
pytest                                            # ~152 tests
```

### 8.3 Frontend
```bash
cd oresight-frontend
pnpm install
pnpm dev            # http://localhost:5173
pnpm typecheck
pnpm test:smoke     # Playwright
```
Environment: `VITE_API_BASE_URL` (default `http://localhost:8000`),
`VITE_USE_MOCK=true` for offline mock mode.

### 8.4 ML Pipeline (hard dependency chain — run in order)
```bash
pip install -r requirements.txt   # root env
python generate_datasets.py
python generate_features.py           # Part 1
python -m prospectivity.train_models --allow-synthetic   # Part 2
python -m prospectivity.classify_export                  # Part 3/4
python shortfall_features_wip.py      # Part 5 (independent)
python train_shortfall_model.py
```
> `pykrige`, `geopandas`, and `rasterio` carry native/GDAL dependencies. If pip
> fails on Windows, use
> `conda install -c conda-forge geopandas rasterio pykrige`.

### 8.5 Neo4j seeding (without Docker)
```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p <password> -f seed_graph.cypher
```
> `seed_graph.cypher` uses `CREATE`, not `MERGE` — re-running it against a
> non-empty database duplicates nodes. Uncomment the
> `MATCH (n) DETACH DELETE n;` line near the top to reseed cleanly.

---

## 9. Configuration Reference

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `dev` | Environment label |
| `DATABASE_URL` | `postgresql+psycopg://oresight:oresight@localhost:5432/oresight` | Auto-normalises `postgres://` and `postgresql://` prefixes |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:7687` / `neo4j` / `oresight123` | Graph connection |
| `PRODUCTION_EDIT_WINDOW_HOURS` | `48` | Hours a production record stays editable |
| `EQUIPMENT_FLAP_WINDOW_HOURS` | `24` | Flap-detection trailing window |
| `EQUIPMENT_FLAP_THRESHOLD` | `4` | Status changes in window that raise `equipment_flapping` |
| `CORS_ORIGINS` | localhost dev origins | Allowed browser origins |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend → API base |
| `VITE_USE_MOCK` | `false` | Offline mock-data mode |

### ID conventions (shared across graph, CSVs, and DB)
- **Site IDs:** `balaghat`, `nagpur`, `bhandara` — used as `MineSite.id` and as
  `site_id` in every CSV.
- **Equipment IDs:** `eq_<site>_<01-05>` (e.g. `eq_bal_01`), identical between
  Neo4j `Equipment.id` and `equipment_id` in `equipment_downtime_log.csv`.

---

## 10. Quality & Engineering Practices

- **Contract-first API** — `docs/API_CONTRACT.md` plus an exported
  `openapi.json`; the frontend's scenario enum was reconciled against the live
  OpenAPI schema rather than assumed.
- **~152 backend tests** across health, smoke, migrations, production, blasting,
  reports, site notes, weather, equipment history, cascade service, graph/agents,
  error handling, demo, and validation limits.
- **Shared validation bounds** — `app/constants/validation_limits.py` mirrored to
  the frontend via `src/constants/validationLimits.js` and served at
  `GET /config/upload-limits`, so limits are declared once.
- **Migration discipline** — Alembic revisions include explicit merge revisions
  where parallel branches converged; `test_migrations.py` guards them.
- **Defensive frontend** — route-level error boundaries keyed on pathname,
  lazy-loaded Field Intake tabs, skeleton loading states, retry affordances, and
  empty states.
- **Secrets hygiene** — `mask_db_url()` redacts passwords from every startup log line.
- **Decisions documented in-source** — every non-obvious trade-off (why not
  LangGraph, why the cascade never raises, why a feature is NaN rather than
  imputed) is written where the code lives, not lost in chat history.
