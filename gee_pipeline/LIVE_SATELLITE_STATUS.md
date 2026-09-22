# Live Satellite Data — Status (2026-09-23)

Branch: `fix/satellite-live`. Step 1 of "real satellite inputs" (item 1) in progress.

## What's live now

`data/satellite_daily_features.csv` and `.meta.json` were regenerated from a real
Earth Engine run (`python gee_pipeline/export_site_daily_climate.py --start 2025-01-01`,
project `manganex-509408`, service-account auth), covering 2025-01-01 to 2026-09-22,
1890 rows (630/site x 3 sites). `meta.json` now says `"simulated": false`.

Per-site coverage from that run:

| Site     | Rainfall           | Soil Moisture      | LST Day             | NDVI          |
|----------|--------------------|---------------------|----------------------|---------------|
| Balaghat | 629/630 (99.8%)    | 626/630 (99.4%)     | 283/630 (44.9%)      | 0/630 (0.0%)  |
| Nagpur   | 629/630 (99.8%)    | 626/630 (99.4%)     | 295/630 (46.8%)      | 0/630 (0.0%)  |
| Bhandara | 629/630 (99.8%)    | 626/630 (99.4%)     | 303/630 (48.1%)      | 0/630 (0.0%)  |

Rainfall/soil-moisture/LST are genuinely live and pass the monsoon-vs-dry-season
sanity check for all three sites (June-Sept mean clearly higher than Jan-April mean).
LST's ~45-48% coverage is expected — documented monsoon cloud-occlusion behavior in
`gee_pipeline/README.md`, not a bug.

**NDVI is still 0% for all sites — not yet live-ready.** See below.

## Bug #1 (fixed): `.copyProperties()` returns `ee.Element`, not `ee.Image`

Earth Engine's `Image.copyProperties()` always returns a generic `ee.Element`
regardless of the receiver's type — a well-known API quirk. Every local
`mask_s2_clouds()` ended its return with `.copyProperties(...)`, so the caller's
`.normalizedDifference()` call failed with:

```
'Element' object has no attribute 'normalizedDifference'
```

This blocked NDVI (and iron-oxide/tile) extraction everywhere it appeared. Fixed by
casting back to `ee.Image(...)` around the `.copyProperties(...)` call, in the three
files in scope for this branch:

- `gee_pipeline/export_site_daily_climate.py` (fixed at the call site, line ~644 —
  wraps the call to `prospectivity.gee_features.mask_s2_clouds`, since that file
  itself is out of scope for this branch)
- `gee_pipeline/gee_prep.py` (fixed inside its own local `mask_s2_clouds()`)
- `gis/ndvi_pull.py` (fixed inside its own local `mask_s2_clouds()`)

After this fix, the exporter got past the `normalizedDifference` crash and made real
GEE Sentinel-2 requests — confirmed via server logs (429s below are real API
responses, not local errors).

### Same pattern found elsewhere, NOT fixed (out of scope / already covered)

- **`prospectivity/gee_features.py:198`** — has the identical `.copyProperties()`
  bug in its own `mask_s2_clouds()`. Out of scope for this branch (explicitly
  excluded). Only `export_site_daily_climate.py` calls this version, and that call
  site now casts the result to `ee.Image(...)` itself, so the exporter is unblocked —
  but the root function is still broken for any other caller. Needs a real fix
  (`return ee.Image(image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"]))`)
  the next time `prospectivity/` is in scope.
- **`gis/ndvi_timeseries.py`** — imports and reuses `mask_s2_clouds` from
  `gis/ndvi_pull.py` (already fixed above). No separate bug, no separate fix needed.
- **`gis/generate_tiles.py`** — has no GEE masking/NDVI logic of its own (checked,
  no `copyProperties`/`normalizedDifference` calls). Not affected.

## Bug #2 (open): GEE 429 "Too many concurrent aggregations" on NDVI

With bug #1 fixed, every Sentinel-2 NDVI chunk request (21 total: 3 sites x 7
90-day chunks each) still failed, this time with a real GEE rate-limit response:

```
ee.ee_exception.EEException: Too many concurrent aggregations.
```

`with_gee_retry` (4 attempts, exponential backoff) exhausted retries on every single
chunk. Root cause: `fetch_s2()` in `export_site_daily_climate.py` calls
`.map(process_s2).getInfo()` on the whole 90-day chunk's `ImageCollection` in one
request. Sentinel-2's ~5-day revisit means a 90-day chunk holds ~18 images, and each
one fires its own `reduceRegion` server-side concurrently — exceeding project
`manganex-509408`'s concurrency quota.

**Not fixed yet.** Likely fix: shrink the chunk size used specifically for the NDVI
branch (e.g. 14-30 days instead of 90) so far fewer images map per request, and/or
serialize the per-image reduceRegion calls instead of batching via `.map()`. This
needs to land in `export_site_daily_climate.py` (in scope) before NDVI, the frontend
JSON export, and tile generation can be re-run live.

## Next steps (not started)

1. Fix the NDVI chunking/concurrency issue above, re-run just the Sentinel-2 portion
   (or the full exporter) until NDVI coverage is non-zero and plausible.
2. Run `gee_pipeline/export_frontend_satellite_json.py` live.
3. Run tile generation (`gis/generate_tiles.py`, `gis/ndvi_pull.py`,
   `gis/ndvi_timeseries.py`) live, confirm `manifest.json` shows real image counts
   and no `SIMULATED_MOCK`.
4. Full CSV validation (columns match old CSV exactly, null counts, value ranges,
   `meta.json` "simulated": false — rainfall/soil-moisture/LST/meta already verified
   true today, NDVI still pending).
5. `pnpm build` in `oresight-frontend`, then `gee_pipeline` tests.
