# Handoff — branch `fix/site-aois` (Phases 1-3 done; 4-5 remain, then merge to `main`)

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

## 3. Still stale (exact commands)
- `oresight-backend/docs/API_CONTRACT.md`, `docs/openapi.json`: `python -m scripts.export_contract` from
  `oresight-backend/` (needs the API running).
- `prospectivity/METHODOLOGY.md`: site areas (810.8 / 142.5 / 193.5 km2) and grid dimensions/cell counts (Balaghat
  81,147, Nagpur 14,248, Bhandara 19,365 at 100 m) in sections 3.2 and 4, by hand. (Feature windows are current.)

## 4. Remaining phases
- **Phase 4:** `docker compose build api`; `python -m scripts.export_contract`; update METHODOLOGY.md; search the
  repo for leftover old coordinates (old Nagpur/Bhandara city-centred boxes).
- **Phase 5:** `python -m scripts.build_site_aois --check`; full backend suite (`pytest` in `oresight-backend/`);
  then `python -m scripts.rebuild_demo_db` and `python -m scripts.backfill_equipment_status_log`; live API checks on
  `/sites`, `/reserve-zones`, `/equipment/metrics`; in `oresight-frontend/`: `pnpm install`, `pnpm typecheck`,
  `pnpm build`, smoke tests. Then merge into `main`.

## 5. Known issues
- The `oresight-api` Docker image is stale and lacks `/equipment/metrics` until rebuilt (`docker compose build api`).
- `tests/test_smoke.py::test_simulate_after_differs_from_before` is xfail pending Tasks 2/3: the shortfall model is
  non-monotonic in downtime (baseline: `equipment_down` points the right way on only 212/365 days at Balaghat).
- `pnpm typecheck` needs `pnpm install` to add typescript (`tsc` is missing locally).
- NDVI tile week 1 (Aug 26 - Sep 2) is `no_data`: all six scenes were 97-100% cloud.
- Balaghat has 17.6% no-data map cells (no clear Sentinel-2 pixel in a window); Bhandara 4.4%, Nagpur 0.03%.
- `jenkspy` is not installed; class breaks use the built-in 1-D k-means fallback.

## 6. Test suite warning
The full backend suite writes to the demo DB. After ANY full run, rerun `python -m scripts.rebuild_demo_db` and
`python -m scripts.backfill_equipment_status_log` (from `oresight-backend/`).
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
  (use the backend `venv`, it needs geoalchemy2).
