"""
MOIL Reserve Intelligence — GIS Master Tile Pipeline & Manifest Generator
==========================================================================
Orchestrates:
  1. 4 Weekly NDVI PNG tiles (gis/tiles/ndvi_week_1.png .. ndvi_week_4.png)
  2. Single-date Iron-Oxide Alteration Index PNG (gis/tiles/iron_oxide_latest.png)
  3. Single-date NDVI PNG (gis/tiles/ndvi_latest.png)
  4. OpenDroneMap high-res UAV orthomosaic PNG (gis/tiles/odm_orthophoto.png)
  5. Consolidated `gis/tiles/manifest.json` for frontend MapLibre GL integration.

Validates:
  - manifest.json is valid JSON
  - Every layer has a valid 4-element numeric bounding box [west, south, east, north]
"""

import os
import sys
import json
import argparse

# Import local GIS modules
from gis.ndvi_pull import pull_single_layers, MOIL_BBOX
from gis.ndvi_timeseries import generate_ndvi_timeseries_tiles
from gis.odm_to_tile import convert_odm_to_tile


def generate_all_tiles(tiles_dir="gis/tiles", data_dir="data", dry_run=False):
    """
    Runs full tile extraction and builds gis/tiles/manifest.json.
    """
    tiles_dir = os.path.abspath(tiles_dir)
    os.makedirs(tiles_dir, exist_ok=True)

    print("=" * 70)
    print(" MOIL Reserve Intelligence — GIS Tile Pipeline & Manifest Generator")
    print("=" * 70)

    # 1. Generate Single-Date NDVI and Iron-Oxide Alteration tiles
    print("\n[STEP 1/3] Generating Single-Date Spectral Index Tiles (NDVI & Iron Oxide)...")
    single_layers_meta = pull_single_layers(tiles_dir=tiles_dir, dry_run=dry_run)

    # 2. Generate 4-Week NDVI Time-Series Tiles for MapLibre Time-Slider
    print("\n[STEP 2/3] Generating 4-Week Weekly NDVI Time-Series Tiles...")
    timeseries_meta = generate_ndvi_timeseries_tiles(tiles_dir=tiles_dir, num_weeks=4, interval_days=7, dry_run=dry_run)

    # 3. Convert OpenDroneMap Orthophoto GeoTIFF
    print("\n[STEP 3/3] Processing OpenDroneMap UAV Orthophoto Tile...")
    odm_tif = os.path.join(data_dir, "odm_orthophoto.tif")
    odm_png = os.path.join(tiles_dir, "odm_orthophoto.png")
    odm_meta = convert_odm_to_tile(input_tif_path=odm_tif, output_png_path=odm_png)

    # Helper function to convert [west, south, east, north] to MapLibre 4-point coordinates
    def to_maplibre_coords(bbox):
        w, s, e, n = bbox
        return [
            [w, n],  # Top-Left [lng, lat]
            [e, n],  # Top-Right [lng, lat]
            [e, s],  # Bottom-Right [lng, lat]
            [w, s]   # Bottom-Left [lng, lat]
        ]

    # 4. Construct Consolidated Manifest for Frontend MapLibre Developer (P4)
    manifest = {
        "title": "MOIL Reserve Intelligence - MapLibre Raster Tiles Manifest",
        "description": "Pre-rendered georeferenced raster PNG tiles and time-series layers for browser rendering in MapLibre GL.",
        "crs": "EPSG:4326 (WGS84)",
        "tiles_directory": "gis/tiles",
        "layers": {
            "ndvi_latest": {
                "id": "ndvi-latest",
                "name": "Sentinel-2 NDVI (Latest)",
                "file": "ndvi_latest.png",
                "date": single_layers_meta["ndvi_latest"]["date"],
                "bbox": single_layers_meta["ndvi_latest"]["bbox"],
                "maplibre_coordinates": to_maplibre_coords(single_layers_meta["ndvi_latest"]["bbox"]),
                "type": "raster",
                "palette_legend": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"],
                "description": "Vegetation index for environmental baseline and overburden monitoring."
            },
            "iron_oxide_latest": {
                "id": "iron-oxide-latest",
                "name": "Sentinel-2 Iron-Oxide Alteration Index",
                "file": "iron_oxide_latest.png",
                "date": single_layers_meta["iron_oxide_latest"]["date"],
                "bbox": single_layers_meta["iron_oxide_latest"]["bbox"],
                "maplibre_coordinates": to_maplibre_coords(single_layers_meta["iron_oxide_latest"]["bbox"]),
                "type": "raster",
                "palette_legend": ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"],
                "description": "Red/Blue spectral alteration ratio highlighting manganese and iron gossan signatures."
            },
            "drone_orthophoto": {
                "id": "odm-drone-orthophoto",
                "name": "UAV High-Resolution Mine Orthomosaic",
                "file": "odm_orthophoto.png",
                "date": "2026-08-30",
                "bbox": odm_meta["bbox"],
                "maplibre_coordinates": odm_meta["maplibre_coordinates"],
                "type": "raster",
                "description": "High-resolution OpenDroneMap photogrammetry for Bharweli open-cast pit."
            }
        },
        "timeseries_ndvi": []
    }

    # Populate 4-week timeseries in manifest
    for item in timeseries_meta:
        manifest["timeseries_ndvi"].append({
            "week_index": item["week_index"],
            "id": f"ndvi-week-{item['week_index']}",
            "name": f"NDVI Week {item['week_index']} ({item['date']})",
            "file": item["file"],
            "date": item["date"],
            "window_start": item["window_start"],
            "window_end": item["window_end"],
            "bbox": item["bbox"],
            "maplibre_coordinates": to_maplibre_coords(item["bbox"]),
            "type": "raster"
        })

    # Save manifest.json
    manifest_path = os.path.join(tiles_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 5. Validation Check
    print("\n" + "=" * 70)
    print(" MANIFEST VALIDATION & SANITY CHECKS")
    print("=" * 70)

    # Check JSON validity by reloading
    with open(manifest_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    print(" [x] manifest.json successfully re-parsed as valid JSON.")

    # Validate all bounding boxes
    all_bboxes = []
    for key, layer in loaded["layers"].items():
        all_bboxes.append((f"layers['{key}']", layer["bbox"]))
    for item in loaded["timeseries_ndvi"]:
        all_bboxes.append((f"timeseries['{item['file']}']", item["bbox"]))

    all_valid = True
    for label, b in all_bboxes:
        if not isinstance(b, list) or len(b) != 4:
            print(f" [!] INVALID BBOX on {label}: {b} (expected 4-element list)")
            all_valid = False
        elif not all(isinstance(x, (int, float)) for x in b):
            print(f" [!] NON-NUMERIC VALUES in {label}: {b}")
            all_valid = False
        else:
            w, s, e, n = b
            if not (w < e and s < n):
                print(f" [!] INVALID COORDINATE BOUNDS in {label}: west/south >= east/north ({b})")
                all_valid = False
            else:
                print(f" [x] Bounding Box OK: {label:32s} -> [{w}, {s}, {e}, {n}]")

    if all_valid:
        print("\n [x] ALL bounding boxes verified: 4 numeric values [west, south, east, north] in WGS84.")

    # Print summary of directory contents
    print("\n" + "=" * 70)
    print(f" SUMMARY OF FILES IN {tiles_dir}")
    print("=" * 70)
    files = sorted(os.listdir(tiles_dir))
    for fname in files:
        fpath = os.path.join(tiles_dir, fname)
        size_kb = os.path.getsize(fpath) / 1024.0
        print(f"  - {fname:25s} ({size_kb:7.1f} KB)")
    print("=" * 70)

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate all GIS tiles and manifest.json for MapLibre")
    parser.add_argument("--tiles-dir", default="gis/tiles", help="Output directory")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--dry-run", action="store_true", help="Run offline simulation")
    args = parser.parse_args()

    generate_all_tiles(tiles_dir=args.tiles_dir, data_dir=args.data_dir, dry_run=args.dry_run)
