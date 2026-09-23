# Handoff — branches `fix/site-aois` + `fix/unify-confidence-scale` (stacked; ready for a visual check, then merge)

> **ZONE CONFIDENCE SCORES DROPPED, ON PURPOSE — NOT A BUG.** `reserve_zones.confidence_score` now comes from the
> same trained-model map layer as the heatmap (one source). Before -> after, e.g. Nagpur North 0.947 -> 0.211,
> Nagpur South 0.957 -> 0.326, Bhandara East 0.919 -> 0.367; site averages now Balaghat 0.24 / Nagpur 0.26 /
> Bhandara 0.36 (KPI 0.29). The old high numbers came from a kriged surface that used synthetic fields and none of
> the real satellite features, so they were disconnected from the map, not evidence of better prospectivity. Do not
> "fix" the lower values. Labels are synthetic; the score is an ensemble agreement index, not a probability of ore.
> Consequence for the UI: every zone now reads "Exploration" with an amber/red badge (<0.7 / <0.4 thresholds
> unchanged); per-cell hotspots reach 0.68-0.87 (see section 4).

## 1. What this branch changed
- **Corrected site boxes.** Nagpur and Bhandara were centred on the cities, 30-50 km from any real MOIL mine;
  Balaghat missed Ukwa. Each AOI is now the bounding box of that site's mines + 5 km.
- **`data/moil_sites.json` is the single source of truth.** `python -m scripts.build_site_aois` copies it into the
  backend and frontend; `--check` verifies the copies.
- **DB seeding repairs wrong geometry** instead of keeping it (seed_dev / import_p2_data).
- **Live satellite data over the corrected boxes** (Earth Engine, nothing simulated).
- Terrain bug fixed: GLO30 `mosaic()` dropped the DEM projection, so slope was 0 and aspect constant.

## 2. Regenerated and correct
Satellite CSV + `meta.json`; frontend satellite JSON; map tiles + `manifest.json` (cloud-masked median mosaics,
no mock); `sites` and `reserve_zones` tables; deposit points; structural lines; confidence surface;
`reserve_zones.geojson`; and (Phase 2) prospectivity feature cache, models, per-site map layers
(`oresight-frontend/public/prospectivity/`) and zone scores.
Prospectivity features: NDVI anomaly = last 90 days vs the same 90 days of year in the 3 prior years; mineral
indices from the Feb-May dry-season composite; terrain at native 30 m. Cells with a missing feature are no-data
(dropped, never imputed). Labels are still synthetic; CV AUCs are chance-level (see `prospectivity/RESULTS.md`).

## 3. Docs (all current)
- `oresight-backend/docs/API_CONTRACT.md` + `docs/openapi.json` regenerated from the rebuilt API
  (`python -m scripts.export_contract`, backend venv). It has an endpoint-sync guard: add every new route to
  `STATUS_TABLE` in that script or it refuses to run. It flips equipment status temporarily, so run
  `rebuild_demo_db` + `backfill_equipment_status_log` afterwards (see section 5).
- `prospectivity/METHODOLOGY.md`: site areas, grid dimensions and feature windows are current.

## 4. Remaining / demo notes
- Merge `fix/site-aois`, then `fix/unify-confidence-scale`, into `main` after a visual check.
- **Re-export the prospectivity layers once** (`python -m prospectivity.classify_export`, offline) so class breaks
  use real Jenks (`jenkspy` is installed). Scores do not change; ~0.15% of cells change band. Then rerun
  `python -m scripts.import_prospectivity_scores` (zone means are unaffected by banding, but keep them in sync).
- **One confidence source (done).** `import_prospectivity_scores.py` reads
  `oresight-frontend/public/prospectivity/{site}.geojson` (`ensemble_confidence_score`) and stores the mean over
  cells inside each zone (NULL if none). The kriging chain (`build_confidence_surface.py`,
  `export_reserve_zones.py`, `train_reserve_classifier.py`, `reserve_classifier.pkl`, `confidence_surface.npz`,
  `data/reserve_zones.geojson`) was deleted. Neo4j `OreZone.confidence_score` (hardcoded seed values, never read)
  was removed from `seed_graph.cypher`, `seed_scenario_a.py` and the report-upload default.
- Demo hotspots (real per-cell scores): Bhandara `bhandara_1680` 0.724 (21.5264, 79.7655, interior, 3/3 models);
  Nagpur `nagpur_258` 0.684 (21.4436, 79.2335, 1.6 km inside); Balaghat: `balaghat_23` 0.867 is only 13 m from the
  west box edge, so prefer interior `balaghat_522` 0.851 (21.8656, 80.1985, 2.0 km inside, 3/3 models).

## 5. Known issues
- `tests/test_smoke.py::test_simulate_after_differs_from_before` is xfail pending Tasks 2/3: the shortfall model is
  non-monotonic in downtime (baseline: `equipment_down` points the right way on only 212/365 days at Balaghat).
- NDVI tile week 1 (Aug 26 - Sep 2) is `no_data`: all six scenes were 97-100% cloud.
- Balaghat has 17.6% no-data map cells (no clear Sentinel-2 pixel in a window); Bhandara 4.4%, Nagpur 0.03%.
- `/equipment/metrics` windows end at the data's last day (Aug 24-30), not today; availability is ~99.5%+ everywhere
  (seed data has few downtime events).

## 6. Test suite warning
The full backend suite writes to the demo DB. After ANY full run, rerun `python -m scripts.rebuild_demo_db` and
`python -m scripts.backfill_equipment_status_log` (from `oresight-backend/`).
Order matters: `rebuild_demo_db` -> tests -> `rebuild_demo_db` again (`export_contract` also leaves
status-flip history that breaks `test_equipment_status_down_creates_risk_event` until the DB is rebuilt).
Fast tests that are safe: `python -m pytest prospectivity gee_pipeline gis -q`.

## 7. GEE setup (for whoever runs GEE steps next)
- `gee_pipeline/.env` needs `EE_PROJECT=manganex-509408` and `EE_SERVICE_ACCOUNT_JSON=<path to key file>`, kept
  OUTSIDE git. Never commit the key (`.env` is gitignored).
- The service account (`earth-engine-runner@manganex-509408.iam.gserviceaccount.com`) needs Earth Engine
  Resource Viewer, Resource Writer (tile PNGs use `thumbnails.create`) and Service Usage Consumer.
- Run only ONE GEE job at a time; concurrent jobs cause 429s. Smoke-test before any full run.
- Regenerate: CSV `python gee_pipeline/export_site_daily_climate.py --start 2025-01-01`; frontend JSON
  `python gee_pipeline/export_frontend_satellite_json.py`; tiles `python -m gis.generate_tiles` (then copy
  `gis/tiles/*` to `oresight-frontend/public/tiles/`); prospectivity `python -m prospectivity.feature_cache --force`
  (~15 min), `python -m prospectivity.train_models --allow-synthetic`, `python -m prospectivity.classify_export`;
  zone scores from `oresight-backend/`: `python -m scripts.import_prospectivity_scores`
  (use the backend `venv`, it needs geoalchemy2; must run AFTER classify_export, it reads its GeoJSONs).
