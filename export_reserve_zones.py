"""
MOIL Reserve Intelligence (SIH26009) — Part 4: Export to GeoJSON
====================================================================
Converts the kriged confidence surface (data/confidence_surface.npz,
from Part 3) into a GeoJSON FeatureCollection of small rectangular
cells, each carrying confidence_score and site_id. Cells whose center
doesn't fall inside any of the 3 known site bounding boxes are
dropped rather than exported with a null site_id.

NOTE on the P1 /reserve-zones contract: this script assumes site_id
is the plain lowercase string used since Day 1 ("balaghat", "nagpur",
"bhandara") — the same value used as MineSite.id in the graph and
site_id throughout every CSV. I don't have visibility into P1's
actual endpoint/schema code, so if P1 expects a different id format
(a UUID, a numeric id, etc.) that needs to be confirmed with whoever
owns P1 and reconciled — this script does not verify it.

Run: python export_reserve_zones.py
"""

import json
import os

import numpy as np
import pandas as pd
from shapely.geometry import box, mapping

from geo_utils import assign_site_id

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

SURFACE_PATH = os.path.join(DATA_DIR, "confidence_surface.npz")
OUT_PATH = os.path.join(DATA_DIR, "reserve_zones.geojson")


def build_features(lon_grid, lat_grid, confidence):
    n_rows, n_cols = lon_grid.shape
    lon_step = (lon_grid[0, -1] - lon_grid[0, 0]) / (n_cols - 1)
    lat_step = (lat_grid[-1, 0] - lat_grid[0, 0]) / (n_rows - 1)
    half_lon, half_lat = lon_step / 2, lat_step / 2

    features = []
    skipped = 0

    for i in range(n_rows):
        for j in range(n_cols):
            lon = float(lon_grid[i, j])
            lat = float(lat_grid[i, j])

            site_id = assign_site_id(lon, lat)
            if site_id is None:
                skipped += 1
                continue

            cell = box(lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat)
            score = float(np.clip(confidence[i, j], 0.0, 1.0))

            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(cell),
                    "properties": {
                        "confidence_score": round(score, 4),
                        "site_id": site_id,
                    },
                }
            )

    return features, skipped


def sanity_check_against_known_deposits(features):
    deposits = pd.read_csv(os.path.join(DATA_DIR, "deposit_ground_truth.csv"))
    confirmed = deposits[deposits["is_confirmed_deposit"]]

    # one confirmed deposit per site for a spread-out spot check
    sample = confirmed.groupby("site_id").first().reset_index().head(3)

    cell_centers = np.array(
        [
            (
                (f["geometry"]["coordinates"][0][0][0] + f["geometry"]["coordinates"][0][2][0]) / 2,
                (f["geometry"]["coordinates"][0][0][1] + f["geometry"]["coordinates"][0][2][1]) / 2,
                f["properties"]["confidence_score"],
            )
            for f in features
        ]
    )
    all_scores = cell_centers[:, 2]
    overall_mean = all_scores.mean()

    print("\nSanity check: known deposits vs. nearest grid cell confidence_score")
    print(f"  Overall mean confidence_score across exported cells: {overall_mean:.3f}")
    for _, row in sample.iterrows():
        d_lon, d_lat = row["longitude"], row["latitude"]
        dists = np.hypot(cell_centers[:, 0] - d_lon, cell_centers[:, 1] - d_lat)
        nearest_idx = np.argmin(dists)
        nearest_score = cell_centers[nearest_idx, 2]
        flag = "OK (above mean)" if nearest_score > overall_mean else "check (at/below mean)"
        print(
            f"  {row['deposit_id']} ({row['site_id']}): nearest cell score = "
            f"{nearest_score:.3f} [{flag}]"
        )


def main():
    print("=" * 70)
    print("Part 4: Export to GeoJSON")
    print("=" * 70)

    surface = np.load(SURFACE_PATH)
    lon_grid, lat_grid, confidence = surface["lon_grid"], surface["lat_grid"], surface["confidence"]
    print(f"\nLoaded confidence surface: {confidence.shape} grid from {SURFACE_PATH}")

    features, skipped = build_features(lon_grid, lat_grid, confidence)

    feature_collection = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(feature_collection, f)

    print(f"\nExported {len(features)} cells to {OUT_PATH} ({skipped} cells outside all site bboxes were dropped)")

    scores_df = pd.DataFrame(
        [{"site_id": f["properties"]["site_id"], "confidence_score": f["properties"]["confidence_score"]} for f in features]
    )
    print("\nconfidence_score distribution per site:")
    print(scores_df.groupby("site_id")["confidence_score"].agg(["count", "min", "max", "mean"]).round(3).to_string())

    sanity_check_against_known_deposits(features)
    print("\nDone.")
    print("=" * 70)


if __name__ == "__main__":
    main()
