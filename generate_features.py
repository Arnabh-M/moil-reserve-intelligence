"""
MOIL Reserve Intelligence (SIH26009) — Part 1: Feature Engineering
====================================================================
1. Generates a synthetic structural lineament dataset (structural
   lines biased toward 1-2 dominant strike directions per site).
2. Computes 4 engineered features for every point in
   data/deposit_ground_truth.csv:
     - dist_to_nearest_structure (meters, projected/geodesic, not
       raw lat/lon Euclidean)
     - structural_density (line count within 2km)
     - synthetic_ndvi (spatially-correlated field, [-1, 1])
     - synthetic_elevation (spatially-correlated field, ~300-650m)
3. Saves data/training_features.csv and persists the two random-field
   interpolators (models/ndvi_field.pkl, models/elevation_field.pkl)
   so build_confidence_surface.py (Part 3) samples the SAME fields
   rather than regenerating new noise.

Run: python generate_features.py
"""

import os

import numpy as np
import pandas as pd

from geo_utils import (
    COMBINED_BBOX,
    SITE_BBOXES,
    build_correlated_field,
    compute_structural_features,
    sample_field,
    save_field,
)

RNG_SEED = 7
rng = np.random.default_rng(RNG_SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

STRUCTURE_TYPES = ["fault", "fold_axis", "shear_zone"]

# Dominant / secondary strike directions per site (degrees, axial —
# a line at azimuth theta is identical to one at theta+180).
# Real structural belts cluster around 1-2 preferred trends rather
# than being isotropic, so each site draws mostly from a dominant
# azimuth with some scatter, plus a minority secondary trend.
SITE_STRIKES = {
    "balaghat": {"dominant": 45, "secondary": 135, "dominant_weight": 0.7},
    "nagpur":   {"dominant": 150, "secondary": 60, "dominant_weight": 0.75},
    "bhandara": {"dominant": 20, "secondary": 100, "dominant_weight": 0.7},
}


def sample_azimuth(strike_cfg, n):
    dominant = rng.random(n) < strike_cfg["dominant_weight"]
    az = np.where(
        dominant,
        rng.normal(strike_cfg["dominant"], 12, n),
        rng.normal(strike_cfg["secondary"], 12, n),
    )
    return np.mod(az, 180.0)


def generate_structural_lines():
    from geo_utils import lonlat_to_utm, utm_to_lonlat

    rows = []
    line_counter = 1

    for site_id, box in SITE_BBOXES.items():
        n_lines = int(rng.integers(15, 21))  # 15-20 per site
        lat_lo, lat_hi = box["lat_range"]
        lon_lo, lon_hi = box["lon_range"]

        center_lats = rng.uniform(lat_lo, lat_hi, n_lines)
        center_lons = rng.uniform(lon_lo, lon_hi, n_lines)
        azimuths_deg = sample_azimuth(SITE_STRIKES[site_id], n_lines)
        lengths_m = rng.uniform(500, 3000, n_lines)
        types = rng.choice(STRUCTURE_TYPES, size=n_lines, p=[0.4, 0.35, 0.25])

        cx, cy = lonlat_to_utm(center_lons, center_lats)
        az_rad = np.deg2rad(azimuths_deg)
        half = lengths_m / 2.0
        dx = np.sin(az_rad) * half  # azimuth measured from North, clockwise
        dy = np.cos(az_rad) * half

        start_x, start_y = cx - dx, cy - dy
        end_x, end_y = cx + dx, cy + dy
        start_lon, start_lat = utm_to_lonlat(start_x, start_y)
        end_lon, end_lat = utm_to_lonlat(end_x, end_y)

        for i in range(n_lines):
            rows.append(
                {
                    "line_id": f"ln_{line_counter:03d}",
                    "site_id": site_id,
                    "start_lat": round(float(start_lat[i]), 6),
                    "start_lon": round(float(start_lon[i]), 6),
                    "end_lat": round(float(end_lat[i]), 6),
                    "end_lon": round(float(end_lon[i]), 6),
                    "structure_type": types[i],
                }
            )
            line_counter += 1

    df = pd.DataFrame(rows)
    path = os.path.join(DATA_DIR, "structural_lines.csv")
    df.to_csv(path, index=False)
    return df


def build_and_save_fields():
    # Independent seeds so NDVI and elevation aren't the same surface.
    ndvi_field = build_correlated_field(COMBINED_BBOX, seed=101, grid_res=120, smoothing_sigma=6.0)
    elevation_field = build_correlated_field(COMBINED_BBOX, seed=202, grid_res=120, smoothing_sigma=6.0)

    save_field(ndvi_field, os.path.join(MODELS_DIR, "ndvi_field.pkl"))
    save_field(elevation_field, os.path.join(MODELS_DIR, "elevation_field.pkl"))
    return ndvi_field, elevation_field


def compute_training_features(lines_df, ndvi_field, elevation_field):
    deposits_path = os.path.join(DATA_DIR, "deposit_ground_truth.csv")
    deposits = pd.read_csv(deposits_path)

    min_dist_m, density = compute_structural_features(
        deposits["longitude"].values, deposits["latitude"].values, lines_df, density_radius_km=2.0
    )

    ndvi_raw = sample_field(ndvi_field, deposits["longitude"].values, deposits["latitude"].values)
    elev_raw = sample_field(elevation_field, deposits["longitude"].values, deposits["latitude"].values)

    synthetic_ndvi = ndvi_raw * 2 - 1  # [0,1] -> [-1,1]
    synthetic_elevation = 300 + elev_raw * (650 - 300)  # [0,1] -> [300,650]

    deposits["dist_to_nearest_structure"] = np.round(min_dist_m, 1)
    deposits["structural_density"] = density
    deposits["synthetic_ndvi"] = np.round(synthetic_ndvi, 4)
    deposits["synthetic_elevation"] = np.round(synthetic_elevation, 1)

    out_path = os.path.join(DATA_DIR, "training_features.csv")
    deposits.to_csv(out_path, index=False)
    return deposits


def main():
    print("=" * 70)
    print("Part 1: Feature Engineering + Structural Line Dataset")
    print("=" * 70)

    lines_df = generate_structural_lines()
    print(f"\n[structural_lines.csv] {len(lines_df)} lines written")
    print(lines_df["site_id"].value_counts().to_string())
    print("structure_type counts:")
    print(lines_df["structure_type"].value_counts().to_string())

    ndvi_field, elevation_field = build_and_save_fields()
    print("\nSaved random-field interpolators: models/ndvi_field.pkl, models/elevation_field.pkl")

    features_df = compute_training_features(lines_df, ndvi_field, elevation_field)
    print(f"\n[training_features.csv] {len(features_df)} rows, {len(features_df.columns)} columns")
    print(features_df.columns.tolist())
    print("\nEngineered feature summary:")
    print(
        features_df[
            ["dist_to_nearest_structure", "structural_density", "synthetic_ndvi", "synthetic_elevation"]
        ].describe().round(2).to_string()
    )
    print("\nBy confirmed/unconfirmed (mean values):")
    print(
        features_df.groupby("is_confirmed_deposit")[
            ["dist_to_nearest_structure", "structural_density", "synthetic_ndvi", "synthetic_elevation"]
        ].mean().round(2).to_string()
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
