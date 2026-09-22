"""
MOIL Reserve Intelligence — GIS Data Prep: 4-Week NDVI Time-Series Tiles
=========================================================================
Generates 4 weekly NDVI PNG tiles for MapLibre GL time-slider UI
covering geo_utils.COMBINED_BBOX.

ARCHITECTURAL DECISION & TRADE-OFF EXPLANATION:
----------------------------------------------
We use `ee.Image.getThumbURL()` with standard NDVI color ramp palette:
  - Advantage: Renders fully styled RGBA PNG tiles on the GEE server. No local
    GeoTIFF to RGBA colormap conversion needed in Python.
  - Integration: MapLibre GL consumes these tiles via raster ImageSource by simply
    supplying the tile URL/path and the 4 corner coordinates.
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
from gis.ndvi_pull import NDVI_PALETTE, NDVI_MIN, NDVI_MAX, mask_s2_clouds, export_thumb_png, create_sample_tile
from gee_pipeline.ee_auth import get_ee

DEFAULT_BBOX = list(COMBINED_BBOX)  # [79.0, 21.0, 80.4, 22.0]


def generate_ndvi_timeseries_tiles(tiles_dir="gis/tiles", bbox=None, num_weeks=4, interval_days=7, dry_run=False):
    """
    Generates 4 weekly NDVI PNG tiles and returns structured metadata for MapLibre.
    Fails loudly if any weekly interval has image_count == 0 in real mode.
    """
    if bbox is None:
        bbox = DEFAULT_BBOX

    os.makedirs(tiles_dir, exist_ok=True)
    ee_mod = get_ee(dry_run=dry_run)

    now = datetime.now(timezone.utc)
    timeseries_list = []

    print(f"\n[GIS] Generating {num_weeks}-Week NDVI Time-Series Tiles (BBox: {bbox})...")

    for i in range(num_weeks):
        week_num = i + 1
        w_end = now - timedelta(days=(num_weeks - 1 - i) * interval_days)
        w_start = w_end - timedelta(days=interval_days)

        start_str = w_start.strftime("%Y-%m-%d")
        end_str = w_end.strftime("%Y-%m-%d")
        tile_filename = f"ndvi_week_{week_num}.png"
        tile_filepath = os.path.join(tiles_dir, tile_filename)

        if ee_mod is not None:
            roi = ee_mod.Geometry.Rectangle(bbox)

            collection = ee_mod.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(roi) \
                .filterDate(start_str, end_str)

            count = collection.size().getInfo()
            if count == 0:
                lookback_start = (w_start - timedelta(days=7)).strftime("%Y-%m-%d")
                print(f"[WARN] No scenes for Week {week_num} ({start_str} to {end_str}), looking back to {lookback_start}...")
                collection = ee_mod.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(roi) \
                    .filterDate(lookback_start, end_str)
                count = collection.size().getInfo()
                if count == 0:
                    raise RuntimeError(f"No Sentinel-2 imagery available for Week {week_num} (window {start_str} to {end_str}, lookback from {lookback_start}; image_count == 0).")

            best_img = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()
            masked_img = mask_s2_clouds(best_img, ee_mod)

            meta = best_img.toDictionary(["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"]).getInfo()
            time_ms = meta.get("system:time_start", 0)
            acq_date = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d") if time_ms else end_str

            ndvi = masked_img.normalizedDifference(["B8", "B4"]).rename("NDVI")

            export_thumb_png(ndvi, roi, tile_filepath, NDVI_MIN, NDVI_MAX, NDVI_PALETTE)
            print(f"[OK] Week {week_num} ({acq_date}) PNG downloaded -> {tile_filepath}")

            timeseries_list.append({
                "week_index": week_num,
                "file": tile_filename,
                "date": acq_date,
                "window_start": start_str,
                "window_end": end_str,
                "date_range": [start_str, end_str],
                "bbox": bbox,
                "layer_type": "NDVI",
                "source": "COPERNICUS/S2_SR_HARMONIZED",
                "image_count": count,
                "cloud_cover_pct": meta.get("CLOUDY_PIXEL_PERCENTAGE"),
                "simulated": False
            })

        else:
            acq_date = end_str
            create_sample_tile(tile_filepath, NDVI_PALETTE, title=f"NDVI Week {week_num} ({acq_date})")

            timeseries_list.append({
                "week_index": week_num,
                "file": tile_filename,
                "date": acq_date,
                "window_start": start_str,
                "window_end": end_str,
                "date_range": [start_str, end_str],
                "bbox": bbox,
                "layer_type": "NDVI",
                "source": "SIMULATED_MOCK",
                "image_count": 0,
                "cloud_cover_pct": 5.0 + i * 2.5,
                "simulated": True
            })

    return timeseries_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 4-week NDVI PNG tiles for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory for PNG tiles")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    generate_ndvi_timeseries_tiles(tiles_dir=args.tiles_dir, dry_run=args.dry_run)
