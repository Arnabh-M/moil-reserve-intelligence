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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from geo_utils import COMBINED_BBOX
from gis.ndvi_pull import (
    NDVI_PALETTE, NDVI_MIN, NDVI_MAX, build_window_mosaic, window_record, indices_from_mosaic,
    remove_stale, export_thumb_png, create_sample_tile,
)
from gee_pipeline.ee_auth import get_ee

DEFAULT_BBOX = list(COMBINED_BBOX)  # [west, south, east, north]


def generate_ndvi_timeseries_tiles(tiles_dir="gis/tiles", bbox=None, num_weeks=4, interval_days=7, dry_run=False):
    """
    Generates weekly NDVI PNG tiles (cloud-masked median mosaic of every scene
    in the week, over the whole bbox) and returns structured metadata.

    A week with no scenes gets one lookback widening (window start moves back
    `interval_days`); the window actually used is recorded. A week that still
    has no scenes, or whose mosaic is < MIN_VALID_FRACTION unmasked, does not
    raise and is not filled from anywhere: it is recorded with status
    "no_data" and NO PNG is written (a stale PNG from an earlier run is
    deleted).
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

            used_start = start_str
            mosaic = build_window_mosaic(ee_mod, roi, used_start, end_str)
            if mosaic["image_count"] == 0:
                used_start = (w_start - timedelta(days=interval_days)).strftime("%Y-%m-%d")
                print(f"[WARN] No scenes for Week {week_num} ({start_str} to {end_str}); widening to {used_start}...")
                mosaic = build_window_mosaic(ee_mod, roi, used_start, end_str)

            record = window_record(mosaic, used_start, end_str, requested_start=start_str)
            print(f"[GEE] Week {week_num} {used_start}..{end_str}: images={record['image_count']} "
                  f"valid_fraction={record['valid_fraction']} status={record['status']}")

            if record["status"] == "ok":
                ndvi, _ = indices_from_mosaic(mosaic["image"])
                export_thumb_png(ndvi, roi, tile_filepath, NDVI_MIN, NDVI_MAX, NDVI_PALETTE)
                file_field = tile_filename
            else:
                remove_stale(tile_filepath)
                file_field = None
                print(f"[WARN] Week {week_num} recorded as no_data (no PNG written).")

            timeseries_list.append({
                **record,
                "week_index": week_num,
                "file": file_field,
                "requested_window_start": start_str,
                "bbox": bbox,
                "layer_type": "NDVI",
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
                "status": "simulated",
                "image_count": 0,
                "valid_fraction": None,
                "simulated": True
            })

    return timeseries_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 4-week NDVI PNG tiles for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory for PNG tiles")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    generate_ndvi_timeseries_tiles(tiles_dir=args.tiles_dir, dry_run=args.dry_run)
