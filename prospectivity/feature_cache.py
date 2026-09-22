"""
MOIL Reserve Intelligence (SIH26009) — Feature Stack Caching
============================================================
Extracts and caches multi-source remote sensing features from Earth Engine:
- Uses prospectivity.gee_features.build_feature_stack for real GEE extraction
- Caches training points to data/cache/training_features_{site_id}.csv
- Caches prediction grid points to data/cache/grid_features_{site_id}.npz
- Cache directory data/cache/ is git-ignored

Pending features:
  ndvi_anomaly, ndri, ndwi, iron_oxide_index, clay_index,
  manganese_spectral_ratio, slope, aspect, terrain_ruggedness
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from shapely.geometry import mapping

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prospectivity.gee_features import (
    FEATURE_NAMES,
    build_feature_stack,
    initialize_ee,
    GEEUnavailableError,
)
from prospectivity.grid import build_all_grids, SiteGrid
from prospectivity.training_data import (
    PENDING_SATELLITE_FEATURES,
    RANDOM_STATE,
    attach_structural_features,
    build_all_sites,
    generate_site_training_points,
    load_site_boundaries,
)

logger = logging.getLogger(__name__)
CACHE_DIR = os.path.join(REPO_ROOT, "data", "cache")


def ensure_cache_dir() -> str:
    """Ensure data/cache exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR


def get_training_cache_path(site_id: str) -> str:
    return os.path.join(CACHE_DIR, f"training_features_{site_id}.csv")


def get_grid_cache_path(site_id: str) -> str:
    return os.path.join(CACHE_DIR, f"grid_features_{site_id}.npz")


def sample_gee_points(ee, stack_img, lons: np.ndarray, lats: np.ndarray, batch_size: int = 1000) -> Dict[str, np.ndarray]:
    """
    Sample an Earth Engine Image stack at given longitude and latitude coordinates.
    Returns a dictionary mapping feature name to a 1D numpy array of values.
    """
    n = len(lons)
    out_dict: Dict[str, List[float]] = {f: [] for f in PENDING_SATELLITE_FEATURES}

    for start_idx in range(0, n, batch_size):
        end_idx = min(start_idx + batch_size, n)
        batch_feats = []
        for i in range(start_idx, end_idx):
            pt = ee.Geometry.Point([float(lons[i]), float(lats[i])])
            batch_feats.append(ee.Feature(pt, {"idx": i}))
        
        fc = ee.FeatureCollection(batch_feats)
        sampled = stack_img.sampleRegions(collection=fc, scale=10, geometries=False)
        info = sampled.getInfo()
        records = info.get("features", [])
        
        # Build index lookup for the batch
        batch_lookup = {r["properties"].get("idx"): r["properties"] for r in records}
        for i in range(start_idx, end_idx):
            props = batch_lookup.get(i, {})
            for f in PENDING_SATELLITE_FEATURES:
                val = props.get(f)
                out_dict[f].append(float(val) if val is not None and not np.isnan(val) else np.nan)

    return {f: np.array(vals, dtype=float) for f, vals in out_dict.items()}


def compute_deterministic_proxy(lons: np.ndarray, lats: np.ndarray, site_id: str) -> Dict[str, np.ndarray]:
    """
    Deterministic realistic spatial proxy for offline/dry-run mode when live GEE is unavailable.
    Produces physically plausible values within standard ranges for each sensor index.
    """
    seed = abs(hash(site_id)) % (2**31)
    rng = np.random.default_rng(seed)
    n = len(lons)

    # Normalize coordinates within site
    lon_norm = (lons - lons.min()) / max(lons.max() - lons.min(), 1e-6)
    lat_norm = (lats - lats.min()) / max(lats.max() - lats.min(), 1e-6)

    # Smooth spatial gradients
    grad_x = np.sin(lon_norm * np.pi * 2)
    grad_y = np.cos(lat_norm * np.pi * 2)

    ndvi_anom = np.clip(-0.15 + 0.10 * grad_x + rng.normal(0, 0.05, n), -0.5, 0.5)
    ndri = np.clip(0.10 + 0.08 * grad_y + rng.normal(0, 0.04, n), -1.0, 1.0)
    ndwi = np.clip(-0.25 + 0.05 * grad_x + rng.normal(0, 0.05, n), -1.0, 1.0)
    iron_ox = np.clip(1.20 + 0.25 * grad_y + rng.normal(0, 0.10, n), 0.5, 3.5)
    clay_idx = np.clip(1.05 + 0.20 * grad_x + rng.normal(0, 0.08, n), 0.4, 3.0)
    mn_ratio = np.clip(0.12 + 0.05 * (grad_x + grad_y) + rng.normal(0, 0.03, n), -0.5, 0.5)

    slope = np.clip(8.0 + 12.0 * np.abs(grad_x) + rng.exponential(3.0, n), 0.0, 45.0)
    aspect = np.mod(180.0 + 120.0 * grad_y + rng.uniform(-30, 30, n), 360.0)
    ruggedness = np.clip(12.0 + 15.0 * np.abs(grad_x) + rng.exponential(5.0, n), 0.0, 100.0)

    return {
        "ndvi_anomaly": ndvi_anom,
        "ndri": ndri,
        "ndwi": ndwi,
        "iron_oxide_index": iron_ox,
        "clay_index": clay_idx,
        "manganese_spectral_ratio": mn_ratio,
        "slope": slope,
        "aspect": aspect,
        "terrain_ruggedness": ruggedness,
    }


def cache_features_for_all_sites(ee=None, force: bool = False, dry_run: bool = False) -> None:
    """
    Builds and caches pending satellite features for training points and prediction grids across all sites.
    """
    ensure_cache_dir()
    sites = load_site_boundaries()
    grids = build_all_grids()
    rng = np.random.default_rng(RANDOM_STATE)

    for site_key, site in sites.items():
        logger.info("Processing features for site '%s'...", site_key)
        train_cache_file = get_training_cache_path(site_key)
        grid_cache_file = get_grid_cache_path(site_key)

        grid = grids.get(site_key)
        if not grid:
            logger.warning("No grid available for site '%s', skipping.", site_key)
            continue

        # 1. Training points
        ts = generate_site_training_points(site_key, site, rng)
        ts.points = attach_structural_features(ts.points)
        train_df = ts.points.copy()

        # Check if already cached
        need_train = force or not os.path.exists(train_cache_file)
        need_grid = force or not os.path.exists(grid_cache_file)

        if not need_train and not need_grid:
            logger.info("Site '%s' is already fully cached. Skipping.", site_key)
            continue

        if ee is not None and not dry_run:
            logger.info("[%s] Computing feature stack via live Earth Engine...", site_key)
            # Convert shapely polygon to EE Geometry
            geom_json = mapping(site["geom"])
            ee_geom = ee.Geometry(geom_json)
            stack_res = build_feature_stack(ee, ee_geom)
            stack_img = stack_res.image

            if need_train:
                logger.info("[%s] Sampling GEE feature stack for %d training points...", site_key, len(train_df))
                sampled_train = sample_gee_points(ee, stack_img, train_df["lon"].values, train_df["lat"].values)
                for f, vals in sampled_train.items():
                    train_df[f] = vals
                train_df.to_csv(train_cache_file, index=False)
                logger.info("[%s] Saved cached training features to %s", site_key, train_cache_file)

            if need_grid:
                logger.info("[%s] Sampling GEE feature stack for %d prediction grid cells...", site_key, len(grid.centers_lonlat))
                # For large grids, sample in chunks or use subsampling
                sampled_grid = sample_gee_points(ee, stack_img, grid.centers_lonlat[:, 0], grid.centers_lonlat[:, 1], batch_size=2000)
                save_dict = {
                    "centers_utm": grid.centers_utm,
                    "centers_lonlat": grid.centers_lonlat,
                }
                save_dict.update(sampled_grid)
                np.savez_compressed(grid_cache_file, **save_dict)
                logger.info("[%s] Saved cached grid features to %s", site_key, grid_cache_file)

        else:
            mode_label = "DRY-RUN / PROXY" if dry_run else "OFFLINE DETERMINISTIC PROXY"
            logger.warning("[%s] Running in %s mode (GEE not connected).", site_key, mode_label)
            if need_train:
                proxy_train = compute_deterministic_proxy(train_df["lon"].values, train_df["lat"].values, site_key)
                for f, vals in proxy_train.items():
                    train_df[f] = vals
                train_df.to_csv(train_cache_file, index=False)
                logger.info("[%s] Saved proxy training features to %s", site_key, train_cache_file)

            if need_grid:
                proxy_grid = compute_deterministic_proxy(grid.centers_lonlat[:, 0], grid.centers_lonlat[:, 1], site_key)
                save_dict = {
                    "centers_utm": grid.centers_utm,
                    "centers_lonlat": grid.centers_lonlat,
                }
                save_dict.update(proxy_grid)
                np.savez_compressed(grid_cache_file, **save_dict)
                logger.info("[%s] Saved proxy grid features to %s", site_key, grid_cache_file)


def load_cached_training_set(site_id: str) -> Optional[pd.DataFrame]:
    """Loads cached training features dataframe for a site."""
    path = get_training_cache_path(site_id)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def load_cached_grid_features(site_id: str) -> Optional[Dict[str, np.ndarray]]:
    """Loads cached prediction grid features for a site."""
    path = get_grid_cache_path(site_id)
    if os.path.exists(path):
        data = np.load(path)
        return {k: data[k] for k in data.files}
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Cache GEE feature stacks for training and grid points.")
    parser.add_argument("--force", action="store_true", help="Force recomputation of cached features.")
    parser.add_argument("--dry-run", action="store_true", help="Generate deterministic proxy features without live GEE.")
    args = parser.parse_args()

    ee_inst = None
    if not args.dry_run:
        try:
            ee_inst = initialize_ee()
            print("\n[GEE] Earth Engine successfully initialized.")
        except GEEUnavailableError as err:
            print("\n" + "=" * 72)
            print("[NOTICE] Earth Engine is not currently authenticated.")
            print(err)
            print("\nTo authenticate with your Google Cloud Project:")
            print('  PowerShell: & "C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python314\\Scripts\\earthengine.exe" authenticate')
            print('  Set project: $env:EE_PROJECT="your-gcp-project-id"')
            print('  Or set EE_PROJECT in .env')
            print("=" * 72 + "\n")
            if not args.dry_run:
                print("Exiting. Pass --dry-run to test with deterministic proxy data.")
                sys.exit(1)

    cache_features_for_all_sites(ee=ee_inst, force=args.force, dry_run=args.dry_run)
    print("\nFeature caching complete.")
