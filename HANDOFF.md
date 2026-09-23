# Handoff — branch `fix/site-aois`

## Status
Item 1 (real satellite inputs) is **complete**. Everything below was produced live
from Google Earth Engine (project `manganex-509408`); nothing is simulated.

| Artifact | Source | Notes |
|---|---|---|
| `data/moil_sites.json` | site AOIs (single source; synced to backend + frontend by `python -m scripts.build_site_aois`) | `--check` verifies the copies |
| `data/satellite_daily_features.csv` (+ `.meta.json`) | `gee_pipeline/export_site_daily_climate.py` | rainfall, SMAP soil moisture, MODIS LST, S2 10-day median NDVI; 1893 rows, `simulated: false` |
| `oresight-frontend/public/satellite/site_daily_features.json` | `gee_pipeline/export_frontend_satellite_json.py` | last 180 days, ends at the last date with rainfall |
| `gis/tiles/*` -> `oresight-frontend/public/tiles/*` | `python -m gis.generate_tiles` | cloud-masked S2 median mosaics over `COMBINED_BBOX`; `manifest.json` has status, actual window, image_count, valid_fraction per layer |

## How to regenerate
- Satellite CSV: `python gee_pipeline/export_site_daily_climate.py --start 2025-01-01` (~30 min, live GEE).
- Frontend JSON: `python gee_pipeline/export_frontend_satellite_json.py` (offline, reads the CSV).
- Tiles: `python -m gis.generate_tiles`, then copy `gis/tiles/*` to `oresight-frontend/public/tiles/`
  (delete PNGs in the destination that no longer exist in the source).
- Run only ONE GEE job at a time (concurrent jobs caused the 429s).

## Things to know
- Service account `earth-engine-runner@...` needs **Earth Engine Resource Writer**; rendering PNGs
  (`getThumbURL`) fails with `earthengine.thumbnails.create denied` without it.
- A tile window with < 10% clear pixels (or no scenes) is `status: "no_data"`: no PNG is written, a stale PNG is
  deleted, and the frontend shows the week as unavailable. Nothing is filled from another week.
- Map layer dates/availability come from `public/tiles/manifest.json` at runtime (`src/lib/useTileManifest.js`).
- `--dry-run` refuses to write into `gis/tiles`; use a scratch `--tiles-dir`.
- `pnpm typecheck` fails locally: `typescript` is not installed (`tsc` not found). `pnpm build` passes.

## Still stale (not done)
- **Prospectivity layers** (Phase 2): `prospectivity/*.geojson`, model outputs and the confidence surface were not
  rebuilt against the live satellite features.
- **API docs**: do not yet reflect the corrected AOIs / site geometry.
- **`prospectivity/METHODOLOGY.md`**: not updated for the mosaic tiles or live satellite inputs.
- Not started: Phase 4, Phase 5. Not merged into `main`.

## Tests (fast; none touch GEE)
`python -m pytest gee_pipeline prospectivity gis -q` and `python -m scripts.build_site_aois --check`.
Do not run the full backend suite casually: it writes to the demo DB.
