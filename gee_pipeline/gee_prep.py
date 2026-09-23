"""
MOIL Reserve Intelligence - Sentinel-2 GEE Data Preparation Pipeline
====================================================================
Standalone pipeline for extracting satellite remote sensing indices
(NDVI & Iron-Oxide Alteration Index) from Sentinel-2 Level-2A Surface
Reflectance imagery via Google Earth Engine (GEE).

Designed for consumption by:
- FastAPI backend (data ingestion & raster serving)
- MapLibre GL frontend (geospatial raster overlay & time-slider)

Outputs:
- Single-date GeoTIFFs: NDVI & Iron-Oxide Alteration Index
- 4-week Time-series GeoTIFFs: Weekly NDVI rasters for UI time-slider
- Metadata JSON: Bounding box, CRS, color ramps, and timestamp manifest
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.error

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from geo_utils import COMBINED_BBOX
from gee_pipeline.ee_auth import get_ee

# ---------------------------------------------------------------------------
# Global Configuration & Combined Mining Belt Bounding Box
# ---------------------------------------------------------------------------

# Format: [min_lon (West), min_lat (South), max_lon (East), max_lat (North)]
# Covers Balaghat (MP), Nagpur & Bhandara (MH) manganese mining belt
DEFAULT_BBOX = list(COMBINED_BBOX)  # [west, south, east, north] from data/moil_sites.json

DEFAULT_EXPORT_SCALE = 250
DEFAULT_CRS = "EPSG:4326"


# ---------------------------------------------------------------------------
# Earth Engine Sentinel-2 Query & Index Calculation Functions
# ---------------------------------------------------------------------------

def get_roi_geometry(ee_module, bbox=None):
    """
    Converts a bounding box [min_lon, min_lat, max_lon, max_lat] into an
    Earth Engine Geometry Rectangle object.
    """
    if bbox is None:
        bbox = DEFAULT_BBOX
    return ee_module.Geometry.Rectangle(bbox)


def mask_s2_clouds(image, ee_module):
    """
    Masks cloud shadow, medium/high cloud probability, and thin cirrus
    using the Sentinel-2 L2A Scene Classification Layer (SCL: 3, 8, 9, 10).
    """
    scl = image.select("SCL")
    mask = ee_module.Image.constant(1)
    for val in [3, 8, 9, 10]:  # 3=shadow, 8=med cloud, 9=high cloud, 10=cirrus
        mask = mask.And(scl.neq(val))
    # .copyProperties() always returns a generic ee.Element (GEE API quirk) —
    # cast back to ee.Image so Image-only methods stay available downstream.
    return ee_module.Image(
        image.updateMask(mask).copyProperties(image, ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "PRODUCT_ID"])
    )


def fetch_least_cloudy_sentinel2(ee_module, roi, start_date: str, end_date: str, max_cloud_percent: float = 30.0):
    """
    Queries the Sentinel-2 Level-2A (Bottom of Atmosphere / Surface Reflectance)
    harmonized collection for the ROI and date range, filtered to the least cloudy scene.
    Applies SCL cloud masking.

    Bands of interest:
    - B2: Blue (490 nm, 10m)
    - B4: Red (665 nm, 10m)
    - B8: NIR (842 nm, 10m)
    - SCL: Scene Classification Layer (20m)
    """
    collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .filter(ee_module.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent))

    count = collection.size().getInfo()
    effective_cloud_filter = max_cloud_percent

    if count == 0:
        print(f"[WARN] No scenes with < {max_cloud_percent}% clouds found between {start_date} and {end_date}. Widening cloud filter...")
        collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(roi) \
            .filterDate(start_date, end_date)
        count = collection.size().getInfo()
        effective_cloud_filter = 100.0
        if count == 0:
            raise RuntimeError(f"No Sentinel-2 imagery available for the region between {start_date} and {end_date} (image_count == 0).")

    best_image = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()
    masked_image = mask_s2_clouds(best_image, ee_module)

    metadata = best_image.toDictionary(["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "PRODUCT_ID"]).getInfo()
    acquisition_timestamp_ms = metadata.get("system:time_start", 0)
    acquisition_date = datetime.fromtimestamp(acquisition_timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    cloud_pct = metadata.get("CLOUDY_PIXEL_PERCENTAGE", None)

    print(f"[GEE] Selected S2 Image: Product ID {metadata.get('PRODUCT_ID', 'N/A')}")
    print(f"      Acquisition Date: {acquisition_date} | Cloud Cover: {cloud_pct:.2f}% | Total matching images: {count}" if cloud_pct is not None else f"Acquisition Date: {acquisition_date}")

    return masked_image, acquisition_date, metadata, count, effective_cloud_filter


def compute_spectral_indices(ee_module, s2_image):
    """
    Computes spectral indices for vegetation and mineral exploration:
    1. NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)
    2. Iron-Oxide Alteration Index = Red / Blue = B4 / B2
    """
    ndvi = s2_image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    iron_oxide = s2_image.select("B4").divide(s2_image.select("B2")).rename("iron_oxide")
    return ndvi, iron_oxide


def download_geotiff(ee_module, ee_image, roi, output_filepath: str, scale: int = DEFAULT_EXPORT_SCALE, crs: str = DEFAULT_CRS):
    """
    Downloads an Earth Engine image directly as a portable GeoTIFF file via GEE's
    getDownloadURL endpoint and saves it to local disk.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

    download_params = {
        "scale": scale,
        "crs": crs,
        "region": roi,
        "format": "GEO_TIFF"
    }

    print(f"[GEE] Requesting download URL for {os.path.basename(output_filepath)} (scale: {scale}m)...")
    url = ee_image.getDownloadURL(download_params)

    urllib.request.urlretrieve(url, output_filepath)
    file_size_kb = os.path.getsize(output_filepath) / 1024.0
    print(f"[OK] Downloaded: {output_filepath} ({file_size_kb:.1f} KB)")
    return output_filepath


def to_repo_relpath(path: str) -> str:
    """Converts any path into a repo-relative forward-slash path."""
    rel = os.path.relpath(os.path.abspath(path), REPO_ROOT)
    return rel.replace("\\", "/")


# ---------------------------------------------------------------------------
# Weekly NDVI Time-Series
# ---------------------------------------------------------------------------

def get_ndvi_timeseries(ee_module, roi, end_date=None, num_weeks: int = 4, interval_days: int = 7,
                        scale: int = DEFAULT_EXPORT_SCALE, output_dir: str = "output"):
    """
    Computes and exports NDVI GeoTIFFs across consecutive weekly intervals leading up to end_date.
    In real mode, fails loudly if any weekly interval has image_count == 0.
    """
    if end_date is None:
        end_dt = datetime.now(timezone.utc)
    elif isinstance(end_date, str):
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_dt = end_date

    os.makedirs(output_dir, exist_ok=True)
    timeseries_manifest = []

    print(f"\n[GEE] Starting {num_weeks}-week NDVI Time-Series generation...")

    for i in range(num_weeks):
        week_num = i + 1
        w_end = end_dt - timedelta(days=(num_weeks - 1 - i) * interval_days)
        w_start = w_end - timedelta(days=interval_days)

        start_str = w_start.strftime("%Y-%m-%d")
        end_str = w_end.strftime("%Y-%m-%d")

        print(f"\n--- Week {week_num}/{num_weeks}: Window {start_str} to {end_str} ---")

        if ee_module is not None:
            collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(roi) \
                .filterDate(start_str, end_str)

            count = collection.size().getInfo()
            if count == 0:
                # Documented fallback: expand window with a 7-day prior lookback
                lookback_start = (w_start - timedelta(days=7)).strftime("%Y-%m-%d")
                print(f"[WARN] No scenes in week {week_num} ({start_str} to {end_str}). Expanding window to {lookback_start}...")
                collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(roi) \
                    .filterDate(lookback_start, end_str)
                count = collection.size().getInfo()
                if count == 0:
                    raise RuntimeError(f"No Sentinel-2 scenes available for Week {week_num} (window {start_str} to {end_str}, lookback {lookback_start}; image_count == 0).")

            best_img = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()
            masked_img = mask_s2_clouds(best_img, ee_module)
            ndvi_img = masked_img.normalizedDifference(["B8", "B4"]).rename("NDVI")

            meta = best_img.toDictionary(["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "PRODUCT_ID"]).getInfo()
            time_ms = meta.get("system:time_start", 0)
            acq_date = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

            filename = f"ndvi_week_{week_num}_{acq_date}.tif"
            filepath = os.path.join(output_dir, filename)

            download_geotiff(ee_module, ndvi_img, roi, filepath, scale=scale)

            timeseries_manifest.append({
                "week_index": week_num,
                "window_start": start_str,
                "window_end": end_str,
                "acquisition_date": acq_date,
                "cloud_cover_pct": meta.get("CLOUDY_PIXEL_PERCENTAGE"),
                "image_count": count,
                "source": "COPERNICUS/S2_SR_HARMONIZED",
                "date_range": [start_str, end_str],
                "filename": filename,
                "filepath": to_repo_relpath(filepath),
                "index_type": "NDVI",
                "simulated": False
            })
        else:
            # Dry-run mock output
            sim_date = w_end.strftime("%Y-%m-%d")
            filename = f"ndvi_week_{week_num}_{sim_date}.tif"
            filepath = os.path.join(output_dir, filename)
            timeseries_manifest.append({
                "week_index": week_num,
                "window_start": start_str,
                "window_end": end_str,
                "acquisition_date": sim_date,
                "cloud_cover_pct": 5.0 + i * 2.5,
                "image_count": 0,
                "source": "SIMULATED_MOCK",
                "date_range": [start_str, end_str],
                "filename": filename,
                "filepath": to_repo_relpath(filepath),
                "index_type": "NDVI",
                "simulated": True
            })

    return timeseries_manifest


def simulate_dry_run_exports(output_dir: str):
    """
    Creates dummy raster placeholder files during dry-run mode so the full
    end-to-end file pipeline, paths, and manifest can be verified offline.
    """
    os.makedirs(output_dir, exist_ok=True)
    sample_files = [
        "ndvi_latest.tif",
        "iron_oxide_latest.tif",
        "ndvi_week_1_sample.tif",
        "ndvi_week_2_sample.tif",
        "ndvi_week_3_sample.tif",
        "ndvi_week_4_sample.tif"
    ]
    for fname in sample_files:
        fpath = os.path.join(output_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, "wb") as f:
                f.write(b"TIFF_SIMULATED_MOCK_GEOTIFF_FOR_TESTING")


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(output_dir: str = "gee_pipeline/output", scale: int = DEFAULT_EXPORT_SCALE, dry_run: bool = False, bbox=None):
    """
    Executes the complete Sentinel-2 GEE data preparation pipeline.
    """
    print("=" * 70)
    print(" MOIL Reserve Intelligence — Sentinel-2 Data Preparation Pipeline")
    print("=" * 70)

    if bbox is None:
        bbox = DEFAULT_BBOX

    os.makedirs(output_dir, exist_ok=True)

    # 1. Unified Earth Engine verification
    ee_mod = get_ee(dry_run=dry_run)

    print(f"\n[1/5] Target District Bounding Box: {bbox}")
    print("      Coverage: Balaghat (MP), Nagpur & Bhandara (MH) Manganese Belt (geo_utils.COMBINED_BBOX)")

    today = datetime.now(timezone.utc)
    thirty_days_ago = today - timedelta(days=30)
    start_date_str = thirty_days_ago.strftime("%Y-%m-%d")
    end_date_str = today.strftime("%Y-%m-%d")

    manifest = {
        "pipeline": "MOIL Reserve Intelligence - Sentinel-2 GEE Prep",
        "generated_at": today.isoformat(),
        "crs": DEFAULT_CRS,
        "export_scale_meters": scale,
        "bounding_box": {
            "min_lon": bbox[0],
            "min_lat": bbox[1],
            "max_lon": bbox[2],
            "max_lat": bbox[3],
            "format": "[minX, minY, maxX, maxY] (WGS84 EPSG:4326)"
        },
        "single_layers": {},
        "timeseries": []
    }

    if ee_mod is not None:
        roi = get_roi_geometry(ee_mod, bbox)

        print(f"\n[2/5] Searching for least-cloudy Sentinel-2 SR scene ({start_date_str} to {end_date_str})...")
        s2_img, acq_date, metadata, count, eff_cloud_pct = fetch_least_cloudy_sentinel2(
            ee_mod, roi, start_date=start_date_str, end_date=end_date_str, max_cloud_percent=20.0
        )

        print("\n[3/5] Computing Spectral Indices with SCL Cloud Masking:")
        print("      - NDVI = (NIR - Red) / (NIR + Red) -> (B8 - B4) / (B8 + B4)")
        print("      - Iron-Oxide Alteration = Red / Blue -> B4 / B2")
        ndvi_image, iron_oxide_image = compute_spectral_indices(ee_mod, s2_img)

        print(f"\n[4/5] Exporting single-date GeoTIFFs (Scale: {scale}m)...")
        ndvi_path = os.path.join(output_dir, f"ndvi_{acq_date}.tif")
        download_geotiff(ee_mod, ndvi_image, roi, ndvi_path, scale=scale)

        iron_oxide_path = os.path.join(output_dir, f"iron_oxide_{acq_date}.tif")
        download_geotiff(ee_mod, iron_oxide_image, roi, iron_oxide_path, scale=scale)

        manifest["single_layers"] = {
            "ndvi": {
                "name": "Normalized Difference Vegetation Index (NDVI)",
                "formula": "(B8 - B4) / (B8 + B4)",
                "source": "COPERNICUS/S2_SR_HARMONIZED",
                "date_range": [start_date_str, end_date_str],
                "cloud_filter_pct": eff_cloud_pct,
                "image_count": count,
                "acquisition_date": acq_date,
                "filepath": to_repo_relpath(ndvi_path),
                "filename": os.path.basename(ndvi_path),
                "value_range": [-1.0, 1.0],
                "recommended_palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"],
                "simulated": False
            },
            "iron_oxide": {
                "name": "Iron-Oxide Alteration Index",
                "formula": "B4 / B2 (Red / Blue)",
                "source": "COPERNICUS/S2_SR_HARMONIZED",
                "date_range": [start_date_str, end_date_str],
                "cloud_filter_pct": eff_cloud_pct,
                "image_count": count,
                "acquisition_date": acq_date,
                "filepath": to_repo_relpath(iron_oxide_path),
                "filename": os.path.basename(iron_oxide_path),
                "value_range": [0.5, 3.5],
                "recommended_palette": ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"],
                "simulated": False
            }
        }

        print("\n[5/5] Generating 4-week weekly NDVI time-series for MapLibre Time-Slider...")
        ts_data = get_ndvi_timeseries(ee_mod, roi, end_date=today, num_weeks=4, interval_days=7, scale=scale, output_dir=output_dir)
        manifest["timeseries"] = ts_data

    else:
        # Offline dry-run simulation
        simulate_dry_run_exports(output_dir)
        sim_date = today.strftime("%Y-%m-%d")
        ndvi_path = os.path.join(output_dir, "ndvi_latest.tif")
        iron_oxide_path = os.path.join(output_dir, "iron_oxide_latest.tif")

        manifest["single_layers"] = {
            "ndvi": {
                "name": "Normalized Difference Vegetation Index (NDVI)",
                "formula": "(B8 - B4) / (B8 + B4)",
                "source": "SIMULATED_MOCK",
                "date_range": [start_date_str, end_date_str],
                "cloud_filter_pct": 20.0,
                "image_count": 0,
                "acquisition_date": sim_date,
                "filepath": to_repo_relpath(ndvi_path),
                "filename": os.path.basename(ndvi_path),
                "simulated": True
            },
            "iron_oxide": {
                "name": "Iron-Oxide Alteration Index",
                "formula": "B4 / B2 (Red / Blue)",
                "source": "SIMULATED_MOCK",
                "date_range": [start_date_str, end_date_str],
                "cloud_filter_pct": 20.0,
                "image_count": 0,
                "acquisition_date": sim_date,
                "filepath": to_repo_relpath(iron_oxide_path),
                "filename": os.path.basename(iron_oxide_path),
                "simulated": True
            }
        }
        ts_data = get_ndvi_timeseries(None, None, end_date=today, num_weeks=4, interval_days=7, scale=scale, output_dir=output_dir)
        manifest["timeseries"] = ts_data

    manifest_path = os.path.join(output_dir, "gee_export_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[OK] Manifest saved: {manifest_path} (repo-relative: {to_repo_relpath(manifest_path)})")

    print("\n" + "=" * 70)
    print(" EXPORT PIPELINE SUMMARY")
    print("=" * 70)
    print(f"Output Directory : {os.path.abspath(output_dir)}")
    print(f"Bounding Box     : {bbox}")
    print(f"CRS              : {DEFAULT_CRS}")
    print(f"Scale            : {scale} meters/pixel")
    print("\nGenerated Artifacts:")
    if "ndvi" in manifest["single_layers"]:
        print(f"  [1] Single NDVI GeoTIFF        -> {manifest['single_layers']['ndvi']['filename']} (simulated: {manifest['single_layers']['ndvi'].get('simulated')})")
    if "iron_oxide" in manifest["single_layers"]:
        print(f"  [2] Alteration Index GeoTIFF   -> {manifest['single_layers']['iron_oxide']['filename']} (simulated: {manifest['single_layers']['iron_oxide'].get('simulated')})")
    print(f"  [3] Weekly Time-Series GeoTIFFs -> {len(manifest['timeseries'])} weekly rasters:")
    for ts in manifest["timeseries"]:
        print(f"      - Week {ts['week_index']} ({ts['window_start']} to {ts['window_end']}): {ts['filename']}")
    print(f"  [4] Manifest JSON Metadata      -> gee_export_manifest.json")
    print("=" * 70)

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MOIL Reserve Intelligence - Sentinel-2 GEE Data Prep Pipeline"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=os.path.join(REPO_ROOT, "gee_pipeline", "output"),
        help="Target folder for exported GeoTIFFs and manifest JSON (default: gee_pipeline/output)"
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=DEFAULT_EXPORT_SCALE,
        help="Export resolution scale in meters per pixel (default: 250 for fast web overlays)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the pipeline offline without making live Earth Engine calls"
    )

    args = parser.parse_args()
    run_pipeline(output_dir=args.out_dir, scale=args.scale, dry_run=args.dry_run)
