"""
MOIL Reserve Intelligence (SIH26009) — Part 3: Grid Prediction + Kriging
====================================================================
1. Builds a 50x50 grid over the combined bounding box.
2. Computes the SAME 4 features as Part 1, reusing
   data/structural_lines.csv and the SAVED random-field interpolators
   from Part 1 (models/ndvi_field.pkl, models/elevation_field.pkl) —
   no new random fields are generated here.
3. Loads models/reserve_classifier.pkl and predicts a probability
   (predict_proba) for every grid point.
4. Krige those grid-point probabilities with PyKrige's
   OrdinaryKriging. Spherical and exponential variogram models are
   compared via k-fold cross-validation on a subsample (full
   leave-one-out CV over 2500 points would mean re-inverting a large
   kriging matrix thousands of times — intractable for a same-day
   prototype run, so a 5-fold CV on a 200-point subsample is used as
   a fast, still-genuine proxy for model selection).
5. Resamples the kriged surface onto a clean, axis-aligned 100x100
   lon/lat grid (kriging is evaluated at each output point's
   projected UTM location via 'points' mode, so the output grid
   stays simple rectangles for Part 4's polygon export).

Run: python build_confidence_surface.py
"""

import os

import joblib
import numpy as np
import pandas as pd
from pykrige.ok import OrdinaryKriging
from sklearn.model_selection import KFold

from geo_utils import COMBINED_BBOX, compute_structural_features, lonlat_to_utm, load_field, sample_field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")

FEATURES = ["dist_to_nearest_structure", "structural_density", "synthetic_ndvi", "synthetic_elevation"]
RNG_SEED = 11
GRID_N_INPUT = 50   # kriging input grid (predictions)
GRID_N_OUTPUT = 100  # resampled output grid (for polygon export)
VARIOGRAM_RANGE_M = 7500.0  # ~7.5km, mid-point of the 5-10km guidance
CV_SUBSAMPLE = 200


def build_prediction_grid(bbox, n):
    west, south, east, north = bbox
    lons = np.linspace(west, east, n)
    lats = np.linspace(south, north, n)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lon_grid, lat_grid


def compute_grid_features(lon_flat, lat_flat, lines_df, ndvi_field, elevation_field):
    min_dist_m, density = compute_structural_features(lon_flat, lat_flat, lines_df, density_radius_km=2.0)
    ndvi_raw = sample_field(ndvi_field, lon_flat, lat_flat)
    elev_raw = sample_field(elevation_field, lon_flat, lat_flat)

    synthetic_ndvi = ndvi_raw * 2 - 1
    synthetic_elevation = 300 + elev_raw * (650 - 300)

    return pd.DataFrame(
        {
            "dist_to_nearest_structure": min_dist_m,
            "structural_density": density,
            "synthetic_ndvi": synthetic_ndvi,
            "synthetic_elevation": synthetic_elevation,
        }
    )


def cv_rmse(x, y, z, variogram_model, rng, n_splits=5):
    n = len(z)
    idx = rng.choice(n, size=min(CV_SUBSAMPLE, n), replace=False)
    x_s, y_s, z_s = x[idx], y[idx], z[idx]

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=RNG_SEED)
    sq_errors = []
    psill = float(np.var(z_s))
    variogram_parameters = [psill, VARIOGRAM_RANGE_M, 0.01 * psill]

    for train_idx, val_idx in kf.split(x_s):
        ok = OrdinaryKriging(
            x_s[train_idx], y_s[train_idx], z_s[train_idx],
            variogram_model=variogram_model,
            variogram_parameters=variogram_parameters,
            verbose=False, enable_plotting=False,
        )
        z_pred, _ = ok.execute("points", x_s[val_idx], y_s[val_idx])
        sq_errors.extend((np.asarray(z_pred) - z_s[val_idx]) ** 2)

    return float(np.sqrt(np.mean(sq_errors)))


def main():
    print("=" * 70)
    print("Part 3: Grid Prediction + Kriging")
    print("=" * 70)

    rng = np.random.default_rng(RNG_SEED)

    lines_df = pd.read_csv(os.path.join(DATA_DIR, "structural_lines.csv"))
    ndvi_field = load_field(os.path.join(MODELS_DIR, "ndvi_field.pkl"))
    elevation_field = load_field(os.path.join(MODELS_DIR, "elevation_field.pkl"))
    classifier = joblib.load(os.path.join(MODELS_DIR, "reserve_classifier.pkl"))

    # --- 1. 50x50 input grid ---
    lon_grid, lat_grid = build_prediction_grid(COMBINED_BBOX, GRID_N_INPUT)
    lon_flat, lat_flat = lon_grid.ravel(), lat_grid.ravel()
    print(f"\nInput grid: {GRID_N_INPUT}x{GRID_N_INPUT} = {len(lon_flat)} points over {COMBINED_BBOX}")

    # --- 2. same 4 features, reusing structural_lines.csv + saved fields ---
    grid_features = compute_grid_features(lon_flat, lat_flat, lines_df, ndvi_field, elevation_field)
    print("Computed features for grid points (reused structural_lines.csv + saved random fields).")

    # --- 3. predict_proba ---
    proba = classifier.predict_proba(grid_features[FEATURES])[:, 1]
    print(f"Predicted probabilities: min={proba.min():.3f}, max={proba.max():.3f}, mean={proba.mean():.3f}")

    # --- 4. krige: compare spherical vs exponential via CV ---
    x_utm, y_utm = lonlat_to_utm(lon_flat, lat_flat)

    print(f"\nCross-validating variogram models (5-fold, {CV_SUBSAMPLE}-point subsample)...")
    rmse_spherical = cv_rmse(x_utm, y_utm, proba, "spherical", rng)
    rmse_exponential = cv_rmse(x_utm, y_utm, proba, "exponential", rng)
    print(f"  spherical   CV RMSE: {rmse_spherical:.4f}")
    print(f"  exponential CV RMSE: {rmse_exponential:.4f}")

    best_model = "spherical" if rmse_spherical <= rmse_exponential else "exponential"
    print(f"  Winner: {best_model} (range={VARIOGRAM_RANGE_M/1000:.1f}km)")

    psill = float(np.var(proba))
    variogram_parameters = [psill, VARIOGRAM_RANGE_M, 0.01 * psill]

    print(f"\nFitting final OrdinaryKriging on all {len(proba)} grid points...")
    ok_final = OrdinaryKriging(
        x_utm, y_utm, proba,
        variogram_model=best_model,
        variogram_parameters=variogram_parameters,
        verbose=False, enable_plotting=False,
    )

    # --- 5. resample onto a clean 100x100 lon/lat grid ---
    out_lon_grid, out_lat_grid = build_prediction_grid(COMBINED_BBOX, GRID_N_OUTPUT)
    out_lon_flat, out_lat_flat = out_lon_grid.ravel(), out_lat_grid.ravel()
    out_x_utm, out_y_utm = lonlat_to_utm(out_lon_flat, out_lat_flat)

    print(f"Resampling kriged surface onto {GRID_N_OUTPUT}x{GRID_N_OUTPUT} output grid...")
    z_out, sigma_out = ok_final.execute("points", out_x_utm, out_y_utm)
    z_out = np.clip(np.asarray(z_out), 0, 1).reshape(out_lon_grid.shape)
    sigma_out = np.asarray(sigma_out).reshape(out_lon_grid.shape)

    out_path = os.path.join(DATA_DIR, "confidence_surface.npz")
    np.savez(
        out_path,
        lon_grid=out_lon_grid,
        lat_grid=out_lat_grid,
        confidence=z_out,
        variance=sigma_out,
        variogram_model=best_model,
    )

    print(f"\nSaved kriged confidence surface to {out_path}")
    print(f"  confidence: min={z_out.min():.3f}, max={z_out.max():.3f}, mean={z_out.mean():.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
