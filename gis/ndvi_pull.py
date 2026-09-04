"""
MOIL Reserve Intelligence — GIS Data Prep: Single-Date NDVI & Iron-Oxide Tiles
================================================================================
Extracts the most recent Sentinel-2 Level-2A Surface Reflectance scene over the
MOIL manganese mining belt (Balaghat, Nagpur, Bhandara), computes:
  1. NDVI (Vegetation Index)
  2. Iron-Oxide Alteration Index (Red / Blue spectral ratio)
and exports them directly as web-ready RGBA PNG tiles for MapLibre GL.

ARCHITECTURAL DECISION & TRADE-OFF EXPLANATION:
----------------------------------------------
We use `ee.Image.getThumbURL()` rather than exporting GeoTIFF to Google Drive:
  - WHY `getThumbURL` IS PREFERRED:
    1. Synchronous & Fast: Generates pre-colored PNGs directly in GEE in ~2 seconds.
    2. Zero GDAL/rasterio C-extension dependencies: Avoids local DLL/GDAL driver issues
       on Windows/Linux client machines.
    3. Direct MapLibre ImageSource compatibility: MapLibre GL JS `ImageSource` requires
       standard PNG/JPG raster tiles with a 4-point georeferenced bounding box.
  - TRADE-OFF:
    ThumbURL raster resolution is capped at web-overlay dimensions (e.g. 1024x1024 / 2048x2048),
    which is optimal for browser rendering but not intended for raw multi-gigabyte spatial analysis.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import urllib.request

from gis.raster_utils import feather_edges

# ---------------------------------------------------------------------------
# Default Configuration & MOIL Mining Belt Bounding Box
# ---------------------------------------------------------------------------

# Geographic bounding box covering Balaghat (MP), Nagpur & Bhandara (MH)
# Format: [west (min_lon), south (min_lat), east (max_lon), north (max_lat)] in WGS84 (EPSG:4326)
MOIL_BBOX = [78.50, 20.90, 80.80, 22.25]

# Standard visualization palettes for frontend rendering:
# NDVI: Green (dense veg) -> Yellow (moderate/sparse) -> Red/Brown (bare soil/mines)
NDVI_PALETTE = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"]
NDVI_MIN = -0.1
NDVI_MAX = 0.7

# Iron-Oxide Alteration Index: Blue (low alteration) -> Yellow -> Red/Deep Red (high iron/manganese gossan)
IRON_OXIDE_PALETTE = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
IRON_OXIDE_MIN = 0.5
IRON_OXIDE_MAX = 3.0


def check_ee_available():
    """
    Checks if Google Earth Engine is installed and initialized.
    Returns ee module or None if uninitialized/offline.
    """
    try:
        import ee
        ee.Number(1).getInfo()
        return ee
    except Exception as exc:
        print(f"[INFO] GEE not initialized ({exc}). Operating in simulation/offline mode.")
        return None


def fetch_latest_sentinel2_indices(ee_module, bbox=None, days_back=30):
    """
    Queries Sentinel-2 L2A Harmonized SR imagery for the last `days_back` days,
    picks the least cloudy scene, and calculates NDVI and Iron-Oxide Alteration ratio.
    """
    if bbox is None:
        bbox = MOIL_BBOX

    # Convert bbox [west, south, east, north] to GEE Geometry Rectangle
    roi = ee_module.Geometry.Rectangle(bbox)

    today = datetime.now(timezone.utc)
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    # Load Sentinel-2 SR collection filtered by ROI and date window
    collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .filter(ee_module.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))

    count = collection.size().getInfo()
    if count == 0:
        # Fallback to no cloud percentage threshold if weather was overcast
        collection = ee_module.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(roi) \
            .filterDate(start_date, end_date)

    # Pick the scene with the lowest cloud percentage
    best_img = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()

    # Extract acquisition date
    meta = best_img.toDictionary(["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"]).getInfo()
    time_ms = meta.get("system:time_start", 0)
    acq_date = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    # Compute NDVI: (NIR - Red) / (NIR + Red) -> (B8 - B4) / (B8 + B4)
    ndvi = best_img.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # Compute Iron-Oxide ratio: Red / Blue -> B4 / B2
    iron_oxide = best_img.select("B4").divide(best_img.select("B2")).rename("iron_oxide")

    return ndvi, iron_oxide, acq_date, roi


def export_thumb_png(ee_image, roi, output_path, min_val, max_val, palette, dimensions="1024x1024"):
    """
    Generates a color-mapped RGBA PNG tile via GEE's getThumbURL and downloads it.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Convert palette hex colors (removing leading # if present)
    clean_palette = [c.replace("#", "") for c in palette]

    vis_params = {
        "min": min_val,
        "max": max_val,
        "palette": clean_palette,
        "dimensions": dimensions,
        "region": roi,
        "crs": "EPSG:4326",
        "format": "png"
    }

    url = ee_image.getThumbURL(vis_params)
    urllib.request.urlretrieve(url, output_path)

    # Feather the outer edge so the overlay blends into the basemap instead
    # of showing a hard-edged rectangle when rendered in MapLibre.
    from PIL import Image
    downloaded = Image.open(output_path)
    feathered = feather_edges(downloaded, feather_px=max(24, int(min(downloaded.size) * 0.05)))
    feathered.save(output_path, format="PNG")

    print(f"[OK] Downloaded PNG tile -> {output_path}")
    return output_path


def create_sample_tile(output_path, palette, title="Sample Tile", size=512, seed=None):
    """
    Creates a color-mapped mock PNG tile for offline/dry-run verification, standing
    in for the real GEE getThumbURL output. Contains ONLY color-mapped pixel data —
    no text, title, or border is ever drawn onto the image; any contextual label
    (date, week number, bounds) is rendered separately as a UI overlay in the
    frontend, not baked into the raster. Edges are feathered to match the real
    tile pipeline's blending behavior.
    """
    import numpy as np
    from PIL import Image, ImageFilter
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    rng = np.random.default_rng(seed if seed is not None else abs(hash(title)) % (2**32))
    yy, xx = (np.mgrid[0:size, 0:size].astype(np.float32) / size)

    # Smooth pseudo-spatial field (overlapping sine components + light noise),
    # normalized to 0..1, standing in for a real georeferenced data surface.
    phase_a, phase_b, phase_c = rng.uniform(0, 2 * np.pi, size=3)
    field = (
        np.sin(xx * 6.0 + phase_a) * np.cos(yy * 5.0 + phase_b)
        + 0.6 * np.sin((xx + yy) * 4.0 + phase_c)
        + rng.normal(0, 0.05, size=(size, size))
    )
    field = (field - field.min()) / (field.max() - field.min() + 1e-9)

    palette_rgb = np.array(
        [[int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)] for c in palette],
        dtype=np.float32,
    )
    stops = np.linspace(0.0, 1.0, len(palette_rgb))

    rgb = np.empty((size, size, 3), dtype=np.float32)
    for channel in range(3):
        rgb[:, :, channel] = np.interp(field, stops, palette_rgb[:, channel])

    alpha = np.full((size, size, 1), 235.0, dtype=np.float32)
    rgba = np.concatenate([rgb, alpha], axis=2).astype(np.uint8)

    img = Image.fromarray(rgba, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=size / 160))
    img = feather_edges(img, feather_px=max(24, size // 12))
    img.save(output_path, format="PNG")
    print(f"[MOCK] Created simulation PNG tile -> {output_path}")


def pull_single_layers(tiles_dir="gis/tiles", bbox=None, dry_run=False):
    """
    Generates single-date NDVI and Iron-Oxide PNG tiles for MapLibre raster ImageSource.
    Returns metadata dict with file paths, acquisition dates, and WGS84 bounding boxes.
    """
    if bbox is None:
        bbox = MOIL_BBOX

    os.makedirs(tiles_dir, exist_ok=True)
    ee_mod = None if dry_run else check_ee_available()

    ndvi_png = os.path.join(tiles_dir, "ndvi_latest.png")
    iron_oxide_png = os.path.join(tiles_dir, "iron_oxide_latest.png")

    if ee_mod is not None:
        print("[GEE] Fetching latest Sentinel-2 scene and computing indices...")
        ndvi_img, iron_img, acq_date, roi = fetch_latest_sentinel2_indices(ee_mod, bbox=bbox)
        
        export_thumb_png(ndvi_img, roi, ndvi_png, NDVI_MIN, NDVI_MAX, NDVI_PALETTE)
        export_thumb_png(iron_img, roi, iron_oxide_png, IRON_OXIDE_MIN, IRON_OXIDE_MAX, IRON_OXIDE_PALETTE)
    else:
        acq_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        create_sample_tile(ndvi_png, NDVI_PALETTE, title="NDVI Latest")
        create_sample_tile(iron_oxide_png, IRON_OXIDE_PALETTE, title="Iron-Oxide Alteration Latest")

    results = {
        "ndvi_latest": {
            "name": "Normalized Difference Vegetation Index (NDVI)",
            "file": "ndvi_latest.png",
            "date": acq_date,
            "bbox": bbox,
            "value_range": [NDVI_MIN, NDVI_MAX]
        },
        "iron_oxide_latest": {
            "name": "Iron-Oxide Alteration Index (Red/Blue)",
            "file": "iron_oxide_latest.png",
            "date": acq_date,
            "bbox": bbox,
            "value_range": [IRON_OXIDE_MIN, IRON_OXIDE_MAX]
        }
    }
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate latest NDVI and Iron Oxide PNG tiles for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory for PNG tiles")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    pull_single_layers(tiles_dir=args.tiles_dir, dry_run=args.dry_run)
