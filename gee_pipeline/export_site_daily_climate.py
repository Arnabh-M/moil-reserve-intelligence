"""
MOIL Reserve Intelligence — Site Daily Climate & Satellite Feature Exporter
=============================================================================
SIH26009: "Using AI/ML and Space Technology to Identify Manganese Reserves
           and Overcome Production Shortfalls"

Exports unified daily climate and environmental satellite features per site:
- Rainfall (CHIRPS daily primary, GPM IMERG fallback)
- Soil moisture (SMAP Level 4 surface soil moisture)
- Land Surface Temperature (MODIS MOD11A1 daytime LST with QC filtering)
- NDVI (Sentinel-2 Harmonized L2A with SCL cloud mask & 30-day carry-forward)

Target outputs:
- data/satellite_daily_features.csv
- data/satellite_daily_features.meta.json

Contract:
  site_id,date,rainfall_mm,rainfall_source,soil_moisture_m3m3,soil_moisture_source,lst_day_c,lst_source,ndvi,ndvi_age_days,ndvi_source
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from gee_pipeline.ee_auth import get_ee
from geo_utils import SITE_BBOXES
from prospectivity.gee_features import mask_s2_clouds, with_gee_retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_VERSION = "1.0.0"

COLUMNS = [
    "site_id",
    "date",
    "rainfall_mm",
    "rainfall_source",
    "soil_moisture_m3m3",
    "soil_moisture_source",
    "lst_day_c",
    "lst_source",
    "ndvi",
    "ndvi_age_days",
    "ndvi_source",
]

DEFAULT_SITES = ["balaghat", "nagpur", "bhandara"]

NON_NDVI_COLUMNS = [
    "site_id", "date", "rainfall_mm", "rainfall_source",
    "soil_moisture_m3m3", "soil_moisture_source", "lst_day_c", "lst_source",
]

# ---------------------------------------------------------------------------
# NDVI composite configuration
#
# Sentinel-2 NDVI is fetched as cloud-masked MEDIAN COMPOSITES over windows of
# NDVI_COMPOSITE_DAYS, one reduceRegion per window (not one per image). This
# replaces a prior per-image .map(...).getInfo() approach that fired one
# reduceRegion per image concurrently server-side and reliably tripped GEE's
# "Too many concurrent aggregations" (HTTP 429) quota on 90-day chunks.
#
# Every day inside a window receives that window's single composite value.
# There is no carry-forward across windows: a window with no images, or with
# fewer than NDVI_MIN_VALID_FRACTION of the site's pixels cloud-free, is
# recorded as missing (empty cells) for every day in that window.
# ---------------------------------------------------------------------------
S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
NDVI_COMPOSITE_DAYS = int(os.environ.get("NDVI_COMPOSITE_DAYS", "10"))
NDVI_MIN_VALID_FRACTION = 0.10
NDVI_SOURCE_LABEL = f"S2_median_{NDVI_COMPOSITE_DAYS}d"

# ---------------------------------------------------------------------------
# Pure Post-Processing Functions (Isolated for Offline Unit Testing)
# ---------------------------------------------------------------------------

def convert_lst(raw_val: Optional[float]) -> Optional[float]:
    """
    Converts MODIS MOD11A1 LST_Day_1km raw digital number to degrees Celsius.
    Formula: val * 0.02 - 273.15
    """
    if raw_val is None or math.isnan(raw_val) or raw_val <= 0:
        return None
    celsius = raw_val * 0.02 - 273.15
    return round(celsius, 2)


def convert_imerg_daily(half_hourly_sum: Optional[float]) -> Optional[float]:
    """
    Converts sum of half-hourly IMERG mm/hr precipitation rates to daily total mm.
    Formula: sum(mm/hr) * 0.5 hr
    """
    if half_hourly_sum is None or math.isnan(half_hourly_sum):
        return None
    daily_mm = max(0.0, half_hourly_sum * 0.5)
    return round(daily_mm, 2)


def compute_daily_ndvi_series(
    acquisitions: Dict[date, float],
    all_dates: List[date],
    max_age_days: int = 30,
) -> List[Tuple[Optional[float], Optional[int], str]]:
    """
    Builds the daily NDVI time-series by carrying the last valid acquisition forward.
    - ndvi_age_days = days since that acquisition (0 on acquisition day).
    - If days since last acquisition > max_age_days (30), outputs (None, None, "").
    - Returns list of (ndvi_val, ndvi_age_days, ndvi_source) aligned with all_dates.
    """
    sorted_acquisitions = sorted(acquisitions.items(), key=lambda x: x[0])
    results: List[Tuple[Optional[float], Optional[int], str]] = []

    last_val: Optional[float] = None
    last_date: Optional[date] = None

    acq_idx = 0
    num_acqs = len(sorted_acquisitions)

    for current_date in all_dates:
        # Advance acquisition pointer up to current_date
        while acq_idx < num_acqs and sorted_acquisitions[acq_idx][0] <= current_date:
            last_date, last_val = sorted_acquisitions[acq_idx]
            acq_idx += 1

        if last_date is not None and last_val is not None:
            age = (current_date - last_date).days
            if 0 <= age <= max_age_days:
                results.append((round(last_val, 4), age, "S2_SR"))
            else:
                results.append((None, None, ""))
        else:
            results.append((None, None, ""))

    return results


def assign_ndvi_window_values(
    window_results: List[Tuple[date, date, Optional[float]]],
    all_dates: List[date],
) -> List[Tuple[Optional[float], Optional[int], str]]:
    """
    Assigns each date in `all_dates` the NDVI value of the composite window
    (inclusive [w_start, w_end], length NDVI_COMPOSITE_DAYS) it falls into.

    Unlike the acquisition carry-forward model above, there is no aging: a
    composite window's value applies uniformly to every day inside it, and
    ndvi_age_days is fixed at 0 for those days (composite windows are not
    "observations" that get stale — see NDVI_SOURCE_LABEL / meta.json for the
    method note). A date with no matching window, or whose window's value is
    None (no images / low valid-pixel coverage), is recorded as missing.

    `window_results` must be sorted ascending and non-overlapping (as produced
    by chunk_date_ranges).
    """
    results: List[Tuple[Optional[float], Optional[int], str]] = []
    win_idx = 0
    n_wins = len(window_results)

    for current_date in all_dates:
        while win_idx < n_wins and current_date > window_results[win_idx][1]:
            win_idx += 1

        if win_idx < n_wins and window_results[win_idx][0] <= current_date <= window_results[win_idx][1]:
            val = window_results[win_idx][2]
            if val is not None:
                results.append((round(val, 4), 0, NDVI_SOURCE_LABEL))
            else:
                results.append((None, None, ""))
        else:
            results.append((None, None, ""))

    return results


def format_cell(val: Optional[Any], precision: Optional[int] = None) -> str:
    """Formats values strictly according to contract: empty string for missing."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    if precision is not None and isinstance(val, (int, float)):
        return f"{val:.{precision}f}"
    return str(val)


def merge_daily_features(
    dates: List[date],
    site_id: str,
    chirps_data: Dict[date, float],
    imerg_data: Dict[date, float],
    smap_data: Dict[date, float],
    lst_data: Dict[date, float],
    ndvi_records: List[Tuple[Optional[float], Optional[int], str]],
) -> List[Dict[str, Any]]:
    """
    Merges per-variable dictionaries into standardized daily records matching
    the exact output column order and contract.
    """
    rows = []
    for i, dt in enumerate(dates):
        dt_str = dt.strftime("%Y-%m-%d")

        # 1. Rainfall: CHIRPS primary, IMERG fallback
        if dt in chirps_data and chirps_data[dt] is not None and not math.isnan(chirps_data[dt]):
            rainfall_mm = round(max(0.0, chirps_data[dt]), 2)
            rainfall_source = "CHIRPS"
        elif dt in imerg_data and imerg_data[dt] is not None and not math.isnan(imerg_data[dt]):
            rainfall_mm = round(max(0.0, imerg_data[dt]), 2)
            rainfall_source = "IMERG"
        else:
            rainfall_mm = None
            rainfall_source = ""

        # 2. Soil moisture: SMAP Level 4
        if dt in smap_data and smap_data[dt] is not None and not math.isnan(smap_data[dt]):
            soil_moisture = round(smap_data[dt], 4)
            soil_moisture_source = "SMAP_L4"
        else:
            soil_moisture = None
            soil_moisture_source = ""

        # 3. LST: MODIS MOD11A1
        if dt in lst_data and lst_data[dt] is not None and not math.isnan(lst_data[dt]):
            lst_val = round(lst_data[dt], 2)
            lst_source = "MODIS_MOD11A1"
        else:
            lst_val = None
            lst_source = ""

        # 4. NDVI
        ndvi_val, ndvi_age, ndvi_src = ndvi_records[i]

        row = {
            "site_id": site_id.lower(),
            "date": dt_str,
            "rainfall_mm": rainfall_mm,
            "rainfall_source": rainfall_source,
            "soil_moisture_m3m3": soil_moisture,
            "soil_moisture_source": soil_moisture_source,
            "lst_day_c": lst_val,
            "lst_source": lst_source,
            "ndvi": ndvi_val,
            "ndvi_age_days": ndvi_age,
            "ndvi_source": ndvi_src,
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Geometry Resolution
# ---------------------------------------------------------------------------

def resolve_site_geometries(
    sites: List[str], geometry_source: str = "db"
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """
    Load each site's AOI polygon.

    `geometry_source`:
      "db"   — PostGIS `sites.geom`. A DB failure RAISES; it does not quietly
               substitute another box.
      "file" — data/moil_sites.json, the same definition the DB was seeded
               from. Explicit opt-in only.

    There is deliberately no automatic fallback. The previous version logged a
    debug line and switched to a different (~33 km) box family whenever the DB
    was unreachable, which is how data/satellite_daily_features.csv came to
    hold 1890 rows sampled over boxes that no longer matched the DB, the map
    or the mines — with `"geometry_source": "bbox"` in the metadata as the
    only trace.

    Returns: (shapely_geoms, geometry_sources)
    """
    if geometry_source not in ("db", "file"):
        raise ValueError(f"geometry_source must be 'db' or 'file', got {geometry_source!r}")

    known = set(SITE_BBOXES)
    for s in sites:
        if s.lower() not in known:
            raise ValueError(f"Unknown site '{s}'. Must be one of {sorted(known)}.")

    shapely_geoms: Dict[str, Any] = {}
    geom_sources: Dict[str, str] = {}

    if geometry_source == "file":
        from prospectivity.training_data import site_geometries_from_file

        file_sites = site_geometries_from_file()
        digest = site_definition_digest()
        for s in sites:
            s_key = s.lower()
            geom = file_sites[s_key]["geom"]
            shapely_geoms[s_key] = geom
            geom_sources[s_key] = _geometry_provenance(
                f"moil_sites.json@{digest}", geom, db_id=file_sites[s_key]["db_id"]
            )
            logger.info("Site '%s' geometry from data/moil_sites.json.", s_key)
        return shapely_geoms, geom_sources

    from prospectivity.training_data import load_site_boundaries

    db_url = os.environ.get("DATABASE_URL")
    try:
        db_sites = load_site_boundaries(db_url)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load site boundaries from the database: {exc}. "
            "Start Postgres and run `python -m scripts.rebuild_demo_db`, or pass "
            "--geometry-source=file to build against data/moil_sites.json "
            "(the same AOIs, explicitly chosen)."
        ) from exc

    for s in sites:
        s_key = s.lower()
        if s_key not in db_sites:
            raise RuntimeError(
                f"Site '{s_key}' has no row in the `sites` table. Run "
                "`python -m scripts.rebuild_demo_db`, or pass "
                "--geometry-source=file."
            )
        geom = db_sites[s_key]["geom"]
        shapely_geoms[s_key] = geom
        geom_sources[s_key] = _geometry_provenance(
            "db_polygon", geom, db_id=db_sites[s_key]["db_id"]
        )
        logger.info("Loaded site '%s' geometry from PostGIS boundary polygon.", s_key)

    return shapely_geoms, geom_sources


def _geometry_provenance(source: str, geom, db_id=None) -> dict:
    """Self-describing provenance for one site's AOI, recorded in meta.json.

    A bare source label ("db_polygon", "bbox") is not enough to trace a CSV
    back to the area it was actually sampled over -- the previous run's
    metadata said "bbox" for all three sites while the boxes silently differed
    from the DB, the map and the mines. Recording the real bounds means a CSV
    can always be checked against the AOI definition that produced it.
    """
    from prospectivity.training_data import _area_km2

    minx, miny, maxx, maxy = geom.bounds
    return {
        "source": source,
        "db_site_id": db_id,
        "bounds_wsen": [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)],
        "area_km2": round(_area_km2(geom), 2),
        "moil_sites_sha256_12": site_definition_digest(),
    }


def site_definition_digest() -> str:
    """Short content hash of data/moil_sites.json, recorded in the export
    metadata so a CSV can be traced back to the exact AOI definition."""
    from geo_utils import SITES_JSON_PATH

    with open(SITES_JSON_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Deterministic Dry-Run Generator
# ---------------------------------------------------------------------------

def generate_dry_run_dataset(
    sites: List[str],
    start_date: date,
    end_date: date,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generates realistic, physically consistent daily climate and satellite
    data for dry-run verification with seasonal monsoon dynamics.
    """
    curr = start_date
    all_dates: List[date] = []
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    all_rows: List[Dict[str, Any]] = []

    # Track valid counts and latest dates per product
    product_stats = {
        "rainfall": {"latest_date": None, "valid_count": 0},
        "soil_moisture": {"latest_date": None, "valid_count": 0},
        "lst": {"latest_date": None, "valid_count": 0},
        "ndvi": {"latest_date": None, "valid_count": 0},
    }

    for site in sites:
        site_key = site.lower()
        # Seed uniquely per site for determinism
        seed = sum(ord(c) for c in site_key) * 10007
        rng = np.random.RandomState(seed)

        chirps_data: Dict[date, float] = {}
        imerg_data: Dict[date, float] = {}
        smap_data: Dict[date, float] = {}
        lst_data: Dict[date, float] = {}
        acquisitions: Dict[date, float] = {}

        # Site climate bias
        site_rain_mult = 1.15 if site_key == "balaghat" else (0.95 if site_key == "nagpur" else 1.05)
        site_temp_add = -1.2 if site_key == "balaghat" else (1.5 if site_key == "nagpur" else 0.0)
        site_ndvi_base = 0.38 if site_key == "balaghat" else (0.28 if site_key == "nagpur" else 0.32)

        # Baseline S2 acquisitions every 5-10 days
        acq_dates = []
        d = start_date
        while d <= end_date:
            step = rng.randint(4, 9)
            d += timedelta(days=step)
            if d <= end_date:
                acq_dates.append(d)

        # Generate daily values
        current_smap = 0.12
        for dt in all_dates:
            day_of_year = dt.timetuple().tm_yday
            is_monsoon = 160 <= day_of_year <= 273  # ~June 10 to Sept 30
            is_summer = 75 <= day_of_year <= 159   # ~mid-March to early June
            days_from_end = (end_date - dt).days

            # Rainfall simulation
            # CHIRPS has ~15 days latency; IMERG covers up to ~2 days ago
            if days_from_end >= 15:
                if is_monsoon:
                    # Monsoon active rain bursts vs breaks
                    p_rain = 0.65
                    rain = rng.exponential(scale=14.0) * site_rain_mult if rng.rand() < p_rain else 0.0
                else:
                    p_rain = 0.04
                    rain = rng.exponential(scale=2.5) * site_rain_mult if rng.rand() < p_rain else 0.0
                chirps_data[dt] = round(rain, 2)
            elif days_from_end >= 2:
                # IMERG fallback for recent window
                if is_monsoon:
                    p_rain = 0.60
                    rain = rng.exponential(scale=12.0) * site_rain_mult if rng.rand() < p_rain else 0.0
                else:
                    p_rain = 0.03
                    rain = rng.exponential(scale=2.0) * site_rain_mult if rng.rand() < p_rain else 0.0
                imerg_data[dt] = round(rain, 2)

            effective_rain = chirps_data.get(dt, imerg_data.get(dt, 0.0))

            # Soil moisture simulation (tracks rainfall with drying decay)
            # SMAP Level 4 has ~3-5 days latency
            if days_from_end >= 3:
                current_smap = current_smap * 0.92 + (effective_rain * 0.006)
                current_smap = min(0.38, max(0.08, current_smap))
                smap_data[dt] = round(current_smap, 4)

            # LST simulation (°C)
            # MODIS has ~2-3 days latency; cloud mask removes ~50% of monsoon days
            if days_from_end >= 2:
                if is_summer:
                    base_lst = 38.0 + 4.0 * math.sin((day_of_year - 75) / 84.0 * math.pi)
                elif is_monsoon:
                    base_lst = 29.5 + rng.normal(0, 1.5)
                else:
                    base_lst = 27.0 + 3.0 * math.sin((day_of_year + 30) / 365.0 * 2 * math.pi)

                val_lst = base_lst + site_temp_add + rng.normal(0, 1.2)
                # Cloud occlusion: >20% invalid pixels in monsoon drops LST
                cloud_prob = 0.55 if is_monsoon else 0.08
                if rng.rand() >= cloud_prob:
                    lst_data[dt] = round(val_lst, 2)

            # NDVI simulation on acquisition dates
            if dt in acq_dates and days_from_end >= 3:
                # Clear pixel check: ~40% cloudy in monsoon
                clear_prob = 0.50 if is_monsoon else 0.88
                if rng.rand() < clear_prob:
                    # Greening curve peaking in Aug-Oct
                    seasonal_green = 0.22 * math.exp(-((day_of_year - 245) ** 2) / (2 * 50 ** 2))
                    acq_ndvi = site_ndvi_base + seasonal_green + rng.normal(0, 0.02)
                    acquisitions[dt] = round(min(0.85, max(0.12, acq_ndvi)), 4)

        ndvi_series = compute_daily_ndvi_series(acquisitions, all_dates, max_age_days=30)
        rows = merge_daily_features(
            all_dates,
            site_key,
            chirps_data,
            imerg_data,
            smap_data,
            lst_data,
            ndvi_series,
        )
        all_rows.extend(rows)

        # Update product statistics
        for r in rows:
            dt_val = r["date"]
            if r["rainfall_mm"] is not None:
                product_stats["rainfall"]["valid_count"] += 1
                if not product_stats["rainfall"]["latest_date"] or dt_val > product_stats["rainfall"]["latest_date"]:
                    product_stats["rainfall"]["latest_date"] = dt_val
            if r["soil_moisture_m3m3"] is not None:
                product_stats["soil_moisture"]["valid_count"] += 1
                if not product_stats["soil_moisture"]["latest_date"] or dt_val > product_stats["soil_moisture"]["latest_date"]:
                    product_stats["soil_moisture"]["latest_date"] = dt_val
            if r["lst_day_c"] is not None:
                product_stats["lst"]["valid_count"] += 1
                if not product_stats["lst"]["latest_date"] or dt_val > product_stats["lst"]["latest_date"]:
                    product_stats["lst"]["latest_date"] = dt_val
            if r["ndvi"] is not None:
                product_stats["ndvi"]["valid_count"] += 1
                if not product_stats["ndvi"]["latest_date"] or dt_val > product_stats["ndvi"]["latest_date"]:
                    product_stats["ndvi"]["latest_date"] = dt_val

    # Sort strictly by site_id, then date
    all_rows.sort(key=lambda r: (r["site_id"], r["date"]))
    return all_rows, product_stats


# ---------------------------------------------------------------------------
# Earth Engine Live Extraction
# ---------------------------------------------------------------------------

def verify_dataset_id(ee, dataset_candidates: List[str]) -> str:
    """Verifies which dataset ID is available in GEE, returning the first accessible one."""
    for candidate in dataset_candidates:
        try:
            col = ee.ImageCollection(candidate)
            count = col.limit(1).size().getInfo()
            if count > 0:
                logger.info("Verified GEE dataset: %s", candidate)
                return candidate
        except Exception as exc:
            logger.debug("Candidate %s not accessible: %s", candidate, exc)
    raise RuntimeError(f"None of the candidate datasets were found in GEE: {dataset_candidates}")


def chunk_date_ranges(start_date: date, end_date: date, chunk_days: int = 90) -> List[Tuple[date, date]]:
    """Splits a date interval into consecutive chunks of at most chunk_days."""
    chunks = []
    curr = start_date
    while curr <= end_date:
        next_date = min(end_date, curr + timedelta(days=chunk_days - 1))
        chunks.append((curr, next_date))
        curr = next_date + timedelta(days=1)
    return chunks


def compute_site_total_pixels(ee, ee_geom, scale: int = 30) -> Optional[int]:
    """
    Counts the total number of scale-m pixels covering the site geometry, once
    per site. Used as the denominator for each NDVI composite window's
    valid-pixel fraction, so it isn't recomputed per window.
    """
    def fetch():
        val = (
            ee.Image.constant(1)
            .reduceRegion(reducer=ee.Reducer.count(), geometry=ee_geom, scale=scale, bestEffort=True, maxPixels=1e9)
            .get("constant")
            .getInfo()
        )
        return val

    try:
        val = with_gee_retry(fetch, what="NDVI site pixel count", attempts=5, base_delay=5.0)
        return int(val) if val is not None else None
    except Exception as exc:
        logger.warning("Could not compute total site pixel count for NDVI coverage check: %s", exc)
        return None


def build_safe_ndvi_composite(ee, col, to_ndvi):
    """Median NDVI composite that always carries an "ndvi" band.

    A window with zero acquisitions makes `col.map(to_ndvi).median()` a
    BAND-LESS image, and the caller's `reduceRegion(...).get("ndvi")` then
    raises "Dictionary does not contain key: 'ndvi'". That is a deterministic
    error, which `with_gee_retry` correctly declines to retry — but it was
    surfacing as a permanent layer failure for what is a normal condition:
    Sentinel-2's ~5-day revisit means any window shorter than the revisit (in
    practice the trailing remainder window of a date range) can legitimately
    hold no images.

    Substituting a fully-masked single-image collection keeps the "ndvi" band
    present, so reduceRegion reports mean=null / valid=0 and the caller takes
    its existing no-data path. Windows that do have images are routed through
    the identical `col.map(to_ndvi).median()` expression as before.
    """
    placeholder = (
        ee.Image.constant(0).rename("ndvi").updateMask(ee.Image.constant(0)).toFloat()
    )
    safe_col = ee.ImageCollection(
        ee.Algorithms.If(
            col.size().gt(0), col.map(to_ndvi), ee.ImageCollection([placeholder])
        )
    )
    return ee.Image(safe_col.median())


def fetch_ndvi_composites(
    ee,
    site_key: str,
    ee_geom,
    start_date: date,
    end_date: date,
    composite_days: int = NDVI_COMPOSITE_DAYS,
    min_valid_fraction: float = NDVI_MIN_VALID_FRACTION,
) -> Tuple[List[Tuple[date, date, Optional[float]]], List[Dict[str, Any]]]:
    """
    Fetches Sentinel-2 NDVI as sequential cloud-masked MEDIAN COMPOSITES over
    `composite_days`-day windows, ONE reduceRegion (mean) call per window, run
    sequentially with a pause between windows.

    This deliberately avoids `.map(fn).getInfo()` over a whole collection: that
    pattern fires one reduceRegion per image concurrently server-side and
    reliably trips GEE's "Too many concurrent aggregations" (429) quota once a
    window has more than a couple of Sentinel-2 acquisitions. Here, cloud
    masking + NDVI are still computed per-image via `.map()`, but the
    reduceRegion is only ever run once, against the window's `.median()`
    composite image.

    Returns:
      - window_results: list of (window_start, window_end, ndvi_mean_or_None),
        sorted ascending, covering [start_date, end_date] with no gaps.
      - diagnostics: list of per-window dicts (image_count, ndvi_mean,
        valid_fraction, status) for inspection/verification.
    """
    windows = chunk_date_ranges(start_date, end_date, chunk_days=composite_days)
    total_pixels = compute_site_total_pixels(ee, ee_geom)

    window_results: List[Tuple[date, date, Optional[float]]] = []
    diagnostics: List[Dict[str, Any]] = []

    for w_start, w_end in windows:
        w_start_str = w_start.strftime("%Y-%m-%d")
        w_end_str = w_end.strftime("%Y-%m-%d")
        w_end_exclusive_str = (w_end + timedelta(days=1)).strftime("%Y-%m-%d")

        def fetch_window():
            col = (
                ee.ImageCollection(S2_COLLECTION_ID)
                .filterDate(w_start_str, w_end_exclusive_str)
                .filterBounds(ee_geom)
            )
            count = col.size()

            def to_ndvi(img):
                # mask_s2_clouds() (prospectivity.gee_features) ends in .copyProperties(),
                # which always returns a generic ee.Element (GEE API quirk) — cast back to
                # ee.Image so Image-only methods like normalizedDifference() are available.
                masked = ee.Image(mask_s2_clouds(img, ee))
                return masked.normalizedDifference(["B8", "B4"]).rename("ndvi")

            composite = build_safe_ndvi_composite(ee, col, to_ndvi)
            valid_mask = composite.select("ndvi").mask()

            mean_dict = composite.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=ee_geom, scale=30, bestEffort=True, maxPixels=1e9,
            )
            valid_dict = valid_mask.reduceRegion(
                reducer=ee.Reducer.sum(), geometry=ee_geom, scale=30, bestEffort=True, maxPixels=1e9,
            )
            combined = ee.Dictionary({
                "image_count": count,
                "ndvi_mean": mean_dict.get("ndvi"),
                "valid_pixels": valid_dict.get("ndvi"),
            })
            return combined.getInfo()

        try:
            info = with_gee_retry(
                fetch_window, what=f"S2 NDVI composite {site_key} {w_start_str}", attempts=5, base_delay=5.0
            )
        except Exception as exc:
            logger.warning(
                "NDVI composite failed permanently for %s window %s to %s: %s", site_key, w_start_str, w_end_str, exc
            )
            window_results.append((w_start, w_end, None))
            diagnostics.append({
                "window_start": w_start_str, "window_end": w_end_str,
                "image_count": None, "ndvi_mean": None, "valid_fraction": None, "status": "failed",
            })
            time.sleep(1.0)
            continue

        image_count = int(info.get("image_count") or 0)
        ndvi_mean = info.get("ndvi_mean")
        valid_pixels = info.get("valid_pixels")
        valid_fraction = (
            float(valid_pixels) / float(total_pixels) if (total_pixels and valid_pixels is not None) else None
        )

        if image_count == 0 or ndvi_mean is None:
            window_results.append((w_start, w_end, None))
            status = "no_images" if image_count == 0 else "no_data"
        elif valid_fraction is not None and valid_fraction < min_valid_fraction:
            window_results.append((w_start, w_end, None))
            status = "low_coverage"
        else:
            window_results.append((w_start, w_end, float(ndvi_mean)))
            status = "ok"

        diagnostics.append({
            "window_start": w_start_str,
            "window_end": w_end_str,
            "image_count": image_count,
            "ndvi_mean": round(float(ndvi_mean), 4) if ndvi_mean is not None else None,
            "valid_fraction": round(valid_fraction, 4) if valid_fraction is not None else None,
            "status": status,
        })
        logger.info(
            "NDVI composite %s %s..%s: images=%d ndvi_mean=%s valid_frac=%s status=%s",
            site_key, w_start_str, w_end_str, image_count,
            f"{ndvi_mean:.4f}" if ndvi_mean is not None else "None",
            f"{valid_fraction:.3f}" if valid_fraction is not None else "None",
            status,
        )

        time.sleep(1.0)  # pause between windows to stay under the concurrency quota

    return window_results, diagnostics


def fetch_live_climate_dataset(
    ee,
    sites: List[str],
    shapely_geoms: Dict[str, Any],
    start_date: date,
    end_date: date,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extracts daily satellite features from live Earth Engine using batch reducers
    and chunked queries. NDVI is fetched separately (see fetch_ndvi_composites)
    as sequential median composites, independent of the 90-day chunking used
    for the other products.
    """
    # 1. Dataset verification
    chirps_id = "UCSB-CHG/CHIRPS/DAILY"
    imerg_id = "NASA/GPM_L3/IMERG_V07"
    smap_id = verify_dataset_id(ee, ["NASA/SMAP/SPL4SMGP/008", "NASA/SMAP/SPL4SMGP/007"])
    modis_id = "MODIS/061/MOD11A1"

    curr = start_date
    all_dates: List[date] = []
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    date_chunks = chunk_date_ranges(start_date, end_date, chunk_days=90)
    all_rows: List[Dict[str, Any]] = []

    product_stats = {
        "rainfall": {"dataset_id": chirps_id, "latest_date": None, "valid_count": 0},
        "soil_moisture": {"dataset_id": smap_id, "latest_date": None, "valid_count": 0},
        "lst": {"dataset_id": modis_id, "latest_date": None, "valid_count": 0},
        "ndvi": {
            "dataset_id": S2_COLLECTION_ID,
            "latest_date": None,
            "valid_count": 0,
            "composite_days": NDVI_COMPOSITE_DAYS,
            "method": (
                f"{NDVI_COMPOSITE_DAYS}-day cloud-masked (SCL) median composite; "
                "one reduceRegion(mean) per window, not per image"
            ),
        },
    }

    for site in sites:
        site_key = site.lower()
        geom = shapely_geoms[site_key]
        minx, miny, maxx, maxy = geom.bounds
        ee_geom = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        chirps_data: Dict[date, float] = {}
        imerg_data: Dict[date, float] = {}
        smap_data: Dict[date, float] = {}
        lst_data: Dict[date, float] = {}

        logger.info("Processing site '%s' over %d date chunks...", site_key, len(date_chunks))

        for c_start, c_end in date_chunks:
            c_start_str = c_start.strftime("%Y-%m-%d")
            # GEE end date is exclusive for filterDate
            c_end_exclusive = (c_end + timedelta(days=1)).strftime("%Y-%m-%d")

            # A. CHIRPS Rainfall (Daily mean over site)
            def fetch_chirps():
                col = (
                    ee.ImageCollection(chirps_id)
                    .filterDate(c_start_str, c_end_exclusive)
                    .filterBounds(ee_geom)
                    .select(["precipitation"])
                )
                def reduce_img(img):
                    mean_val = img.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=5566,
                        maxPixels=1e8,
                    ).get("precipitation")
                    return ee.Feature(None, {
                        "date": img.date().format("YYYY-MM-dd"),
                        "val": mean_val,
                    })
                return col.map(reduce_img).getInfo()["features"]

            try:
                features = with_gee_retry(fetch_chirps, what=f"CHIRPS {site_key} {c_start_str}")
                for feat in features:
                    props = feat["properties"]
                    if props.get("val") is not None:
                        d_obj = datetime.strptime(props["date"], "%Y-%m-%d").date()
                        chirps_data[d_obj] = round(float(props["val"]), 2)
            except Exception as exc:
                logger.warning("CHIRPS fetch failed for %s (%s to %s): %s", site_key, c_start_str, c_end_exclusive, exc)

            # B. IMERG Rainfall Fallback (for dates where CHIRPS has gaps)
            def fetch_imerg():
                col = (
                    ee.ImageCollection(imerg_id)
                    .filterDate(c_start_str, c_end_exclusive)
                    .filterBounds(ee_geom)
                    .select(["precipitation"])
                )
                def reduce_img(img):
                    mean_val = img.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=11132,
                        maxPixels=1e8,
                    ).get("precipitation")
                    return ee.Feature(None, {
                        "date": img.date().format("YYYY-MM-dd"),
                        "val": mean_val,
                    })
                return col.map(reduce_img).getInfo()["features"]

            try:
                features = with_gee_retry(fetch_imerg, what=f"IMERG {site_key} {c_start_str}")
                daily_sums: Dict[date, float] = {}
                for feat in features:
                    props = feat["properties"]
                    if props.get("val") is not None:
                        d_obj = datetime.strptime(props["date"], "%Y-%m-%d").date()
                        daily_sums[d_obj] = daily_sums.get(d_obj, 0.0) + float(props["val"])
                for d_obj, h_sum in daily_sums.items():
                    # If CHIRPS does not cover this date, populate IMERG fallback
                    if d_obj not in chirps_data:
                        daily_mm = convert_imerg_daily(h_sum)
                        if daily_mm is not None:
                            imerg_data[d_obj] = daily_mm
            except Exception as exc:
                logger.warning("IMERG fetch failed for %s (%s): %s", site_key, c_start_str, exc)

            # C. SMAP Soil Moisture (Daily mean of 3-hourly)
            def fetch_smap():
                col = (
                    ee.ImageCollection(smap_id)
                    .filterDate(c_start_str, c_end_exclusive)
                    .filterBounds(ee_geom)
                    .select(["sm_surface"])
                )
                def reduce_img(img):
                    mean_val = img.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=9000,
                        maxPixels=1e8,
                    ).get("sm_surface")
                    return ee.Feature(None, {
                        "date": img.date().format("YYYY-MM-dd"),
                        "val": mean_val,
                    })
                return col.map(reduce_img).getInfo()["features"]

            try:
                features = with_gee_retry(fetch_smap, what=f"SMAP {site_key} {c_start_str}")
                smap_daily_accum: Dict[date, List[float]] = {}
                for feat in features:
                    props = feat["properties"]
                    if props.get("val") is not None:
                        d_obj = datetime.strptime(props["date"], "%Y-%m-%d").date()
                        smap_daily_accum.setdefault(d_obj, []).append(float(props["val"]))
                for d_obj, vals in smap_daily_accum.items():
                    smap_data[d_obj] = round(float(np.mean(vals)), 4)
            except Exception as exc:
                logger.warning("SMAP fetch failed for %s (%s): %s", site_key, c_start_str, exc)

            # D. MODIS LST Day with QC Masking
            def fetch_modis():
                col = (
                    ee.ImageCollection(modis_id)
                    .filterDate(c_start_str, c_end_exclusive)
                    .filterBounds(ee_geom)
                    .select(["LST_Day_1km", "QC_Day"])
                )
                def process_lst(img):
                    # Bits 0-1 of QC_Day: 0 = good, 1 = other quality, 2/3 = not produced
                    qc = img.select("QC_Day")
                    valid_mask = qc.bitwiseAnd(2).eq(0)
                    lst_masked = img.select("LST_Day_1km").updateMask(valid_mask)
                    # Compute mean and valid pixel ratio
                    mean_dict = lst_masked.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=1000,
                        maxPixels=1e8,
                    )
                    valid_pixels = valid_mask.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=1000,
                        maxPixels=1e8,
                    ).get("QC_Day")
                    return ee.Feature(None, {
                        "date": img.date().format("YYYY-MM-dd"),
                        "lst_raw": mean_dict.get("LST_Day_1km"),
                        "valid_fraction": valid_pixels,
                    })
                return col.map(process_lst).getInfo()["features"]

            try:
                features = with_gee_retry(fetch_modis, what=f"MODIS LST {site_key} {c_start_str}")
                for feat in features:
                    props = feat["properties"]
                    raw_val = props.get("lst_raw")
                    valid_frac = props.get("valid_fraction")
                    if raw_val is not None and valid_frac is not None and float(valid_frac) >= 0.20:
                        celsius = convert_lst(float(raw_val))
                        if celsius is not None:
                            d_obj = datetime.strptime(props["date"], "%Y-%m-%d").date()
                            lst_data[d_obj] = celsius
            except Exception as exc:
                logger.warning("MODIS LST fetch failed for %s (%s): %s", site_key, c_start_str, exc)

        # NDVI: fetched once per site over the whole [start_date, end_date] range as
        # sequential median composites (see fetch_ndvi_composites), independent of
        # the 90-day chunking above.
        window_results, ndvi_diag = fetch_ndvi_composites(ee, site_key, ee_geom, start_date, end_date)
        ok_windows = sum(1 for d in ndvi_diag if d["status"] == "ok")
        failed_windows = sum(1 for d in ndvi_diag if d["status"] == "failed")
        logger.info(
            "NDVI composites for '%s': %d/%d windows ok, %d failed permanently",
            site_key, ok_windows, len(ndvi_diag), failed_windows,
        )
        ndvi_series = assign_ndvi_window_values(window_results, all_dates)
        rows = merge_daily_features(
            all_dates,
            site_key,
            chirps_data,
            imerg_data,
            smap_data,
            lst_data,
            ndvi_series,
        )
        all_rows.extend(rows)

        # Update stats
        for r in rows:
            dt_val = r["date"]
            if r["rainfall_mm"] is not None:
                product_stats["rainfall"]["valid_count"] += 1
                if not product_stats["rainfall"]["latest_date"] or dt_val > product_stats["rainfall"]["latest_date"]:
                    product_stats["rainfall"]["latest_date"] = dt_val
            if r["soil_moisture_m3m3"] is not None:
                product_stats["soil_moisture"]["valid_count"] += 1
                if not product_stats["soil_moisture"]["latest_date"] or dt_val > product_stats["soil_moisture"]["latest_date"]:
                    product_stats["soil_moisture"]["latest_date"] = dt_val
            if r["lst_day_c"] is not None:
                product_stats["lst"]["valid_count"] += 1
                if not product_stats["lst"]["latest_date"] or dt_val > product_stats["lst"]["latest_date"]:
                    product_stats["lst"]["latest_date"] = dt_val
            if r["ndvi"] is not None:
                product_stats["ndvi"]["valid_count"] += 1
                if not product_stats["ndvi"]["latest_date"] or dt_val > product_stats["ndvi"]["latest_date"]:
                    product_stats["ndvi"]["latest_date"] = dt_val

    all_rows.sort(key=lambda r: (r["site_id"], r["date"]))
    return all_rows, product_stats


# ---------------------------------------------------------------------------
# Exporter Pipeline Entry Point
# ---------------------------------------------------------------------------

def write_outputs(
    rows: List[Dict[str, Any]],
    meta: Dict[str, Any],
    out_csv: str,
    out_meta: str,
) -> None:
    """Writes standardized CSV and metadata JSON files."""
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_meta)), exist_ok=True)

    # 1. Write CSV
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(COLUMNS) + "\n")
        for r in rows:
            line_vals = [
                r["site_id"],
                r["date"],
                format_cell(r["rainfall_mm"], precision=2),
                r["rainfall_source"] or "",
                format_cell(r["soil_moisture_m3m3"], precision=4),
                r["soil_moisture_source"] or "",
                format_cell(r["lst_day_c"], precision=2),
                r["lst_source"] or "",
                format_cell(r["ndvi"], precision=4),
                format_cell(r["ndvi_age_days"]),
                r["ndvi_source"] or "",
            ]
            fh.write(",".join(line_vals) + "\n")

    # 2. Write Meta JSON
    with open(out_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    logger.info("Successfully exported CSV: %s (%d rows)", out_csv, len(rows))
    logger.info("Successfully exported Meta: %s", out_meta)


def print_site_summary(rows: List[Dict[str, Any]], sites: List[str]) -> None:
    """Prints acceptance criteria summary per site."""
    print("\n" + "=" * 76)
    print(" MOIL RESERVE INTELLIGENCE — SATELLITE DAILY CLIMATE EXPORT SUMMARY")
    print("=" * 76)

    for site in sites:
        site_key = site.lower()
        site_rows = [r for r in rows if r["site_id"] == site_key]
        n_total = len(site_rows)
        if n_total == 0:
            continue

        print(f"\nSite: {site_key.upper()} (Total rows: {n_total})")
        print("-" * 50)

        feature_cols = [
            ("Rainfall", "rainfall_mm", "rainfall_source"),
            ("Soil Moisture", "soil_moisture_m3m3", "soil_moisture_source"),
            ("LST Day", "lst_day_c", "lst_source"),
            ("NDVI", "ndvi", "ndvi_source"),
        ]

        for label, val_col, src_col in feature_cols:
            non_null = [r for r in site_rows if r[val_col] is not None and r[val_col] != ""]
            pct = (len(non_null) / n_total) * 100.0
            last_date = max((r["date"] for r in non_null), default="None")
            sources = set(r[src_col] for r in non_null if r[src_col])
            src_str = ", ".join(sources) if sources else "None"
            print(f"  • {label:14s}: {len(non_null):4d}/{n_total} ({pct:5.1f}%) non-missing | Latest: {last_date} | Sources: {src_str}")

        # Monsoon vs pre-monsoon sanity check
        monsoon_rain = [
            float(r["rainfall_mm"])
            for r in site_rows
            if r["rainfall_mm"] is not None and "2025-06-01" <= r["date"] <= "2025-09-30"
        ]
        premonsoon_rain = [
            float(r["rainfall_mm"])
            for r in site_rows
            if r["rainfall_mm"] is not None and "2025-01-01" <= r["date"] <= "2025-04-30"
        ]

        mean_monsoon = np.mean(monsoon_rain) if monsoon_rain else 0.0
        mean_premonsoon = np.mean(premonsoon_rain) if premonsoon_rain else 0.0

        print(f"  • Sanity check (Rainfall):")
        print(f"    - June–Sept 2025 (Monsoon) mean : {mean_monsoon:6.2f} mm/day")
        print(f"    - Jan–April 2025 (Dry) mean     : {mean_premonsoon:6.2f} mm/day")
        if mean_monsoon > mean_premonsoon:
            print("    [PASSED] Monsoon season is clearly wetter than pre-monsoon dry season.")
        else:
            print("    [WARNING] Monsoon rainfall did not exceed dry season rainfall — please inspect!")

    print("=" * 76 + "\n")


def load_csv_rows(csv_path: str) -> List[Dict[str, str]]:
    """Reads the CSV preserving each cell's exact original string — no reparsing
    or reformatting — so non-NDVI columns can be written back byte-identical."""
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"CSV column mismatch: {reader.fieldnames} != {COLUMNS}")
        return list(reader)


def hash_non_ndvi_columns(rows: List[Dict[str, str]]) -> str:
    """SHA-256 over every row's non-NDVI cells, in file order. Used to verify
    --only-ndvi never alters rainfall/soil-moisture/LST data."""
    h = hashlib.sha256()
    for r in rows:
        h.update("|".join(r[c] for c in NON_NDVI_COLUMNS).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def write_csv_rows(csv_path: str, rows: List[Dict[str, str]]) -> None:
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(COLUMNS) + "\n")
        for r in rows:
            fh.write(",".join(r[c] for c in COLUMNS) + "\n")


def run_ndvi_only_update(
    start_str: str = "2025-01-01",
    end_str: Optional[str] = None,
    sites: Optional[List[str]] = None,
    out_csv: Optional[str] = None,
    out_meta: Optional[str] = None,
    geometry_source: str = "db",
) -> None:
    """
    Re-fetches ONLY NDVI (live GEE, median-composite method) for the given date
    range and sites, and merges it into the existing CSV in place. Rainfall,
    soil moisture, and LST cells are carried over byte-for-byte unchanged from
    the existing file — verified with a before/after hash of those columns;
    the write is refused if that hash ever changes.
    """
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else datetime.now(timezone.utc).date()
    if start_date > end_date:
        raise ValueError(f"Start date ({start_date}) cannot be after end date ({end_date}).")

    target_sites = [s.strip().lower() for s in (sites or DEFAULT_SITES)]
    csv_path = out_csv or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.csv")
    meta_path = out_meta or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.meta.json")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"--only-ndvi requires an existing CSV at {csv_path}")

    logger.info("NDVI-only update: %s to %s for sites: %s", start_date, end_date, target_sites)

    rows = load_csv_rows(csv_path)
    before_hash = hash_non_ndvi_columns(rows)
    row_index = {(r["site_id"], r["date"]): r for r in rows}

    ee = get_ee(dry_run=False)
    if ee is None:
        raise RuntimeError("--only-ndvi requires live Earth Engine; dry-run is not supported for this mode.")

    shapely_geoms, geom_sources = resolve_site_geometries(target_sites, geometry_source)

    curr = start_date
    all_dates: List[date] = []
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    total_updated = 0
    total_skipped_no_row = 0
    per_site_diag: Dict[str, List[Dict[str, Any]]] = {}
    ndvi_valid_count = 0
    ndvi_latest_date = None

    for site in target_sites:
        site_key = site.lower()
        geom = shapely_geoms[site_key]
        minx, miny, maxx, maxy = geom.bounds
        ee_geom = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        window_results, diag = fetch_ndvi_composites(ee, site_key, ee_geom, start_date, end_date)
        per_site_diag[site_key] = diag
        ndvi_series = assign_ndvi_window_values(window_results, all_dates)

        for i, dt in enumerate(all_dates):
            dt_str = dt.strftime("%Y-%m-%d")
            key = (site_key, dt_str)
            row = row_index.get(key)
            if row is None:
                total_skipped_no_row += 1
                continue
            val, age, src = ndvi_series[i]
            row["ndvi"] = format_cell(val, precision=4)
            row["ndvi_age_days"] = format_cell(age)
            row["ndvi_source"] = src or ""
            total_updated += 1
            if val is not None:
                ndvi_valid_count += 1
                if ndvi_latest_date is None or dt_str > ndvi_latest_date:
                    ndvi_latest_date = dt_str

    after_hash = hash_non_ndvi_columns(rows)
    if before_hash != after_hash:
        raise RuntimeError(
            "--only-ndvi integrity check failed: rainfall/soil-moisture/LST columns "
            "changed in memory. Aborting write — CSV on disk is untouched."
        )
    logger.info("Integrity check passed: rainfall/soil-moisture/LST columns unchanged (hash %s...).", before_hash[:12])

    write_csv_rows(csv_path, rows)
    logger.info(
        "NDVI-only update complete: %d row-dates updated, %d had no matching existing CSV row.",
        total_updated, total_skipped_no_row,
    )

    meta: Dict[str, Any] = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)

    meta["generated_at"] = datetime.now(timezone.utc).isoformat()
    meta.setdefault("products", {})
    meta["products"]["ndvi"] = {
        "dataset_id": S2_COLLECTION_ID,
        "band": "NDVI=(B8-B4)/(B8+B4)",
        "scale_m": 30,
        "units": "unitless [-1, 1]",
        "latest_valid_date": ndvi_latest_date,
        "valid_day_count": ndvi_valid_count,
        "composite_days": NDVI_COMPOSITE_DAYS,
        "method": (
            f"{NDVI_COMPOSITE_DAYS}-day cloud-masked (SCL) median composite; "
            "one reduceRegion(mean) per window, not per image"
        ),
        "min_valid_pixel_fraction": NDVI_MIN_VALID_FRACTION,
        "last_ndvi_only_update": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "sites": target_sites,
        },
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    logger.info("Updated meta.json NDVI block and generated_at.")

    print("\n" + "=" * 76)
    print(" NDVI-ONLY UPDATE SUMMARY")
    print("=" * 76)
    for site_key, diag in per_site_diag.items():
        ok = sum(1 for d in diag if d["status"] == "ok")
        failed = sum(1 for d in diag if d["status"] == "failed")
        no_img = sum(1 for d in diag if d["status"] == "no_images")
        low_cov = sum(1 for d in diag if d["status"] == "low_coverage")
        print(f"  {site_key}: {ok}/{len(diag)} windows ok | failed={failed} no_images={no_img} low_coverage={low_cov}")
    print(f"  Non-NDVI columns verified byte-for-byte unchanged (hash {before_hash[:12]}...).")
    print("=" * 76 + "\n")


def run_export(
    start_str: str = "2025-01-01",
    end_str: Optional[str] = None,
    sites: Optional[List[str]] = None,
    dry_run: bool = False,
    out_csv: Optional[str] = None,
    out_meta: Optional[str] = None,
    geometry_source: str = "db",
) -> None:
    """Orchestrates daily climate data export."""
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    if end_str:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    else:
        end_date = datetime.now(timezone.utc).date()

    if start_date > end_date:
        raise ValueError(f"Start date ({start_date}) cannot be after end date ({end_date}).")

    target_sites = [s.strip().lower() for s in (sites or DEFAULT_SITES)]
    csv_path = out_csv or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.csv")
    meta_path = out_meta or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.meta.json")

    logger.info("Initializing daily climate export: %s to %s for sites: %s", start_date, end_date, target_sites)
    shapely_geoms, geom_sources = resolve_site_geometries(target_sites, geometry_source)

    ee = get_ee(dry_run=dry_run)

    if dry_run or ee is None:
        rows, product_stats = generate_dry_run_dataset(target_sites, start_date, end_date)
        is_simulated = True
        dataset_meta = {
            "rainfall": {
                "dataset_id": "UCSB-CHG/CHIRPS/DAILY + NASA/GPM_L3/IMERG_V07",
                "band": "precipitation",
                "scale_m": 5566,
                "units": "mm/day",
                "latest_valid_date": product_stats["rainfall"]["latest_date"],
                "valid_day_count": product_stats["rainfall"]["valid_count"],
            },
            "soil_moisture": {
                "dataset_id": "NASA/SMAP/SPL4SMGP/008",
                "band": "sm_surface",
                "scale_m": 9000,
                "units": "m3/m3",
                "latest_valid_date": product_stats["soil_moisture"]["latest_date"],
                "valid_day_count": product_stats["soil_moisture"]["valid_count"],
            },
            "lst": {
                "dataset_id": "MODIS/061/MOD11A1",
                "band": "LST_Day_1km",
                "scale_m": 1000,
                "units": "deg_c",
                "latest_valid_date": product_stats["lst"]["latest_date"],
                "valid_day_count": product_stats["lst"]["valid_count"],
            },
            "ndvi": {
                "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
                "band": "NDVI=(B8-B4)/(B8+B4)",
                "scale_m": 30,
                "units": "unitless [-1, 1]",
                "latest_valid_date": product_stats["ndvi"]["latest_date"],
                "valid_day_count": product_stats["ndvi"]["valid_count"],
            },
        }
    else:
        rows, product_stats = fetch_live_climate_dataset(ee, target_sites, shapely_geoms, start_date, end_date)
        is_simulated = False
        dataset_meta = {
            "rainfall": {
                "dataset_id": "UCSB-CHG/CHIRPS/DAILY + NASA/GPM_L3/IMERG_V07",
                "band": "precipitation",
                "scale_m": 5566,
                "units": "mm/day",
                "latest_valid_date": product_stats["rainfall"]["latest_date"],
                "valid_day_count": product_stats["rainfall"]["valid_count"],
            },
            "soil_moisture": {
                "dataset_id": product_stats["soil_moisture"].get("dataset_id", "NASA/SMAP/SPL4SMGP/008"),
                "band": "sm_surface",
                "scale_m": 9000,
                "units": "m3/m3",
                "latest_valid_date": product_stats["soil_moisture"]["latest_date"],
                "valid_day_count": product_stats["soil_moisture"]["valid_count"],
            },
            "lst": {
                "dataset_id": "MODIS/061/MOD11A1",
                "band": "LST_Day_1km",
                "scale_m": 1000,
                "units": "deg_c",
                "latest_valid_date": product_stats["lst"]["latest_date"],
                "valid_day_count": product_stats["lst"]["valid_count"],
            },
            "ndvi": {
                "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
                "band": "NDVI=(B8-B4)/(B8+B4)",
                "scale_m": 30,
                "units": "unitless [-1, 1]",
                "latest_valid_date": product_stats["ndvi"]["latest_date"],
                "valid_day_count": product_stats["ndvi"]["valid_count"],
                "composite_days": product_stats["ndvi"].get("composite_days"),
                "method": product_stats["ndvi"].get("method"),
                "min_valid_pixel_fraction": NDVI_MIN_VALID_FRACTION,
            },
        }

    meta = {
        "pipeline": "MOIL Reserve Intelligence — Site Daily Climate & Satellite Exporter",
        "script_version": SCRIPT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d"),
        "simulated": is_simulated,
        "geometry_source": geom_sources,
        "products": dataset_meta,
        "columns": COLUMNS,
    }

    write_outputs(rows, meta, csv_path, meta_path)
    print_site_summary(rows, target_sites)


def main():
    parser = argparse.ArgumentParser(
        description="Export daily satellite features (rainfall, soil moisture, LST, NDVI) per site."
    )
    parser.add_argument("--start", default="2025-01-01", help="Start date (YYYY-MM-DD, default 2025-01-01).")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD, default today UTC).")
    parser.add_argument("--sites", default="balaghat,nagpur,bhandara", help="Comma-separated site list.")
    parser.add_argument("--dry-run", action="store_true", help="Generate deterministic simulated data without GEE.")
    parser.add_argument(
        "--geometry-source", choices=["db", "file"], default="db",
        help="Where site AOI polygons come from: 'db' (PostGIS sites.geom, the default -- "
             "a DB failure is an error, not a silent substitution) or 'file' "
             "(data/moil_sites.json, the same AOIs, chosen explicitly).",
    )
    parser.add_argument("--out-csv", default=None, help="Custom output CSV path.")
    parser.add_argument("--out-meta", default=None, help="Custom output metadata JSON path.")
    parser.add_argument(
        "--only-ndvi", action="store_true",
        help="Re-fetch ONLY NDVI (live) and merge into the existing CSV, leaving rainfall/"
             "soil-moisture/LST columns byte-for-byte unchanged. Requires an existing CSV "
             "and live GEE credentials (incompatible with --dry-run).",
    )

    args = parser.parse_args()
    site_list = [s.strip() for s in args.sites.split(",") if s.strip()]

    if args.only_ndvi:
        if args.dry_run:
            raise SystemExit("--only-ndvi and --dry-run are mutually exclusive.")
        run_ndvi_only_update(
            start_str=args.start,
            end_str=args.end,
            sites=site_list,
            out_csv=args.out_csv,
            out_meta=args.out_meta,
            geometry_source=args.geometry_source,
        )
        return

    run_export(
        start_str=args.start,
        end_str=args.end,
        sites=site_list,
        dry_run=args.dry_run,
        out_csv=args.out_csv,
        out_meta=args.out_meta,
        geometry_source=args.geometry_source,
    )


if __name__ == "__main__":
    main()
