"""
MOIL Reserve Intelligence — GIS Data Prep: Single-Date NDVI & Iron-Oxide Tiles
================================================================================
Extracts the most recent Sentinel-2 Level-2A Surface Reflectance scene over the
MOIL manganese mining belt (geo_utils.COMBINED_BBOX), computes:
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

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from geo_utils import COMBINED_BBOX
from gis.raster_utils import feather_edges
from gee_pipeline.ee_auth import get_ee

# ---------------------------------------------------------------------------
# Default Configuration & MOIL Mining Belt Bounding Box
# ---------------------------------------------------------------------------

# Geographic bounding box covering Balaghat (MP), Nagpur & Bhandara (MH)
# Format: [west (min_lon), south (min_lat), east (max_lon), north (max_lat)] in WGS84 (EPSG:4326)
DEFAULT_BBOX = list(COMBINED_BBOX)  # [west, south, east, north]

# Standard visualization palettes for frontend rendering:
# NDVI: Green (dense veg) -> Yellow (moderate/sparse) -> Red/Brown (bare soil/mines)
NDVI_PALETTE = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"]
NDVI_MIN = -0.1
NDVI_MAX = 0.7

# Iron-Oxide Alteration Index: Blue (low alteration) -> Yellow -> Red/Deep Red (high iron/manganese gossan)
IRON_OXIDE_PALETTE = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
IRON_OXIDE_MIN = 0.5
IRON_OXIDE_MAX = 3.0


def mask_s2_clouds(image, ee_module):
    """
    Masks cloud shadow, medium/high cloud probability, and thin cirrus
    using the Sentinel-2 L2A Scene Classification Layer (SCL: 3, 8, 9, 10).
    """
    scl = image.select("SCL")
    mask = ee_module.Image.constant(1)
    for val in [3, 8, 9, 10]:
        mask = mask.And(scl.neq(val))
    # .copyProperties() always returns a generic ee.Element (GEE API quirk) —
    # cast back to ee.Image so Image-only methods stay available downstream.
    return ee_module.Image(
        image.updateMask(mask).copyProperties(image, ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "PRODUCT_ID"])
    )


S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

# A window whose mosaic has less than this share of unmasked pixels over the
# bbox is recorded as "no_data" instead of being rendered.
MIN_VALID_FRACTION = 0.10
VALID_FRACTION_SCALE_M = 300


def s2_status(image_count, valid_fraction):
    """'ok' if the mosaic is worth rendering, else 'no_data'."""
    if not image_count or valid_fraction is None or valid_fraction < MIN_VALID_FRACTION:
        return "no_data"
    return "ok"


def _ms_to_date(ms):
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d") if ms else None


def build_window_mosaic(ee_module, roi, start_date, end_date):
    """
    Cloud-masked (SCL) median mosaic of EVERY Sentinel-2 scene over `roi` in
    [start_date, end_date). One scene is narrower than the MOIL bbox, so a
    single least-cloudy scene leaves most of the overlay empty.

    Returns dict: image (ee.Image or None), image_count, valid_fraction (share
    of roi with unmasked pixels), acquisition_first / acquisition_last (dates).
    """
    collection = ee_module.ImageCollection(S2_COLLECTION).filterBounds(roi).filterDate(start_date, end_date)
    count = collection.size().getInfo()
    if count == 0:
        return {"image": None, "image_count": 0, "valid_fraction": 0.0,
                "acquisition_first": None, "acquisition_last": None}

    times = ee_module.Dictionary({
        "first": collection.aggregate_min("system:time_start"),
        "last": collection.aggregate_max("system:time_start"),
    }).getInfo()

    masked = collection.map(
        lambda im: ee_module.Image(mask_s2_clouds(im, ee_module)).select(["B2", "B4", "B8"])
    )
    mosaic = masked.median()

    valid = mosaic.select("B4").mask().unmask(0)
    vf = valid.reduceRegion(
        reducer=ee_module.Reducer.mean(), geometry=roi, scale=VALID_FRACTION_SCALE_M,
        maxPixels=int(1e9), bestEffort=True,
    ).get("B4").getInfo()

    return {
        "image": mosaic,
        "image_count": int(count),
        "valid_fraction": round(float(vf or 0.0), 4),
        "acquisition_first": _ms_to_date(times.get("first")),
        "acquisition_last": _ms_to_date(times.get("last")),
    }


def window_record(mosaic, window_start, window_end, requested_start=None):
    """Manifest fields describing the window ACTUALLY used for a layer."""
    status = s2_status(mosaic["image_count"], mosaic["valid_fraction"])
    return {
        "status": status,
        "window_start": window_start,
        "window_end": window_end,
        "date_range": [window_start, window_end],
        "lookback_applied": bool(requested_start and requested_start != window_start),
        "image_count": mosaic["image_count"],
        "valid_fraction": mosaic["valid_fraction"],
        "acquisition_first": mosaic["acquisition_first"],
        "acquisition_last": mosaic["acquisition_last"],
        "date": mosaic["acquisition_last"] if status == "ok" else None,  # no_data has no usable acquisition
        "source": S2_COLLECTION,
        "method": "cloud-masked (SCL) median mosaic of all scenes in window",
        "simulated": False,
    }


def indices_from_mosaic(mosaic_image):
    ndvi = mosaic_image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    iron_oxide = mosaic_image.select("B4").divide(mosaic_image.select("B2")).rename("iron_oxide")
    return ndvi, iron_oxide


def export_thumb_png(ee_image, roi, output_path, min_val, max_val, palette, dimensions="1024x1024"):
    """
    Generates a color-mapped RGBA PNG tile via GEE's getThumbURL and downloads it.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

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

    # Feather the outer edge so the overlay blends into the basemap
    from PIL import Image
    downloaded = Image.open(output_path)
    feathered = feather_edges(downloaded, feather_px=max(24, int(min(downloaded.size) * 0.05)))
    feathered.save(output_path, format="PNG")

    print(f"[OK] Downloaded PNG tile -> {output_path}")
    return output_path


def create_sample_tile(output_path, palette, title="Sample Tile", size=512, seed=None):
    """
    Creates a color-mapped mock PNG tile for offline/dry-run verification, standing
    in for the real GEE getThumbURL output. Contains ONLY color-mapped pixel data.
    """
    import numpy as np
    from PIL import Image, ImageFilter
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    rng = np.random.default_rng(seed if seed is not None else abs(hash(title)) % (2**32))
    yy, xx = (np.mgrid[0:size, 0:size].astype(np.float32) / size)

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


def remove_stale(path):
    """Delete a PNG left by a previous run so a no_data layer never serves an old image."""
    if os.path.exists(path):
        os.remove(path)


def pull_single_layers(tiles_dir="gis/tiles", bbox=None, dry_run=False, days_back=30):
    """
    Generates NDVI and Iron-Oxide PNG tiles from ONE cloud-masked median mosaic
    over the last `days_back` days, for MapLibre raster ImageSource.
    A layer whose mosaic has too little clear data gets status "no_data" and no
    PNG (any stale PNG from a previous run is deleted).
    Returns metadata dict per layer.
    """
    if bbox is None:
        bbox = DEFAULT_BBOX

    os.makedirs(tiles_dir, exist_ok=True)
    ee_mod = get_ee(dry_run=dry_run)

    ndvi_png = os.path.join(tiles_dir, "ndvi_latest.png")
    iron_oxide_png = os.path.join(tiles_dir, "iron_oxide_latest.png")

    layer_defs = {
        "ndvi_latest": {
            "name": "Normalized Difference Vegetation Index (NDVI)", "file": "ndvi_latest.png",
            "value_range": [NDVI_MIN, NDVI_MAX],
        },
        "iron_oxide_latest": {
            "name": "Iron-Oxide Alteration Index (Red/Blue)", "file": "iron_oxide_latest.png",
            "value_range": [IRON_OXIDE_MIN, IRON_OXIDE_MAX],
        },
    }

    today = datetime.now(timezone.utc)
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    if ee_mod is not None:
        print(f"[GEE] Building cloud-masked median mosaic {start_date}..{end_date} over {bbox}...")
        roi = ee_mod.Geometry.Rectangle(bbox)
        mosaic = build_window_mosaic(ee_mod, roi, start_date, end_date)
        record = window_record(mosaic, start_date, end_date)
        print(f"[GEE] images={record['image_count']} valid_fraction={record['valid_fraction']} status={record['status']}")

        results = {key: {**meta, **record, "bbox": bbox} for key, meta in layer_defs.items()}
        if record["status"] == "ok":
            ndvi_img, iron_img = indices_from_mosaic(mosaic["image"])
            export_thumb_png(ndvi_img, roi, ndvi_png, NDVI_MIN, NDVI_MAX, NDVI_PALETTE)
            export_thumb_png(iron_img, roi, iron_oxide_png, IRON_OXIDE_MIN, IRON_OXIDE_MAX, IRON_OXIDE_PALETTE)
        else:
            for key in results:
                remove_stale(os.path.join(tiles_dir, layer_defs[key]["file"]))
                results[key]["file"] = None
    else:
        create_sample_tile(ndvi_png, NDVI_PALETTE, title="NDVI Latest")
        create_sample_tile(iron_oxide_png, IRON_OXIDE_PALETTE, title="Iron-Oxide Alteration Latest")
        results = {
            key: {
                **meta, "date": end_date, "date_range": [start_date, end_date], "window_start": start_date,
                "window_end": end_date, "bbox": bbox, "source": "SIMULATED_MOCK", "status": "simulated",
                "image_count": 0, "valid_fraction": None, "simulated": True,
            }
            for key, meta in layer_defs.items()
        }

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate latest NDVI and Iron Oxide PNG tiles for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory for PNG tiles")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    pull_single_layers(tiles_dir=args.tiles_dir, dry_run=args.dry_run)
