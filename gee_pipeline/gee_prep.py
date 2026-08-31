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

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Global Configuration & MOIL Mining Belt Bounding Box
# ---------------------------------------------------------------------------

# Bounding box coordinates covering the primary MOIL manganese mining belt:
# Balaghat district (Madhya Pradesh), Nagpur & Bhandara districts (Maharashtra).
# Format: [min_lon (West), min_lat (South), max_lon (East), max_lat (North)]
#
# NOTE: These are approximate public district boundaries and should be refined
# against actual surveyed MOIL lease boundary shapefiles/cadastral maps in production.
MOIL_MINING_BELT_BBOX = [78.50, 20.90, 80.80, 22.25]

# Web-map scale in meters per pixel.
# 250m is ideal for lightweight browser overlays (fast export, <5MB GeoTIFFs).
# Lower scale (e.g. 20m) yields native Sentinel-2 resolution for heavy analysis.
DEFAULT_EXPORT_SCALE = 250

# Spatial Reference System for web map overlays
DEFAULT_CRS = "EPSG:4326"


# ---------------------------------------------------------------------------
# GEE Initialization Guard
# ---------------------------------------------------------------------------

def verify_and_get_ee(dry_run: bool = False):
    """
    Verifies that Google Earth Engine Python API is installed and initialized.
    Assumes ee.Authenticate() and ee.Initialize() have already been configured.
    
    Returns the initialized `ee` module, or None if in dry-run/mock mode.
    Raises SystemExit with a clear error message if ee is uninitialized.
    """
    if dry_run:
        print("[INFO] Running in DRY-RUN mode — GEE network calls will be simulated.")
        return None

    try:
        # Import the official Earth Engine Python library
        import ee
    except ImportError:
        print("\n" + "=" * 70)
        print("[ERROR] The 'earthengine-api' package is not installed.")
        print("Install it with:")
        print("    pip install earthengine-api")
        print("=" * 70 + "\n")
        sys.exit(1)

    try:
        # ee.Number(1).getInfo() executes a minimal round-trip call to Earth Engine
        # servers to confirm valid authentication credentials and an active project session.
        ee.Number(1).getInfo()
        return ee
    except Exception as exc:
        print("\n" + "=" * 70)
        print("[ERROR] Google Earth Engine is not initialized or credentials expired.")
        print(f"Details: {exc}")
        print("\nPlease authenticate and initialize Earth Engine in your environment:")
        print("    1. Run `earthengine authenticate` in your terminal, OR")
        print("    2. Run `ee.Authenticate()` followed by `ee.Initialize(project='your-gcp-project')` in Python.")
        print("=" * 70 + "\n")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Earth Engine Sentinel-2 Query & Index Calculation Functions
# ---------------------------------------------------------------------------

def get_roi_geometry(ee_module, bbox=None):
    """
    Converts a bounding box [min_lon, min_lat, max_lon, max_lat] into an
    Earth Engine Geometry Rectangle object.
    """
    if bbox is None:
        bbox = MOIL_MINING_BELT_BBOX
    
    # ee.Geometry.Rectangle creates a planar/geodetic rectangular polygon from [minX, minY, maxX, maxY]
    return ee_module.Geometry.Rectangle(bbox)


def fetch_least_cloudy_sentinel2(ee_module, roi, start_date: str, end_date: str, max_cloud_percent: float = 30.0):
    """
    Queries the Sentinel-2 Level-2A (Bottom of Atmosphere / Surface Reflectance)
    harmonized collection for the ROI and date range, filtered to the least cloudy scene.
    
    Bands of interest:
    - B2: Blue (490 nm, 10m)
    - B4: Red (665 nm, 10m)
    - B8: NIR (842 nm, 10m)
    """
    # ee.ImageCollection loads the catalog of Sentinel-2 L2A Surface Reflectance images
    collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .filter(ee_module.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent))
    
    # Check if any scenes match the criteria
    count = collection.size().getInfo()
    if count == 0:
        # If no scenes found with strict cloud threshold, fallback to collection sorted by cloud cover without threshold
        print(f"[WARN] No scenes with < {max_cloud_percent}% clouds found between {start_date} and {end_date}. Widening cloud filter...")
        collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(roi) \
            .filterDate(start_date, end_date)
        
        count = collection.size().getInfo()
        if count == 0:
            raise RuntimeError(f"No Sentinel-2 imagery available for the region between {start_date} and {end_date}.")

    # .sort('CLOUDY_PIXEL_PERCENTAGE', True) orders images ascending (lowest cloud % first)
    # .first() extracts the single best (least-cloudy) image from the collection
    best_image = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()
    
    # Retrieve acquisition metadata for reporting and frontend manifest
    metadata = best_image.toDictionary(["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "PRODUCT_ID"]).getInfo()
    acquisition_timestamp_ms = metadata.get("system:time_start", 0)
    acquisition_date = datetime.fromtimestamp(acquisition_timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    cloud_pct = metadata.get("CLOUDY_PIXEL_PERCENTAGE", None)

    print(f"[GEE] Selected S2 Image: Product ID {metadata.get('PRODUCT_ID', 'N/A')}")
    print(f"      Acquisition Date: {acquisition_date} | Cloud Cover: {cloud_pct:.2f}%" if cloud_pct is not None else f"Acquisition Date: {acquisition_date}")

    return best_image, acquisition_date, metadata


def compute_spectral_indices(ee_module, s2_image):
    """
    Computes spectral indices for vegetation and mineral exploration:
    1. NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)
       - Standard vegetation index (-1.0 to +1.0)
    2. Iron-Oxide Alteration Index = Red / Blue = B4 / B2
       - Standard ratio used in mineral exploration to detect hydrothermal/ferruginous
         alteration and gossans associated with manganese/iron ore host rocks.
    """
    # ee.Image.normalizedDifference(['B8', 'B4']) calculates (Band_1 - Band_2) / (Band_1 + Band_2)
    # .rename('NDVI') assigns a clean band name to the resulting single-band image
    ndvi = s2_image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # .select('B4') and .select('B2') extract the Red and Blue reflectance bands
    # .divide() executes pixel-wise division (Red / Blue)
    # .rename('iron_oxide') assigns a descriptive name for raster export
    iron_oxide = s2_image.select("B4").divide(s2_image.select("B2")).rename("iron_oxide")

    return ndvi, iron_oxide


def download_geotiff(ee_module, ee_image, roi, output_filepath: str, scale: int = DEFAULT_EXPORT_SCALE, crs: str = DEFAULT_CRS):
    """
    Downloads an Earth Engine image directly as a portable GeoTIFF file via GEE's
    getDownloadURL endpoint and saves it to local disk.
    
    This avoids slow asynchronous Google Drive exports and provides immediate,
    portable GeoTIFF assets for FastAPI and MapLibre.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
    
    # ee.Image.getDownloadURL generates a temporary HTTPS signed URL to download
    # the processed raster clipped to the region of interest at the specified pixel scale
    download_params = {
        "scale": scale,           # Resolution in meters (e.g. 250m for web-map overlay)
        "crs": crs,               # Coordinate Reference System (EPSG:4326 for WGS84 lat/lon)
        "region": roi,            # Earth Engine Geometry defining export extent
        "format": "GEO_TIFF"      # Export format
    }
    
    print(f"[GEE] Requesting download URL for {os.path.basename(output_filepath)} (scale: {scale}m)...")
    url = ee_image.getDownloadURL(download_params)
    
    # Download the GeoTIFF binary stream to local disk
    urllib.request.urlretrieve(url, output_filepath)
    file_size_kb = os.path.getsize(output_filepath) / 1024.0
    print(f"[OK] Downloaded: {output_filepath} ({file_size_kb:.1f} KB)")
    return output_filepath


# ---------------------------------------------------------------------------
# Task 5: 4-Week NDVI Time-Series Function (for MapLibre Time-Slider UI)
# ---------------------------------------------------------------------------

def get_ndvi_timeseries(ee_module, roi, end_date=None, num_weeks: int = 4, interval_days: int = 7,
                        scale: int = DEFAULT_EXPORT_SCALE, output_dir: str = "output"):
    """
    Computes and exports NDVI GeoTIFFs across consecutive weekly intervals leading
    up to end_date. Designed to feed a dynamic time-slider UI in MapLibre GL.
    
    Parameters:
    - ee_module: Initialized ee module (or None in dry-run)
    - roi: ee.Geometry region of interest
    - end_date: datetime or YYYY-MM-DD string (defaults to today)
    - num_weeks: Number of intervals to extract (default: 4)
    - interval_days: Duration of each interval in days (default: 7)
    - scale: Resolution in meters per pixel (default: 250)
    - output_dir: Directory to save exported GeoTIFFs
    
    Returns:
    - List of dicts with week metadata, acquisition dates, and local file paths.
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
        # Calculate weekly temporal windows backwards from end_dt
        # Week 1: [T-28d to T-21d], ..., Week 4: [T-7d to T-0d]
        week_num = i + 1
        w_end = end_dt - timedelta(days=(num_weeks - 1 - i) * interval_days)
        w_start = w_end - timedelta(days=interval_days)
        
        start_str = w_start.strftime("%Y-%m-%d")
        end_str = w_end.strftime("%Y-%m-%d")
        
        print(f"\n--- Week {week_num}/{num_weeks}: Window {start_str} to {end_str} ---")
        
        if ee_module is not None:
            try:
                s2_img, acq_date, meta = fetch_least_cloudy_sentinel2(
                    ee_module, roi, start_date=start_str, end_date=end_str, max_cloud_percent=40.0
                )
                ndvi_img = s2_img.normalizedDifference(["B8", "B4"]).rename("NDVI")
                
                filename = f"ndvi_week_{week_num}_{acq_date}.tif"
                filepath = os.path.join(output_dir, filename)
                
                download_geotiff(ee_module, ndvi_img, roi, filepath, scale=scale)
                
                timeseries_manifest.append({
                    "week_index": week_num,
                    "window_start": start_str,
                    "window_end": end_str,
                    "acquisition_date": acq_date,
                    "cloud_cover_pct": meta.get("CLOUDY_PIXEL_PERCENTAGE"),
                    "filename": filename,
                    "filepath": os.path.abspath(filepath),
                    "index_type": "NDVI"
                })
            except Exception as e:
                print(f"[WARN] Could not export Week {week_num} ({start_str} to {end_str}): {e}")
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
                "filename": filename,
                "filepath": os.path.abspath(filepath),
                "index_type": "NDVI",
                "simulated": True
            })

    return timeseries_manifest


# ---------------------------------------------------------------------------
# Dry-run Simulation Helper (for offline / CI verification without live GEE)
# ---------------------------------------------------------------------------

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
                # Write minimal placeholder header bytes
                f.write(b"TIFF_SIMULATED_MOCK_GEOTIFF_FOR_TESTING")


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(output_dir: str = "output", scale: int = DEFAULT_EXPORT_SCALE, dry_run: bool = False):
    """
    Executes the complete GEE data preparation pipeline:
    1. Validates GEE environment
    2. Defines mining belt ROI bounding box
    3. Fetches latest 30-day cloud-free Sentinel-2 image
    4. Computes and exports latest NDVI and Iron-Oxide Alteration GeoTIFFs
    5. Computes and exports 4-week weekly NDVI time-series
    6. Writes an integration manifest JSON for FastAPI and MapLibre GL
    """
    print("=" * 70)
    print(" MOIL Reserve Intelligence — Sentinel-2 Data Preparation Pipeline")
    print("=" * 70)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Guard check & GEE module access
    ee_mod = verify_and_get_ee(dry_run=dry_run)
    
    # 2. Define Bounding Box & ROI
    bbox = MOIL_MINING_BELT_BBOX
    print(f"\n[1/5] Target District Bounding Box: {bbox}")
    print("      Coverage: Balaghat (MP), Nagpur & Bhandara (MH) Manganese Belt")
    print("      Note: Refine against actual MOIL cadastral mining leases in production.")
    
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
        # ee.Geometry.Rectangle defines the spatial query envelope for Earth Engine
        roi = get_roi_geometry(ee_mod, bbox)
        
        # 3. Pull most recent cloud-free Sentinel-2 image in last 30 days
        print(f"\n[2/5] Searching for least-cloudy Sentinel-2 SR scene ({start_date_str} to {end_date_str})...")
        s2_img, acq_date, metadata = fetch_least_cloudy_sentinel2(
            ee_mod, roi, start_date=start_date_str, end_date=end_date_str, max_cloud_percent=20.0
        )
        
        # 4. Compute NDVI and Iron-Oxide Alteration Index
        print("\n[3/5] Computing Spectral Indices:")
        print("      - NDVI = (NIR - Red) / (NIR + Red) -> (B8 - B4) / (B8 + B4)")
        print("      - Iron-Oxide Alteration = Red / Blue -> B4 / B2")
        ndvi_image, iron_oxide_image = compute_spectral_indices(ee_mod, s2_img)
        
        # 5. Export latest GeoTIFFs (web-map scale)
        print(f"\n[4/5] Exporting single-date GeoTIFFs (Scale: {scale}m)...")
        ndvi_path = os.path.join(output_dir, f"ndvi_{acq_date}.tif")
        download_geotiff(ee_mod, ndvi_image, roi, ndvi_path, scale=scale)
        
        iron_oxide_path = os.path.join(output_dir, f"iron_oxide_{acq_date}.tif")
        download_geotiff(ee_mod, iron_oxide_image, roi, iron_oxide_path, scale=scale)
        
        manifest["single_layers"] = {
            "ndvi": {
                "name": "Normalized Difference Vegetation Index (NDVI)",
                "formula": "(B8 - B4) / (B8 + B4)",
                "acquisition_date": acq_date,
                "filepath": os.path.abspath(ndvi_path),
                "filename": os.path.basename(ndvi_path),
                "value_range": [-1.0, 1.0],
                "recommended_palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"]
            },
            "iron_oxide": {
                "name": "Iron-Oxide Alteration Index",
                "formula": "B4 / B2 (Red / Blue)",
                "acquisition_date": acq_date,
                "filepath": os.path.abspath(iron_oxide_path),
                "filename": os.path.basename(iron_oxide_path),
                "value_range": [0.5, 3.5],
                "recommended_palette": ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
            }
        }
        
        # 6. Export 4-week weekly NDVI time-series
        print("\n[5/5] Generating 4-week weekly NDVI time-series for MapLibre Time-Slider...")
        ts_data = get_ndvi_timeseries(ee_mod, roi, end_date=today, num_weeks=4, interval_days=7, scale=scale, output_dir=output_dir)
        manifest["timeseries"] = ts_data

    else:
        # Simulated execution for offline testing
        simulate_dry_run_exports(output_dir)
        sim_date = today.strftime("%Y-%m-%d")
        ndvi_path = os.path.join(output_dir, "ndvi_latest.tif")
        iron_oxide_path = os.path.join(output_dir, "iron_oxide_latest.tif")
        
        manifest["single_layers"] = {
            "ndvi": {
                "name": "Normalized Difference Vegetation Index (NDVI)",
                "formula": "(B8 - B4) / (B8 + B4)",
                "acquisition_date": sim_date,
                "filepath": os.path.abspath(ndvi_path),
                "filename": os.path.basename(ndvi_path),
                "simulated": True
            },
            "iron_oxide": {
                "name": "Iron-Oxide Alteration Index",
                "formula": "B4 / B2 (Red / Blue)",
                "acquisition_date": sim_date,
                "filepath": os.path.abspath(iron_oxide_path),
                "filename": os.path.basename(iron_oxide_path),
                "simulated": True
            }
        }
        ts_data = get_ndvi_timeseries(None, None, end_date=today, num_weeks=4, interval_days=7, scale=scale, output_dir=output_dir)
        manifest["timeseries"] = ts_data

    # Write manifest JSON for FastAPI and MapLibre integration
    manifest_path = os.path.join(output_dir, "gee_export_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[OK] Manifest saved: {manifest_path}")

    # Print summary table
    print("\n" + "=" * 70)
    print(" EXPORT PIPELINE SUMMARY")
    print("=" * 70)
    print(f"Output Directory : {os.path.abspath(output_dir)}")
    print(f"Bounding Box     : {bbox}")
    print(f"CRS              : {DEFAULT_CRS}")
    print(f"Scale            : {scale} meters/pixel")
    print("\nGenerated Artifacts:")
    if "ndvi" in manifest["single_layers"]:
        print(f"  [1] Single NDVI GeoTIFF        -> {manifest['single_layers']['ndvi']['filename']}")
    if "iron_oxide" in manifest["single_layers"]:
        print(f"  [2] Alteration Index GeoTIFF   -> {manifest['single_layers']['iron_oxide']['filename']}")
    print(f"  [3] Weekly Time-Series GeoTIFFs -> {len(manifest['timeseries'])} weekly rasters:")
    for ts in manifest["timeseries"]:
        print(f"      - Week {ts['week_index']} ({ts['window_start']} to {ts['window_end']}): {ts['filename']}")
    print(f"  [4] Manifest JSON Metadata      -> gee_export_manifest.json")
    print("=" * 70)

    return manifest


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MOIL Reserve Intelligence - Sentinel-2 GEE Data Prep Pipeline"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"),
        help="Target folder for exported GeoTIFFs and manifest JSON (default: ./output)"
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
