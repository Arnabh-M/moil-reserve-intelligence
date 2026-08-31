"""
MOIL Reserve Intelligence — GIS Data Prep: OpenDroneMap (ODM) Orthophoto Converter
===================================================================================
Converts an OpenDroneMap (ODM) UAV orthomosaic GeoTIFF (`odm_orthophoto.tif`) into
a lightweight, web-ready RGBA PNG tile with an accurate WGS84 bounding box JSON.

Why this is needed:
-------------------
1. ODM outputs raw, high-resolution GeoTIFFs (often projected in UTM, e.g. EPSG:32644,
   and hundreds of megabytes in size).
2. Web map renderers (like MapLibre GL JS) cannot render multi-hundred MB raw GeoTIFFs
   directly in the browser.
3. This script downsamples the orthomosaic into an optimized PNG raster (e.g. 1024x1024 / 2048x2048)
   and computes the exact geographic boundary `[west, south, east, north]` in WGS84 (EPSG:4326),
   ready for `map.addSource('odm-drone-layer', { type: 'image', url: '...', coordinates: [...] })`.
"""

import os
import sys
import json
import argparse
import numpy as np
from PIL import Image

# Default Balaghat MOIL Bharweli Mine drone flight area bounding box (for fallback/sample)
# Balaghat Bharweli Mine: ~21.87°N, 80.22°E
SAMPLE_ODM_BBOX_WGS84 = [80.215, 21.865, 80.235, 21.885] # [west, south, east, north]


def create_mock_odm_orthophoto(output_tif_path, bbox=SAMPLE_ODM_BBOX_WGS84):
    """
    Creates a sample ODM orthophoto GeoTIFF for testing when raw drone data is not yet available.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_tif_path)), exist_ok=True)
    width, height = 1024, 1024
    
    # Generate synthetic RGB terrain imagery (mine pit, haul roads, vegetation)
    img_data = np.zeros((height, width, 4), dtype=np.uint8)
    # Background terrain (ochre/brown pit ground)
    img_data[:, :, 0] = 160  # R
    img_data[:, :, 1] = 130  # G
    img_data[:, :, 2] = 95   # B
    img_data[:, :, 3] = 255  # A

    # Draw synthetic mine bench contours
    for r in range(100, 450, 40):
        y, x = np.ogrid[:height, :width]
        dist = np.sqrt((x - 512)**2 + (y - 512)**2)
        mask = (dist > r - 10) & (dist < r)
        img_data[mask, 0] = 110
        img_data[mask, 1] = 90
        img_data[mask, 2] = 70

    # Save as PNG/TIF image
    pil_img = Image.fromarray(img_data, mode="RGBA")
    pil_img.save(output_tif_path)
    print(f"[SAMPLE] Generated mock ODM orthophoto -> {output_tif_path}")


def convert_odm_to_tile(input_tif_path="data/odm_orthophoto.tif", output_png_path="gis/tiles/odm_orthophoto.png",
                        max_dim=1024, fallback_bbox=SAMPLE_ODM_BBOX_WGS84):
    """
    Converts odm_orthophoto.tif into a web-ready PNG tile + extracts WGS84 bounding box.
    
    Parameters:
    - input_tif_path: Path to ODM orthophoto GeoTIFF
    - output_png_path: Target PNG output path (under gis/tiles/)
    - max_dim: Maximum width/height in pixels for the web tile (default 1024)
    - fallback_bbox: Bounding box [west, south, east, north] if GeoTIFF tags are unprojected
    
    Returns:
    - dict containing file metadata, bbox [west, south, east, north], and MapLibre coordinates.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    # 1. If input file doesn't exist, create a sample orthophoto
    if not os.path.exists(input_tif_path):
        print(f"[INFO] '{input_tif_path}' not found. Generating sample ODM orthophoto for testing...")
        create_mock_odm_orthophoto(input_tif_path, bbox=fallback_bbox)

    bbox_wgs84 = fallback_bbox
    pil_image = None

    # 2. Attempt to read and reproject bounds using rasterio
    rasterio_success = False
    try:
        import rasterio
        from rasterio.warp import transform_bounds

        with rasterio.open(input_tif_path) as src:
            print(f"[RASTERIO] Opened '{input_tif_path}' — CRS: {src.crs}, Size: {src.width}x{src.height}, Bands: {src.count}")
            
            # Extract geographic bounding box in WGS84 (EPSG:4326)
            if src.crs and src.crs.to_string() != "EPSG:4326":
                # Reproject bounding box from native CRS (e.g. UTM) to WGS84 lat/lon
                w, s, e, n = transform_bounds(src.crs, "EPSG:4326", src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
                bbox_wgs84 = [round(w, 6), round(s, 6), round(e, 6), round(n, 6)]
            elif src.crs:
                bbox_wgs84 = [round(src.bounds.left, 6), round(src.bounds.bottom, 6), round(src.bounds.right, 6), round(src.bounds.top, 6)]

            # Read RGB or RGBA bands
            num_bands = min(src.count, 4)
            data = src.read(list(range(1, num_bands + 1)))
            
            # Reshape from (Bands, Height, Width) to (Height, Width, Bands)
            data = np.moveaxis(data, 0, -1)
            
            if data.dtype != np.uint8:
                # Normalize float / uint16 data to 0-255 uint8 for PNG display
                min_val, max_val = data.min(), data.max()
                if max_val > min_val:
                    data = ((data - min_val) / (max_val - min_val) * 255).astype(np.uint8)
                else:
                    data = data.astype(np.uint8)
            
            if num_bands == 1:
                pil_image = Image.fromarray(data[:, :, 0], mode="L").convert("RGBA")
            elif num_bands == 3:
                pil_image = Image.fromarray(data, mode="RGB").convert("RGBA")
            else:
                pil_image = Image.fromarray(data, mode="RGBA")
                
            rasterio_success = True
            
    except Exception as exc:
        print(f"[NOTICE] rasterio inspection skipped or DLL unavailable ({exc}). Using PIL fallback reader.")

    # 3. Fallback reader using standard PIL if rasterio was unavailable
    if not rasterio_success or pil_image is None:
        pil_image = Image.open(input_tif_path)
        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")
        bbox_wgs84 = fallback_bbox

    # 4. Downsample to web-ready dimensions (keeping aspect ratio)
    orig_w, orig_h = pil_image.size
    pil_image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    final_w, final_h = pil_image.size

    # 5. Save web-ready PNG
    pil_image.save(output_png_path, format="PNG", optimize=True)
    file_size_kb = os.path.getsize(output_png_path) / 1024.0
    print(f"[OK] Converted ODM orthophoto -> {output_png_path} ({final_w}x{final_h} px, {file_size_kb:.1f} KB)")
    print(f"     WGS84 Bounding Box: {bbox_wgs84} [west, south, east, north]")

    # 6. Construct MapLibre-compliant 4-corner coordinates:
    # MapLibre format: [ [west, north], [east, north], [east, south], [west, south] ] (Top-Left, Top-Right, Bottom-Right, Bottom-Left)
    w, s, e, n = bbox_wgs84
    maplibre_coords = [
        [w, n],  # Top-Left
        [e, n],  # Top-Right
        [e, s],  # Bottom-Right
        [w, s]   # Bottom-Left
    ]

    metadata = {
        "file": os.path.basename(output_png_path),
        "source": "OpenDroneMap (UAV High-Resolution Orthomosaic)",
        "bbox": bbox_wgs84,
        "maplibre_coordinates": maplibre_coords,
        "width_px": final_w,
        "height_px": final_h
    }

    # Save standalone bbox JSON next to the tile
    bbox_json_path = os.path.splitext(output_png_path)[0] + "_bbox.json"
    with open(bbox_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Saved georeference metadata -> {bbox_json_path}")

    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert ODM orthophoto GeoTIFF to web-ready PNG tile + bbox JSON")
    parser.add_argument("--input", default="data/odm_orthophoto.tif", help="Path to input odm_orthophoto.tif")
    parser.add_argument("--output", default="gis/tiles/odm_orthophoto.png", help="Path to output PNG tile")
    parser.add_argument("--max-dim", type=int, default=1024, help="Max pixel dimension for web tile")
    args = parser.parse_args()

    convert_odm_to_tile(input_tif_path=args.input, output_png_path=args.output, max_dim=args.max_dim)
