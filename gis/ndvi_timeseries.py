"""
MOIL Reserve Intelligence — GIS Data Prep: 4-Week NDVI Time-Series Tiles
=========================================================================
Generates 4 weekly NDVI PNG tiles for MapLibre GL time-slider UI.

ARCHITECTURAL DECISION & TRADE-OFF EXPLANATION:
----------------------------------------------
We use `ee.Image.getThumbURL()` with standard NDVI color ramp palette:
  - Advantage: Renders fully styled RGBA PNG tiles on the GEE server. No local
    GeoTIFF to RGBA colormap conversion needed in Python.
  - Integration: MapLibre GL consumes these tiles via raster ImageSource by simply
    supplying the tile URL/path and the 4 corner coordinates.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import urllib.request

# Global Bounding Box [west, south, east, north] (WGS84 EPSG:4326)
MOIL_BBOX = [78.50, 20.90, 80.80, 22.25]

# Standard NDVI visual palette: Red -> Orange -> Yellow -> Light Green -> Dark Green
NDVI_PALETTE = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"]
NDVI_MIN = -0.1
NDVI_MAX = 0.7


def check_ee_available():
    """
    Checks if Google Earth Engine is installed and initialized.
    """
    try:
        import ee
        ee.Number(1).getInfo()
        return ee
    except Exception as exc:
        print(f"[INFO] GEE not initialized ({exc}). Operating in simulation/offline mode.")
        return None


def generate_ndvi_timeseries_tiles(tiles_dir="gis/tiles", bbox=None, num_weeks=4, interval_days=7, dry_run=False):
    """
    Generates 4 weekly NDVI PNG tiles and returns structured metadata for MapLibre.
    """
    if bbox is None:
        bbox = MOIL_BBOX

    os.makedirs(tiles_dir, exist_ok=True)
    ee_mod = None if dry_run else check_ee_available()

    now = datetime.now(timezone.utc)
    timeseries_list = []

    print(f"\n[GIS] Generating {num_weeks}-Week NDVI Time-Series Tiles...")

    for i in range(num_weeks):
        week_num = i + 1
        w_end = now - timedelta(days=(num_weeks - 1 - i) * interval_days)
        w_start = w_end - timedelta(days=interval_days)

        start_str = w_start.strftime("%Y-%m-%d")
        end_str = w_end.strftime("%Y-%m-%d")
        tile_filename = f"ndvi_week_{week_num}.png"
        tile_filepath = os.path.join(tiles_dir, tile_filename)

        if ee_mod is not None:
            try:
                roi = ee_mod.Geometry.Rectangle(bbox)
                
                # Filter Sentinel-2 L2A collection for the weekly interval
                collection = ee_mod.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(roi) \
                    .filterDate(start_str, end_str)

                count = collection.size().getInfo()
                if count > 0:
                    best_img = collection.sort("CLOUDY_PIXEL_PERCENTAGE", True).first()
                else:
                    # Fallback to nearest scene if a specific week was overcast
                    print(f"[WARN] No scenes for Week {week_num} ({start_str} to {end_str}), picking closest available.")
                    best_img = ee_mod.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                        .filterBounds(roi) \
                        .filterDate((w_start - timedelta(days=5)).strftime("%Y-%m-%d"), end_str) \
                        .sort("CLOUDY_PIXEL_PERCENTAGE", True).first()

                meta = best_img.toDictionary(["system:time_start"]).getInfo()
                time_ms = meta.get("system:time_start", 0)
                acq_date = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d") if time_ms else end_str

                # Calculate NDVI
                ndvi = best_img.normalizedDifference(["B8", "B4"]).rename("NDVI")

                # Export PNG via getThumbURL
                clean_palette = [c.replace("#", "") for c in NDVI_PALETTE]
                vis_params = {
                    "min": NDVI_MIN,
                    "max": NDVI_MAX,
                    "palette": clean_palette,
                    "dimensions": "1024x1024",
                    "region": roi,
                    "crs": "EPSG:4326",
                    "format": "png"
                }
                url = ndvi.getThumbURL(vis_params)
                urllib.request.urlretrieve(url, tile_filepath)
                print(f"[OK] Week {week_num} ({acq_date}) PNG downloaded -> {tile_filepath}")

            except Exception as exc:
                print(f"[ERROR] Week {week_num} export failed: {exc}. Generating mock tile.")
                acq_date = end_str
                from gis.ndvi_pull import create_sample_tile
                create_sample_tile(tile_filepath, NDVI_PALETTE, title=f"NDVI Week {week_num} ({acq_date})")
        else:
            acq_date = end_str
            from gis.ndvi_pull import create_sample_tile
            create_sample_tile(tile_filepath, NDVI_PALETTE, title=f"NDVI Week {week_num} ({acq_date})")

        timeseries_list.append({
            "week_index": week_num,
            "file": tile_filename,
            "date": acq_date,
            "window_start": start_str,
            "window_end": end_str,
            "bbox": bbox,
            "layer_type": "NDVI"
        })

    return timeseries_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 4-week NDVI PNG tiles for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory for PNG tiles")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    generate_ndvi_timeseries_tiles(tiles_dir=args.tiles_dir, dry_run=args.dry_run)
