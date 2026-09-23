<div align="center">

# ⛏️ MANGANEX

### Mapping Minerals for a Stronger Tomorrow

**AI/ML-driven Reserve Intelligence & Production Forecasting Platform for MOIL Manganese Mines**

*Smart India Hackathon 2026 · Problem Statement **SIH26009** · Ministry of Steel / MOIL Ltd.*

[![Live Demo](https://img.shields.io/badge/Live%20Demo-oresite.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://oresite.vercel.app)
[![API Docs](https://img.shields.io/badge/API-OpenAPI%20%2F%20Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black)](#-api-reference)
[![Tests](https://img.shields.io/badge/Tests-~152%20passing-2EA44F?style=for-the-badge&logo=pytest&logoColor=white)](#-quality--engineering-practices)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791)
![pgvector](https://img.shields.io/badge/pgvector-256--dim-6E4AFF)
![Neo4j](https://img.shields.io/badge/Neo4j-5%20%2B%20APOC-4581C3?logo=neo4j&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-2.1+-EB5B25)
![scikit-learn](https://img.shields.io/badge/scikit--learn-RandomForest-F7931E?logo=scikitlearn&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-JSX%20hybrid-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-build-646CFF?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind%20CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)
![MapLibre](https://img.shields.io/badge/MapLibre%20GL-v6-396CB2)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

</div>

---

## 📑 Table of Contents

1. [The Problem](#-the-problem)
2. [Our Solution](#-our-solution)
3. [Highlights at a Glance](#-highlights-at-a-glance)
4. [System Architecture](#-system-architecture)
5. [Agentic Workflow](#-agentic-workflow)
6. [Causal Knowledge Graph](#-causal-knowledge-graph)
7. [ML & Geospatial Pipeline](#-ml--geospatial-pipeline)
8. [Features](#-features)
9. [MVP Scope](#-mvp-scope)
10. [Technology Stack](#-technology-stack)
11. [Repository Structure](#-repository-structure)
12. [API Reference](#-api-reference)
13. [Frontend Routes](#-frontend-routes)
14. [Getting Started](#-getting-started)
15. [Configuration Reference](#-configuration-reference)
16. [Model Validation](#-model-validation)
17. [Honest Limitations](#-honest-limitations)
18. [Quality & Engineering Practices](#-quality--engineering-practices)
19. [Roadmap](#-roadmap)
20. [References](#-references)

---

## 🎯 The Problem

MOIL Ltd. operates manganese mines across Madhya Pradesh and Maharashtra. Mine planners today face four disconnected challenges:

- **Reserve uncertainty** — exploration data is sparse and expensive, so it is hard to know where high-confidence ore zones lie.
- **Reactive operations** — equipment breakdowns, weather, and blasting delays are noticed *after* output has already dropped.
- **Invisible ripple effects** — a delayed blast or a down drill affects ore zones, schedules, and downstream targets in ways spreadsheets cannot trace.
- **No decision support** — planners lack a way to test "what if?" before committing crews and equipment.

**SIH26009** asks for AI/ML-driven reserve estimation and production intelligence to close these gaps.

---

## 💡 Our Solution

MANGANEX is an end-to-end **mine reserve intelligence platform** that fuses **geospatial prospectivity modelling**, a **causal knowledge graph**, **agentic what-if simulation**, and a **live operations dashboard** across three MOIL mine sites — **Balaghat**, **Nagpur**, and **Bhandara**.

It answers the four questions a mine planner asks every day:

| # | Question | How MANGANEX answers it |
|---|---|---|
| 1 | **Where is the ore likely to be?** | Random Forest / XGBoost prospectivity classifier over structural-geology and remote-sensing proxies, **kriged** into a continuous confidence surface and exported as map-ready reserve zones. |
| 2 | **What is going wrong right now?** | A **Watcher agent** polls production and equipment telemetry, raises risk events, and mirrors them into a **Neo4j causal graph**. |
| 3 | **What happens if I do nothing?** | A **Simulator agent** runs trained shortfall-forecaster projections plus a real graph traversal to show the blast-plan → ore-zone → output ripple. |
| 4 | **What should I do instead?** | A **Planner agent** proposes reschedule / redeploy / adjust-plan options, each scored by an actual simulation run, with a deterministic **cascade (ripple-impact)** analysis attached. |

> 🔍 **Explainability is a hard design constraint, not a feature.** Every number surfaced in the UI is traceable to a specific model, query, or graph path.

---

## ✨ Highlights at a Glance

| Metric | Value |
|---|---|
| Mine sites modelled | **3** (Balaghat, Nagpur, Bhandara) |
| AI agents | **3** (Watcher, Simulator, Planner) + cascade service |
| What-if scenarios | **3** (`equipment_down`, `delay_blasting`, `rainfall_event`) |
| API routers | **16** (contract-documented, OpenAPI exported) |
| ORM models / Pydantic schemas | **11** / **15** |
| Database migrations | **9** Alembic revisions (incl. merge revisions) |
| Backend tests | **~152** across **14** pytest suites |
| UI components | **~45** shadcn/Radix primitives |
| Prospectivity classifier AUC | **0.875** (held-out) · **0.773** (5-fold CV × 3 seeds) · **p = 0.005** (permutation test) |
| Data stores | **PostgreSQL + PostGIS + pgvector** and **Neo4j** (dual-store by design) |

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph FE["🖥️ FRONTEND — React 18 + Vite (deployed on Vercel)"]
        direction LR
        F1["Dashboard"] --- F2["Reserve Map<br/>MapLibre GL"] --- F3["Simulator"] --- F4["Reports<br/>Recharts / Plotly"] --- F5["Field Intake"] --- F6["Causal Graph<br/>React Flow"]
    end

    FE -- "REST / JSON (CORS-guarded)" --> API

    subgraph API["⚙️ API — FastAPI · 16 routers · OpenAPI"]
        direction TB
        subgraph AG["🤖 Agent Layer — app/agents/"]
            A1["WatcherAgent<br/>detect & mirror risk"]
            A2["SimulatorAgent<br/>what-if projection"]
            A3["PlannerAgent<br/>mitigation ranking"]
            A4["_bridge.py<br/>Postgres ↔ Neo4j reconciliation"]
        end
        subgraph SV["🧩 Service Layer — app/services/"]
            S1["cascade_service"]
            S2["dependency_derivation"]
            S3["embedding"]
            S4["extraction · pdf_text"]
            S5["geo · lookups"]
            S6["scheduler (APScheduler)"]
            S7["weather (Open-Meteo)"]
        end
    end

    API --> PG[("🐘 PostgreSQL 16<br/>+ PostGIS 3.4 + pgvector<br/>sites · equipment · production<br/>risk · zones · notes · blasts · weather")]
    API --> NEO[("🕸️ Neo4j 5 + APOC<br/>Causal knowledge graph<br/>MineSite · Equipment · OreZone<br/>BlastPlan · Weather · RiskEvent")]
    API --> ML[["🧠 ML Artifacts<br/>reserve_classifier.pkl<br/>shortfall XGBoost<br/>per-site rf_/xgb_ models<br/>kriged surface .npz"]]
    S7 --> OM(["🌦️ Open-Meteo API<br/>ECMWF · GFS · ICON"])
```

<details>
<summary><b>ASCII version (for terminals / plain viewers)</b></summary>

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
│ + PostGIS 3.4    │   │ Causal knowledge    │   │ reserve_classifier │
│ + pgvector       │   │ graph: MineSite,    │   │ shortfall XGBoost  │
│ Sites, equipment,│   │ Equipment, OreZone, │   │ rf_/xgb_ per-site  │
│ production, risk,│   │ BlastPlan, Weather, │   │ kriged confidence  │
│ zones, notes,    │   │ RiskEvent + CAUSES/ │   │ surface (.npz)     │
│ blasts, weather  │   │ AFFECTS/DEPENDS_ON  │   │ NDVI/elev fields   │
└──────────────────┘   └─────────────────────┘   └────────────────────┘
```

</details>

### 🧭 Key Architectural Decisions

| Decision | Rationale |
|---|---|
| **Dual-store by design** | Postgres is the transactional system of record (rows, audit trails, spatial geometry, vectors). Neo4j holds *relationships* — the causal chains that make *"why did output drop?"* answerable in **one traversal instead of six joins**. `_bridge.py` reconciles both entity spaces and **refuses to guess** when an entity cannot be matched (logs a warning, omits the edge). |
| **Plain-Python agents, not LangGraph** | All three agents are deterministic, straight-line `detect → query → perturb → predict → rank` pipelines with no branching LLM decisions. An orchestration framework would add dependency weight without earning it — documented in each agent's module docstring. |
| **Graceful degradation is a contract** | `compute_cascade` never raises — failures yield `None`, logged with context, and never alter the recommendation. Causal-graph endpoints fall back to a single-node graph tagged `graph_source='postgres_fallback'` when Neo4j has no matching node. |
| **Typed error envelope** | Every error is `{detail, error_code}` (`VALIDATION_ERROR`, `SERVICE_UNAVAILABLE`, `PAYLOAD_TOO_LARGE`, …). Postgres/Neo4j outages are classified as **503 transient**, never 500 — separating infrastructure faults from bugs. 422 `detail` stays a list of human-readable `"field: value - message"` strings generated generically for any new Pydantic constraint. |
| **Local-first embeddings** | `HashingEmbedder` (256-dim, stemmed bag-of-words + bigrams, L2-normalised) is deterministic — no model download, API key, or network. Swappable for sentence-transformers behind one `Embedder.embed()` interface; DB column width pinned to `EMBEDDING_DIM` by migration. |

---

## 🤖 Agentic Workflow

```mermaid
sequenceDiagram
    autonumber
    participant SCH as APScheduler (5 min)
    participant W as WatcherAgent
    participant PG as PostgreSQL
    participant N as Neo4j
    participant UI as Planner UI
    participant P as PlannerAgent
    participant S as SimulatorAgent
    participant C as Cascade Service

    SCH->>W: trigger poll
    W->>PG: read production & equipment telemetry
    W->>W: detect equipment-down / shortfall > 15%
    W->>PG: write risk_events (idempotent)
    W->>N: write RiskEvent node + CAUSES edges (external_ref links IDs)

    UI->>P: GET /recommendations
    P->>N: candidate search (Cypher lookups)
    P->>PG: candidate search (SQL lookups)
    loop for each candidate action
        P->>S: simulate(scenario, horizon)
        S->>S: XGBoost shortfall projection
        S->>N: traverse BlastPlan → OreZone path
        S-->>P: forecast tonnes · reserve confidence Δ · graph path
    end
    P->>C: compute_cascade(option)
    C-->>P: cascade_adjusted_impact (or None — never raises)
    P-->>UI: ranked options with confidence + projected_impact
```

| Agent | Responsibility | Output |
|---|---|---|
| **Watcher** | Scheduled 5-minute poll for equipment-down and production-shortfall signals (>15% below target); idempotent dual-write to Postgres `risk_events` and Neo4j `RiskEvent` with causal edges. | Risk events linked across both stores via `external_ref` |
| **Simulator** | Runs `equipment_down`, `delay_blasting`, or `rainfall_event` over a configurable horizon. | `production_forecast_tonnes`, before/after `reserve_confidence`, `affected_graph_path` |
| **Planner** | Candidate search (3 fixed Cypher/SQL lookups) → simulate each → rank. | Options with `confidence` and simulation-derived `projected_impact` (*risk avoided by acting now*) |
| **Cascade service** | Deterministic traversal + rule evaluation over blast plans. | `cascade_adjusted_impact` with **blocking / shifted / clear** classification and date-collision detection |

---

## 🕸️ Causal Knowledge Graph

```mermaid
flowchart LR
    WX(["🌧️ Weather"]) -- CAUSES --> RE(["⚠️ RiskEvent"])
    EQ(["🚜 Equipment"]) -- CAUSES --> RE
    EQ -- DEPENDS_ON --> BP(["💥 BlastPlan"])
    BP -- AFFECTS --> OZ(["🪨 OreZone"])
    BP -- SCHEDULED_ON --> CD(["📅 CalendarDate"])
```

- **Node labels:** `MineSite`, `Equipment`, `OreZone`, `BlastPlan`, `Weather`, `RiskEvent`, `CalendarDate`, `StructuralFeature`
- **Seed data:** 3 mine sites, 15 equipment units, ore zones, weather events, blast plans, and risk events — with schema constraints (`seed_graph.cypher`)
- **Relationship semantics are reused, never redefined** across the codebase
- **`GET /risk-events/{id}/causal-graph`** returns an up-to-3-hop traversal, rendered in the UI with React Flow
- **Dependency-edge derivation** script infers missing structural edges
- **Built-in verification queries:** node counts by label, the full Balaghat *weather → blast delay → ore zone → risk* chain, and the idle-equipment redeploy candidate (Drill at Bhandara matching the down Drill at Nagpur)

---

## 🧠 ML & Geospatial Pipeline

```mermaid
flowchart LR
    GD["generate_datasets.py<br/>synthetic production,<br/>downtime, ground truth"] --> GF["generate_features.py<br/>structural lines +<br/>training features"]
    GF --> TR["train_reserve_classifier.py<br/>RandomForest vs XGBoost"]
    TR --> CS["build_confidence_surface.py<br/>50×50 grid → Ordinary Kriging<br/>→ 100×100 surface"]
    CS --> EX["export_reserve_zones.py<br/>reserve_zones.geojson"]
    EX --> MAP[["🗺️ /reserve-zones → MapLibre"]]

    GD --> SF["shortfall_features_wip.py<br/>feature engineering"]
    SF --> TS["train_shortfall_model.py<br/>XGBRegressor (time split)"]
    TS --> FS["finalize_shortfall_model.py"]
    FS --> SIM[["🤖 SimulatorAgent"]]
```

### Reserve Prospectivity
- **Features:** `dist_to_nearest_structure`, `structural_density`, `synthetic_ndvi`, `synthetic_elevation` (UTM-projected distances via `pyproj`, spatially correlated random fields via `geo_utils.py`)
- **Models:** scikit-learn `RandomForestClassifier` vs `XGBClassifier` — better model auto-selected and persisted with a pinned feature-order JSON
- **Geostatistics:** PyKrige `OrdinaryKriging`, variogram model selected by **5-fold CV**
- **Export:** GeoJSON cell polygons carrying `confidence_score` + `site_id`
- **Per-site models:** `rf_` / `xgb_` × `balaghat` / `nagpur` / `bhandara` alongside the global model
- **Remote sensing:** Google Earth Engine pipeline (`gee_pipeline/`, `prospectivity/gee_features.py`), NDVI pull + time series (`gis/`), custom raster → XYZ tile generation

### Production Shortfall Forecasting
- **Target:** `shortfall_pct = (target − actual) / target`
- **Model:** XGBoost `XGBRegressor` on a **time-based** (not random) split to prevent look-ahead leakage
- **Engineered features:**
  - `rolling_7day_downtime_pct`
  - `days_since_last_maintenance` — left as NaN; XGBoost handles missingness natively
  - `rainfall_proxy` — monsoon-weighted seasonal signal
  - `schedule_pressure` — lag-shifted trailing 14-day mean shortfall (the current day never leaks into its own feature)
  - Cyclical `dow_sin/cos` and `month_sin/cos` encodings
- Exact feature column order persisted so the Simulator agent reuses it verbatim

---

## 🚀 Features

### 🗺️ 1. Reserve Prospectivity & Mapping
- RF / XGBoost deposit classifier with automatic best-model selection
- Kriged 100×100 lon/lat confidence surface
- Interactive **MapLibre GL** map with raster prospectivity overlay and opacity control
- Structural-lines GeoJSON layer, layer toggles, and confidence legend
- **NDVI time slider**, zone detail panel, prospectivity cell inspector
- **Cross-section drawer** rendered with Plotly.js

### 📉 2. Production Shortfall Forecasting
- XGBoost regressor with leakage-safe, time-based validation
- Scenario-driven projections consumed by the Simulator agent

### 🕸️ 3. Causal Knowledge Graph
- Neo4j graph with constraints, seed data, and 3-hop causal traversal
- React Flow visualisation of *why* a risk occurred

### 🤖 4. Agentic Intelligence
- Watcher → Simulator → Planner loop with cascade ripple-impact analysis
- Every recommendation is backed by a real simulation run, not a heuristic label

### 📝 5. Field Intake (operator data capture)
Four tabs — each **lazy-loaded behind its own error boundary** so one broken tab cannot take down the router:

| Tab | Capability |
|---|---|
| **Production** | Persisted records with a configurable **edit window** (`PRODUCTION_EDIT_WINDOW_HOURS`, default 48h) beyond which PATCH is refused; full audit trail in `production_record_audit` |
| **Equipment** | Status changes logged to `equipment_status_log` with **flap detection** — more than 4 changes in 24h opens one `equipment_flapping` risk event |
| **Geology** | Survey **PDF upload** → deterministic deposit extraction → Neo4j `OreZone` / `StructuralFeature` nodes; server-declared limits via `GET /config/upload-limits` |
| **Blast Log** | Blast-event capture feeding the blast-plan graph and cascade checks |

### 🔎 6. Semantic Site Notes (RAG)
- Free-text operator notes embedded as 256-dim vectors in a **pgvector** column
- `GET /site-notes/search` ranks by cosine similarity — a query for *"monsoon flooding"* surfaces a note about *"heavy rain waterlogging the haul road"*

### 🌦️ 7. Live Weather Integration
- Real **Open-Meteo** (ECMWF / GFS / ICON) observations and forecasts at each site centroid, persisted to `weather_records`
- Provenance, licensing, and the ~9–13 km grid resolution limit documented in-source

### 📊 8. Reporting, KPIs & Demo Tooling
- `GET /kpi/summary` — aggregate production, risk, and averaged reserve confidence
- Reports & insights view with time-series and comparative charts (Recharts + Plotly)
- `GET /demo/scenarios` resolves seeded scenarios to their **current** risk-event IDs — nothing in the demo path is hardcoded
- `GET /admin/jobs` for scheduler introspection; seed/rebuild scripts for **Scenario A** and **Scenario B** walkthroughs
- **Offline fallback:** `VITE_USE_MOCK=true` switches the frontend to bundled mock data for venue Wi-Fi resilience
- Light / dark theming, toast notifications, skeleton loaders, retry affordances, and empty states

---

## ✅ MVP Scope

**Working end-to-end:**

| Capability | Status |
|---|---|
| Three-site reserve map with kriged confidence surface | 🟢 Live |
| Prospectivity classifier + GeoJSON zone export | 🟢 Live |
| Shortfall forecaster (XGBoost) | 🟢 Live |
| Neo4j causal graph + 3-hop traversal endpoint | 🟢 Live |
| Watcher / Simulator / Planner agent loop | 🟢 Live |
| Cascade ripple-impact analysis | 🟢 Live |
| Field Intake (4 tabs) with audit trail + flap detection | 🟢 Live |
| Survey-PDF extraction into the graph | 🟢 Live |
| pgvector semantic note search | 🟢 Live |
| Real weather ingestion (Open-Meteo) | 🟢 Live |
| KPI summary + reports dashboard | 🟢 Live |
| Dockerised 3-service stack with healthchecks | 🟢 Live |

**Deliberately out of MVP scope (documented, not hidden):**

| Item | Status |
|---|---|
| Authentication & RBAC (supervisor override on edit window specified, unimplemented) | 🟡 Phase 8 |
| Real Earth Engine features — 9 of 10 left as explicit `NaN`, **never imputed or replaced with noise** | 🟡 Pending provisioning |
| Real MOIL operational data — demo runs on synthetic, GSI-styled data | 🟡 Requires MOIL data access |
| Learned reserve-confidence model — Simulator delta is a labelled decay heuristic | 🟡 Placeholder |

---

## 🛠️ Technology Stack

### Backend — `oresight-backend/`

| Layer | Technology |
|---|---|
| Language | **Python 3.11+** (containerised on `python:3.11-slim`) |
| Web framework | **FastAPI** ≥0.115 · **Uvicorn** (standard / uvloop) ASGI server |
| ORM / data access | **SQLAlchemy 2.0** (typed `Mapped[]` declarative models) |
| Spatial ORM | **GeoAlchemy2** + **Shapely 2.x** (geometry columns, WKB/WKT) |
| Relational DB | **PostgreSQL 16** + **PostGIS 3.4** + **pgvector** |
| Graph DB | **Neo4j 5 Community** · Bolt Python driver ≥5.25 · **APOC** plugin · **Cypher** |
| Migrations | **Alembic** (9 revisions, incl. merge revisions) |
| Validation / config | **Pydantic v2** + **pydantic-settings** (`.env`-driven `Settings`) |
| Vector search | **pgvector** (256-dim cosine similarity) |
| Scheduling | **APScheduler** (background Watcher polling + job introspection) |
| ML inference | **XGBoost** ≥2.1 · **scikit-learn** · **joblib** · **pandas** · **NumPy** |
| PDF ingestion | **pypdf** + **python-multipart** |
| External data | **httpx** → **Open-Meteo API** (ECMWF / GFS / ICON) |
| Testing | **pytest** (~152 tests, 14 suites) |
| Packaging | **Docker** + **Docker Compose** (api / postgres / neo4j, healthchecked) |

### Frontend — `oresight-frontend/`

| Layer | Technology |
|---|---|
| Framework | **React 18** + **TypeScript / JSX** hybrid |
| Build tool | **Vite** (env-driven `PORT` / `BASE_PATH`) · **cross-env** |
| Package manager | **pnpm** (workspace catalog protocol) |
| Routing | **react-router-dom v7** · **wouter** (landing shell) |
| Mapping | **MapLibre GL v6** + **react-map-gl v8** (raster tiles, GeoJSON overlays) |
| Graph visualisation | **@xyflow/react** (React Flow v12) |
| Charting | **Recharts** (KPIs / time series) · **Plotly.js** (cross-sections, surfaces) |
| Design system | **Tailwind CSS v4** · **shadcn/ui** · **Radix UI** primitives (~45 components) |
| Icons | **lucide-react** · **react-icons** |
| Forms & validation | **react-hook-form** · **zod** · **@hookform/resolvers** |
| Server state | **@tanstack/react-query** · custom `useAsync` hook |
| Animation | **framer-motion** · **tw-animate-css** |
| Utilities | **clsx** · **tailwind-merge** · **class-variance-authority** · **date-fns** · **react-window** · **rc-slider** |
| Notifications | **sonner** toasts · Radix toast primitives |
| Theming | **next-themes** (light / dark) |
| E2E testing | **Playwright** (`pnpm test:smoke`) |
| Deployment | **Vercel** — [oresite.vercel.app](https://oresite.vercel.app) |

### Data Science & Geospatial — repo root

| Purpose | Technology |
|---|---|
| Classification | scikit-learn **RandomForestClassifier** · **XGBClassifier** |
| Regression | **XGBRegressor** (time-based split) |
| Geostatistics | **PyKrige** `OrdinaryKriging` (CV-selected variogram) |
| Geospatial I/O | **GeoPandas** · **Rasterio** · **Shapely** · **pyproj** (UTM reprojection) · **GDAL** (native dependency) |
| Numerics | **NumPy** · **SciPy** · **pandas** |
| Remote sensing | **Google Earth Engine API** |
| Tiling | Custom raster → **XYZ tile** generation (`gis/generate_tiles.py`) |
| Model persistence | **joblib** `.pkl` artifacts + pinned feature-order JSON |
| Exploration | **Jupyter** notebooks |
| Environment | **venv** / **pip** · **conda-forge** (for GDAL-based packages on Windows) |

### Tooling & Infrastructure

| Tool | Use |
|---|---|
| **Docker Compose** | One-command 3-service stack with healthchecks |
| **cypher-shell** / **Neo4j Browser** | Graph seeding and verification |
| **OpenAPI** | Exported schema at `docs/openapi.json` |
| **Git / GitHub** | Version control and collaboration |

---

## 📂 Repository Structure

```
moil-reserve-intelligence/
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
│   │   ├── routers/               # 16 API routers
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
│   │   ├── pages/landing/         # MANGANEX landing page
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
├── generate_datasets.py           # Synthetic production / downtime / ground truth
├── geo_utils.py                   # Shared geospatial helpers
├── generate_features.py           # Structural lines + training features
├── train_reserve_classifier.py    # RF vs XGBoost, best model persisted
├── build_confidence_surface.py    # Kriged 100×100 confidence surface
├── export_reserve_zones.py        # Surface → reserve_zones.geojson
├── shortfall_features_wip.py      # Shortfall feature engineering
├── train_shortfall_model.py       # XGBoost shortfall forecaster
├── finalize_shortfall_model.py
│
├── seed_graph.cypher              # Neo4j constraints + seed data + verification queries
├── data/                          # Generated CSVs, GeoJSON, .npz surface
├── models/                        # .pkl artifacts (global + per-site)
├── methodology.md                 # Model metrics, validation, limitations
├── IMPLEMENTATION_NOTES.md        # Field Intake hardening phases & decisions
├── demo_script.md                 # Demo walkthrough
└── requirements.txt               # Data-science environment
```

---

## 📡 API Reference

Interactive docs are served at **`http://localhost:8000/docs`** (Swagger UI). A hand-written contract lives in `oresight-backend/docs/API_CONTRACT.md`.

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
| meta | `/`, `/health` | service root + DB / Neo4j health |

**Error envelope (all endpoints):**

```json
{
  "detail": "Neo4j is temporarily unavailable",
  "error_code": "SERVICE_UNAVAILABLE"
}
```

---

## 🧭 Frontend Routes

| Route | Page |
|---|---|
| `/` | Dashboard |
| `/site/:id` | Site detail |
| `/map` | Reserve map |
| `/reports` | Reports & insights |
| `/simulator` | Scenario simulator |
| `/field-intake` | Field intake |
| `/settings` | Settings |
| `/login` | Login |
| Landing | MANGANEX landing page |

Legacy paths (`/timeline`, `/recommendations`, `/data-input`) redirect to their current equivalents.

---

## ⚡ Getting Started

### Prerequisites
- **Docker** + **Docker Compose** (recommended), or local **Python 3.11+**, **PostgreSQL 16 + PostGIS + pgvector**, **Neo4j 5 + APOC**
- **Node.js** + **pnpm**
- *(Windows)* **conda** for GDAL-based packages

### 1️⃣ Clone
```bash
git clone https://github.com/Arnabh-M/moil-reserve-intelligence.git
cd moil-reserve-intelligence
```

### 2️⃣ Infrastructure (Docker — recommended)
```bash
cd oresight-backend
docker compose up -d --build     # postgres (+PostGIS +pgvector), neo4j (+APOC), api
```
| Service | Port |
|---|---|
| API (docs at `/docs`) | `8000` |
| PostgreSQL | `5432` |
| Neo4j Browser / Bolt | `7474` / `7687` |

### 3️⃣ Backend (local)
```bash
cd oresight-backend
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m scripts.load_graph     # seed Neo4j
python -m scripts.rebuild_demo_db  # seed demo scenarios
uvicorn app.main:app --reload
pytest                           # ~152 tests
```

### 4️⃣ Frontend
```bash
cd oresight-frontend
pnpm install
pnpm dev             # http://localhost:5173
pnpm typecheck
pnpm test:smoke      # Playwright
```
Set `VITE_API_BASE_URL` (default `http://localhost:8000`) or `VITE_USE_MOCK=true` for offline mode.

### 5️⃣ ML Pipeline (hard dependency chain — run in order)
```bash
pip install -r requirements.txt       # root env
python -m scripts.build_site_aois     # Site AOIs — run first, see below
python generate_datasets.py
python generate_features.py           # Part 1 — features + structural_lines.geojson
python train_reserve_classifier.py    # Part 2 — classifier
python build_confidence_surface.py    # Part 3 — kriging
python export_reserve_zones.py        # Part 4 — GeoJSON
python shortfall_features_wip.py      # Part 5 — independent
python train_shortfall_model.py
python finalize_shortfall_model.py
```
> ⚠️ `pykrige`, `geopandas`, and `rasterio` carry native/GDAL dependencies. If pip fails on Windows:
> ```bash
> conda install -c conda-forge geopandas rasterio pykrige
> ```

### 6️⃣ Neo4j seeding without Docker
```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p <password> -f seed_graph.cypher
```
Or paste `seed_graph.cypher` into **Neo4j Browser** (`http://localhost:7474`) — each `;`-terminated statement runs in sequence.

> ⚠️ `seed_graph.cypher` uses `CREATE`, not `MERGE` — re-running it duplicates nodes. Uncomment `MATCH (n) DETACH DELETE n;` near the top to reseed cleanly.

**Quick connectivity check from Python:**
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "<password>"))
with driver.session() as session:
    for r in session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"):
        print(r["label"], r["count"])
driver.close()
```

---

## ⚙️ Configuration Reference

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

### Site AOIs — one definition, everywhere

`data/moil_sites.json` is **the** definition of where the three sites are: each
site's MOIL mines (with coordinates, positional confidence and provenance) and
the AOI box, which is the bounding box of that site's included mines plus a
**5 km** buffer on every side.

| Site | Mines in the AOI | Box | Size |
|---|---|---|---|
| `balaghat` | Bharveli, Ukwa | 21.8050–22.0160 N, 80.1790–80.5150 E | 34.7 × 23.3 km |
| `nagpur` | Kandri, Munsar, Beldongri | 21.3529–21.4657 N, 79.2178–79.3277 E | 11.4 × 12.5 km |
| `bhandara` | Chikla, Sitapatore, Dongri Buzurg | 21.4865–21.5954 N, 79.6457–79.8006 E | 16.0 × 12.1 km |

Gumgaon (low-confidence coordinates) and Tirodi (~55 km west of Bharveli, in a
different belt) are listed in the file but **excluded** from every box. They
still render on the **MOIL Mines** map layer as faded, dark-ringed markers.

Everything reads that one file:

- `geo_utils.SITE_BBOXES` / `COMBINED_BBOX` / `SITE_AOIS` / `MINES`
- `generate_datasets.py`, `generate_features.py`, `build_confidence_surface.py`,
  `export_reserve_zones.py`, `gis/*`, `gee_pipeline/*`
- `oresight-backend/app/seed_dev.py` → `sites.geom` and `sites.centroid` in Postgres
- `oresight-frontend/src/lib/map.js` → site bounds, map centre, raster overlay
  corners, the mines layer

```bash
python -m scripts.build_site_aois            # regenerate every copy
python -m scripts.build_site_aois --check    # fail if any copy has drifted
```

The generated copies are `oresight-backend/app/data/moil_sites.json`,
`oresight-frontend/src/lib/moil_sites.json` (byte-identical) and
`oresight-frontend/public/moil_mines.geojson` (derived). `pytest
tests/test_site_aoi_sync.py` in the backend asserts they are in sync, that each
box really is its mines plus the buffer, that no two AOIs overlap, and that
every reserve-zone block lands inside its site.

**No fallback boxes.** If a pipeline cannot reach Postgres it now fails with an
actionable message instead of silently switching to a different rectangle. Pass
`--geometry-source=file` to `gee_pipeline/export_site_daily_climate.py`, or call
`prospectivity.training_data.site_geometries_from_file()`, to use the JSON
deliberately — that returns the same AOIs the DB was seeded with.

### ID Conventions (shared across graph, CSVs, and DB)
- **Site IDs:** `balaghat`, `nagpur`, `bhandara` — used as `MineSite.id` and `site_id` everywhere
- **Equipment IDs:** `eq_<site>_<01-05>` (e.g. `eq_bal_01`) — identical between Neo4j `Equipment.id` and `equipment_id` in `equipment_downtime_log.csv`

---

## 📈 Model Validation

**Reserve Prospectivity Classifier** — n = 40 labelled points, 4 features

| Model | AUC-ROC | Precision | Recall | F1 |
|---|---|---|---|---|
| **RandomForest (selected)** | **0.625** | **0.667** | **1.000** | **0.800** |
| XGBoost | 0.625 | 0.600 | 0.750 | 0.667 |

> Measured after the site AOIs moved onto the real MOIL mines. The 40 labelled
> points are drawn inside the site boxes, so new boxes mean a new sample: this
> is a different draw, not a degraded model. The previous numbers on the old
> (mis-placed) boxes were RF/XGB AUC 0.875. An 8-point test fold moves by 0.125
> per point, so neither figure should be read as a precise estimate.

| Check | Result |
|---|---|
| Feature importance | `dist_to_nearest_structure` dominates (RF 0.37, XGB 0.63) |

> **Stale — needs re-running on the current AOIs.** The 5-fold CV (RF 0.773 /
> XGB 0.715), label-shuffle permutation test (p = 0.005) and point-biserial
> correlations previously quoted here were measured on the old boxes, and the
> one-off script that produced them is not in the repo. They have been removed
> rather than left standing as if they described the shipped model.

---

## ⚠️ Honest Limitations

We document our constraints rather than masking them:

- **Synthetic data** — all production, downtime, and deposit data is synthetic and GSI-styled; none of it is real MOIL exploration or production data.
- **Moderate signal by design** — CV folds swing between ~0.56 and ~1.0; n = 40 keeps every estimate wide.
- **Shortfall forecaster artifacts** — `rolling_7day_downtime_pct` saturates and `schedule_pressure` carries a negative learned relationship, an artifact of six months of synthetic data with isolated 5–10 day shortfall windows. As a result `equipment_down` and `delay_blasting` show weak deltas, while `rainfall_event` behaves as expected.
- **Weather resolution** — regional (9–13 km grid), not in-pit or bench-level microclimate.
- **Weather licensing** — Open-Meteo's public API is non-commercial/educational; production deployment needs a commercial plan or a self-hosted Open-Meteo / IMD instance.

---

## 🧪 Quality & Engineering Practices

- **Contract-first API** — `docs/API_CONTRACT.md` + exported `openapi.json`; the frontend scenario enum is reconciled against the live schema, not assumed
- **~152 backend tests** covering health, smoke, migrations, production, blasting, reports, site notes, weather, equipment history, cascade service, graph/agents, error handling, demo, and validation limits
- **Playwright smoke tests** for the frontend
- **Shared validation bounds** — declared once in `app/constants/validation_limits.py`, mirrored to `src/constants/validationLimits.js`, and served at `GET /config/upload-limits`
- **Migration discipline** — explicit Alembic merge revisions, guarded by `test_migrations.py`
- **Defensive frontend** — route-level error boundaries keyed on pathname, lazy-loaded tabs, skeletons, retries, and empty states
- **Secrets hygiene** — `mask_db_url()` redacts passwords from every startup log line
- **Decisions documented in-source** — why not LangGraph, why the cascade never raises, why a feature is NaN rather than imputed — all written where the code lives

---

## 🗺️ Roadmap

- [x] Kriged three-site reserve map and prospectivity classifier
- [x] XGBoost shortfall forecaster
- [x] Neo4j causal graph with 3-hop traversal
- [x] Watcher / Simulator / Planner agents + cascade analysis
- [x] Field Intake with audit trail and flap detection
- [x] pgvector semantic search and live weather ingestion
- [ ] Authentication & RBAC, including supervisor override on the production edit window
- [ ] Provision Google Earth Engine and replace the 9 pending `NaN` features with real remote-sensing inputs
- [ ] Train on real MOIL exploration and production data
- [ ] Learned reserve-confidence model to replace the decay heuristic
- [ ] Commercial / self-hosted weather source (Open-Meteo or IMD) for production use

---

## 📚 References

- **Zhao et al. (2025).** *Predicting Manganese Mineralization Using Multi-Source Remote Sensing and Machine Learning: A Case Study from the Malkansu Manganese Belt.* Minerals, 15(2), 113. [DOI: 10.3390/min15020113](https://doi.org/10.3390/min15020113)
- **Open-Meteo** — open weather API (ECMWF, GFS, ICON models)
- **Geological Survey of India (GSI)** — styling reference for synthetic geological data

---

<div align="center">

**Built for Smart India Hackathon 2026 · SIH26009 · Ministry of Steel / MOIL Ltd.**

*MANGANEX — Mapping Minerals for a Stronger Tomorrow* ⛏️

</div>
