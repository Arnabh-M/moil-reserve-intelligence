# MOIL Reserve Intelligence — Google Earth Engine (GEE) Pipeline

Automated remote sensing pipelines for SIH26009: *"Using AI/ML and Space Technology to Identify Manganese Reserves and Overcome Production Shortfalls"* (Ministry of Steel / MOIL Ltd).

This module ingests and standardizes satellite inputs across the primary Central Indian manganese belt (Balaghat, Nagpur, Bhandara) for downstream reserve prospectivity modeling and operational shortfall forecasting.

---

## 1. Setup & Authentication

### Installation
Install pinned dependencies:
```bash
pip install -r gee_pipeline/requirements.txt
```

### Authentication Options
Earth Engine authentication is centralized in [`gee_pipeline/ee_auth.py`](ee_auth.py) via `get_ee(dry_run: bool = False)`:

1. **Interactive User Authentication**:
   ```bash
   earthengine authenticate
   # Set your registered Google Cloud Project:
   export EE_PROJECT="your-gcp-project-id"        # Linux / macOS
   $env:EE_PROJECT = "your-gcp-project-id"        # Windows PowerShell
   ```
2. **Service Account Key (Headless / Automated)**:
   ```bash
   export EE_SERVICE_ACCOUNT_JSON="/path/to/key.json"
   export EE_PROJECT="your-gcp-project-id"
   ```
3. **Local `.env` File**:
   Copy [`gee_pipeline/.env.example`](.env.example) to `.env` in the repository root or `gee_pipeline/`:
   ```ini
   EE_PROJECT=your-gcp-project-id
   EE_SERVICE_ACCOUNT_JSON=
   ```

> **Integrity Contract**: Real execution modes **never** silently fall back to synthetic data. If GEE credentials are not configured or the connection fails, the scripts raise `GEEUnavailableError` with an actionable checklist. Dry-run mode (`--dry-run`) is explicitly required to generate deterministic simulated data.

---

## 2. CLI Usage & Commands

### Export Daily Site Climate Features (`export_site_daily_climate.py`)
Generates daily time-series of rainfall, soil moisture, surface temperature, and vegetation health per mine site:
```bash
# Real live GEE run from 2025-01-01 to today (UTC):
python gee_pipeline/export_site_daily_climate.py

# Custom date range and target sites:
python gee_pipeline/export_site_daily_climate.py --start 2025-01-01 --end 2026-09-22 --sites balaghat,nagpur,bhandara

# Dry-run offline verification (deterministic physical simulation, no network required):
python gee_pipeline/export_site_daily_climate.py --dry-run
```

Outputs written:
- `data/satellite_daily_features.csv`
- `data/satellite_daily_features.meta.json`

### Sentinel-2 Raster Preparation (`gee_prep.py`)
Generates georeferenced GeoTIFFs and MapLibre browser tiles across `geo_utils.COMBINED_BBOX` (`[79.0, 21.0, 80.4, 22.0]`):
```bash
# Live run:
python gee_pipeline/gee_prep.py --scale 250

# Dry-run mode:
python gee_pipeline/gee_prep.py --dry-run
```

---

## 3. Output Contract: `satellite_daily_features.csv`

The CSV is read directly by the downstream shortfall forecaster and Watcher intelligence agent. The schema, ordering, and missing value formats are strictly fixed.

### Column Specification

| Column Index | Column Name | Format / Type | Units | Description & Source Values |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `site_id` | String (lowercase) | — | Mine identifier: `balaghat`, `nagpur`, or `bhandara` |
| 2 | `date` | String (`YYYY-MM-DD`) | UTC Day | Calendar date |
| 3 | `rainfall_mm` | Float (2 decimal places) | mm/day | Daily accumulated precipitation. Empty if unobserved. |
| 4 | `rainfall_source` | String enum | — | `"CHIRPS"`, `"IMERG"`, or empty `""` |
| 5 | `soil_moisture_m3m3`| Float (4 decimal places) | m³/m³ | Surface soil moisture (0–5 cm depth). Empty if unobserved. |
| 6 | `soil_moisture_source` | String enum | — | `"SMAP_L4"` or empty `""` |
| 7 | `lst_day_c` | Float (2 decimal places) | °C | Daytime land surface temperature. Empty if unobserved / cloud-occluded. |
| 8 | `lst_source` | String enum | — | `"MODIS_MOD11A1"` or empty `""` |
| 9 | `ndvi` | Float (4 decimal places) | [-1, 1] | Sentinel-2 NDVI with 30-day carry-forward. Empty if unobserved. |
| 10 | `ndvi_age_days` | Integer (0 to 30) | days | Days since the last clear Sentinel-2 acquisition (0 on acquisition day). |
| 11 | `ndvi_source` | String enum | — | `"S2_SR"` or empty `""` |

### Integrity Rules
1. **Row Uniqueness & Completeness**: Exactly one row per `(site_id, date)`. Every calendar date in the requested range is guaranteed to be present with zero gaps or duplicates.
2. **Missing Values**: Missing observations are strictly **empty cells** (`,,`). Never `0`, never `NaN`, and never interpolated (except for the explicitly documented NDVI 30-day carry-forward).
3. **Sorting**: Rows are sorted strictly by `site_id` (alphabetically), then by `date` (chronologically).
4. **Column Extensibility**: New columns may only be appended at the end. Existing columns are never renamed, reordered, or removed.

---

## 4. Earth Engine Datasets & Processing Logic

### 1. Rainfall (CHIRPS + IMERG Fallback)
- **Primary**: `UCSB-CHG/CHIRPS/DAILY`
  - Band: `precipitation` (mm/day)
  - Native Scale: ~5566 m
  - Reduction: Spatial mean over the site geometry.
- **Fallback**: `NASA/GPM_L3/IMERG_V07`
  - Band: `precipitation` (mm/hr half-hourly)
  - Native Scale: ~11132 m
  - Conversion: Daily total = $\sum (\text{half-hourly rates}) \times 0.5\text{ hr}$.
  - Fallback trigger: Activated only on dates where CHIRPS has not yet published.

### 2. Soil Moisture (SMAP Level 4)
- **Collection**: `NASA/SMAP/SPL4SMGP/008` (fallback: `NASA/SMAP/SPL4SMGP/007`)
- **Band**: `sm_surface` (surface soil moisture, 0–5 cm, volumetric fraction $\text{m}^3/\text{m}^3$)
- **Native Scale**: ~9000 m
- **Reduction**: Spatial mean over site geometry, averaged daily across 3-hourly assimilation steps.

### 3. Land Surface Temperature (MODIS MOD11A1)
- **Collection**: `MODIS/061/MOD11A1`
- **Band**: `LST_Day_1km`
- **Native Scale**: 1000 m
- **Conversion**: $\text{LST (°C)} = \text{DN} \times 0.02 - 273.15$
- **Quality Control**:
  - Filtered using `QC_Day` mandatory QA flags (bits 0–1): keeps only pixels where LST was produced with good or acceptable quality (`(QC_Day & 2) == 0`).
  - **Coverage Threshold**: If fewer than 20% of the site's pixels have clear, valid LST retrievals on a given day (e.g. during heavy monsoon cloud cover), the day is recorded as empty. No synthetic interpolation is applied.

### 4. NDVI (Sentinel-2 Harmonized L2A)
- **Collection**: `COPERNICUS/S2_SR_HARMONIZED`
- **Bands**: `B8` (NIR, 842 nm), `B4` (Red, 665 nm), `SCL` (Scene Classification Layer)
- **Scale**: 30 m (`bestEffort=True`, `tileScale=4`)
- **Cloud Masking**: Cloud shadow (3), medium cloud probability (8), high cloud probability (9), and thin cirrus (10) are masked via `prospectivity.gee_features.mask_s2_clouds`.
- **Acquisition Filter**: An acquisition is accepted only if at least 30% of the site's pixels are clear.
- **Carry-Forward Model**: The latest valid mean NDVI is carried forward daily with `ndvi_age_days` indicating the age of the observation. If more than 30 days elapse without a clear acquisition, both `ndvi` and `ndvi_age_days` revert to empty cells.

---

## 5. Satellite Latency & Publishing Delay

Satellite data products operate on varying latency schedules:

| Product | Source Provider | Typical Publishing Latency | Behavior on Recent Days |
| :--- | :--- | :---: | :--- |
| **CHIRPS Daily** | UCSB Climate Hazards Center | ~15–20 days | Empty in CHIRPS; automatically filled by IMERG fallback. |
| **GPM IMERG** | NASA GSFC | ~2–3 days | Leaves the most recent 1–2 days empty. |
| **SMAP L4** | NASA GSFC / GMAO | ~3–5 days | Recent 3–5 days empty. |
| **MODIS MOD11A1** | NASA LP DAAC | ~1–2 days | Recent 1–2 days empty. |
| **Sentinel-2 L2A** | ESA Copernicus | ~2–5 days revisit | Carried forward up to 30 days; empty if older than 30 days. |

---

## 6. Testing

The offline test suite validates all post-processing algorithms without requiring network access:
```bash
python -m pytest gee_pipeline/tests/test_export_site_daily_climate.py -v
```

Covered test cases:
- Exact column names and ordering.
- Row uniqueness and calendar day continuity.
- Missing values serialized as empty cells (never 0 or NaN).
- MODIS DN to Celsius scaling (`val * 0.02 - 273.15`).
- IMERG half-hourly mm/hr sum conversion ($\times 0.5$).
- NDVI 30-day carry-forward cut-off (day 30 valid, day 31 empty).
- Priority rules (CHIRPS prioritized over IMERG).
- Physical validation of monsoon wet-season dynamics.
