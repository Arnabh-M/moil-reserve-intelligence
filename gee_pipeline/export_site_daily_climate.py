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
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import logging
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from gee_pipeline.ee_auth import get_ee
from geo_utils import SITE_BBOXES

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

def resolve_site_geometries(sites: List[str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Attempts to load site boundary polygons from database if reachable;
    otherwise falls back to geo_utils.SITE_BBOXES rectangles.
    Returns: (shapely_geoms, geometry_sources)
    """
    from shapely.geometry import box

    db_url = os.environ.get("DATABASE_URL")
    shapely_geoms: Dict[str, Any] = {}
    geom_sources: Dict[str, str] = {}

    if db_url:
        try:
            from prospectivity.training_data import load_site_boundaries
            db_sites = load_site_boundaries(db_url)
            for s in sites:
                s_key = s.lower()
                if s_key in db_sites:
                    shapely_geoms[s_key] = db_sites[s_key]["geom"]
                    geom_sources[s_key] = "db_polygon"
                    logger.info("Loaded site '%s' geometry from PostGIS boundary polygon.", s_key)
        except Exception as exc:
            logger.info("Database boundary load skipped (%s). Using geo_utils.SITE_BBOXES.", exc)

    for s in sites:
        s_key = s.lower()
        if s_key not in shapely_geoms:
            if s_key not in SITE_BBOXES:
                raise ValueError(f"Unknown site '{s}'. Must be one of {list(SITE_BBOXES.keys())}.")
            bbox = SITE_BBOXES[s_key]
            lat_lo, lat_hi = bbox["lat_range"]
            lon_lo, lon_hi = bbox["lon_range"]
            shapely_geoms[s_key] = box(lon_lo, lat_lo, lon_hi, lat_hi)
            geom_sources[s_key] = "bbox"
            logger.info("Site '%s' geometry set from geo_utils.SITE_BBOXES rectangle.", s_key)

    return shapely_geoms, geom_sources


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


def fetch_live_climate_dataset(
    ee,
    sites: List[str],
    shapely_geoms: Dict[str, Any],
    start_date: date,
    end_date: date,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extracts daily satellite features from live Earth Engine using batch reducers
    and chunked queries.
    """
    from prospectivity.gee_features import mask_s2_clouds, with_gee_retry

    # 1. Dataset verification
    chirps_id = "UCSB-CHG/CHIRPS/DAILY"
    imerg_id = "NASA/GPM_L3/IMERG_V07"
    smap_id = verify_dataset_id(ee, ["NASA/SMAP/SPL4SMGP/008", "NASA/SMAP/SPL4SMGP/007"])
    modis_id = "MODIS/061/MOD11A1"
    s2_id = "COPERNICUS/S2_SR_HARMONIZED"

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
        "ndvi": {"dataset_id": s2_id, "latest_date": None, "valid_count": 0},
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
        acquisitions: Dict[date, float] = {}

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

            # E. Sentinel-2 NDVI with SCL Cloud Masking
            def fetch_s2():
                col = (
                    ee.ImageCollection(s2_id)
                    .filterDate(c_start_str, c_end_exclusive)
                    .filterBounds(ee_geom)
                )
                def process_s2(img):
                    # mask_s2_clouds() ends in .copyProperties(), which always returns a
                    # generic ee.Element (GEE API quirk) — cast back to ee.Image so
                    # Image-only methods like normalizedDifference() are available.
                    masked = ee.Image(mask_s2_clouds(img, ee))
                    ndvi = masked.normalizedDifference(["B8", "B4"]).rename("ndvi")
                    # Clear mask is where mask == 1
                    clear_mask = masked.select("B4").mask()
                    mean_dict = ndvi.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=30,
                        bestEffort=True,
                        tileScale=4,
                        maxPixels=1e8,
                    )
                    clear_fraction = clear_mask.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_geom,
                        scale=30,
                        bestEffort=True,
                        tileScale=4,
                        maxPixels=1e8,
                    ).get("B4")
                    return ee.Feature(None, {
                        "date": img.date().format("YYYY-MM-dd"),
                        "ndvi": mean_dict.get("ndvi"),
                        "clear_fraction": clear_fraction,
                    })
                return col.map(process_s2).getInfo()["features"]

            try:
                features = with_gee_retry(fetch_s2, what=f"Sentinel-2 NDVI {site_key} {c_start_str}")
                for feat in features:
                    props = feat["properties"]
                    ndvi_val = props.get("ndvi")
                    clear_frac = props.get("clear_fraction")
                    if ndvi_val is not None and clear_frac is not None and float(clear_frac) >= 0.30:
                        d_obj = datetime.strptime(props["date"], "%Y-%m-%d").date()
                        acquisitions[d_obj] = round(float(ndvi_val), 4)
            except Exception as exc:
                logger.warning("Sentinel-2 fetch failed for %s (%s): %s", site_key, c_start_str, exc)

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


def run_export(
    start_str: str = "2025-01-01",
    end_str: Optional[str] = None,
    sites: Optional[List[str]] = None,
    dry_run: bool = False,
    out_csv: Optional[str] = None,
    out_meta: Optional[str] = None,
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
    shapely_geoms, geom_sources = resolve_site_geometries(target_sites)

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
    parser.add_argument("--out-csv", default=None, help="Custom output CSV path.")
    parser.add_argument("--out-meta", default=None, help="Custom output metadata JSON path.")

    args = parser.parse_args()
    site_list = [s.strip() for s in args.sites.split(",") if s.strip()]

    run_export(
        start_str=args.start,
        end_str=args.end,
        sites=site_list,
        dry_run=args.dry_run,
        out_csv=args.out_csv,
        out_meta=args.out_meta,
    )


if __name__ == "__main__":
    main()
