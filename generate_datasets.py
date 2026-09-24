"""
MOIL Reserve Intelligence (SIH26009) — Synthetic Dataset Generator
====================================================================
Generates the CSVs consistent with seed_graph.cypher's node IDs:

  1. production_history.csv     — 630 days (2025-01-01..2026-09-22) of
                                    daily output per site, causally driven
                                    by real rainfall, equipment downtime,
                                    accumulated backlog and delayed blasts.
                                    See scripts/synthetic_operations.py.
  2. equipment_downtime_log.csv — same span, 19-machine renewal-process
                                    reliability model (also
                                    scripts/synthetic_operations.py).
  3. blast_events.csv           — delayed-blast events feeding term 4
                                    above (scripts/synthetic_operations.py).
  4. deposit_ground_truth.csv   — 40 labeled points for tomorrow's
                                    deposit classifier. is_confirmed_deposit
                                    is drawn Bernoulli(p) where p is a
                                    logistic function of the point's OWN
                                    structural/NDVI/elevation features (the
                                    same 4 the classifier later trains on),
                                    so the label carries real, moderate,
                                    noisy signal instead of being a
                                    feature-independent coin flip.

Run:  python generate_datasets.py
Output: ./data/*.csv
"""

import os

import numpy as np
import pandas as pd

import generate_features as _gf
from geo_utils import compute_structural_features, sample_field
from scripts.synthetic_operations import (
    DATA_DIR,
    END_DATE,
    START_DATE,
    generate_equipment_downtime_log,
    generate_production_history,
    print_downtime_summary,
    print_production_summary,
    sha256_of,
)

# deposit_ground_truth.csv draws from its OWN Generator, never anything in
# scripts.synthetic_operations. production_history.csv and
# equipment_downtime_log.csv are generated first (via that module, which
# owns its own RNG_SEED=42 / PRODUCTION_RNG_SEED=43 streams); keeping
# deposits (locations AND the feature-conditioned label) on a separate
# stream means nothing about the deposit step can shift the byte content
# of those two files, and nothing in synthetic_operations.py can shift
# deposit_ground_truth.csv's.
DEPOSIT_RNG_SEED = 2026

# Logistic label rule (STEP 2). Each feature is z-scored across the sample,
# perturbed with Gaussian noise, weighted, summed, and pushed through a
# sigmoid to get P(confirmed); the label is then a Bernoulli draw. Weights
# make distance-to-structure and structural density the dominant signals
# (matching the real Malkansu prospectivity study's top features); NDVI and
# elevation are weak secondary terms. dist_to_nearest_structure enters with a
# negative sign: closer to a mapped structure -> more likely a real deposit.
LABEL_FEATURE_WEIGHTS = {
    "dist_to_nearest_structure": -2.10,
    "structural_density": 1.75,
    "synthetic_ndvi": 0.35,
    "synthetic_elevation": 0.28,
}
# Noise added to every z-scored feature before the weighted sum, so the rule
# is a moderate probabilistic tendency, not a clean separator.
LABEL_ZSCORE_NOISE_SD = 0.42

OUT_DIR = str(DATA_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# Site config for deposit_ground_truth.csv — lat/lon ranges come from
# data/moil_sites.json via geo_utils, so this cannot drift from the DB,
# the pipelines or the map. site_id/target_output/equipment roster for
# production_history.csv and equipment_downtime_log.csv now live in
# scripts/synthetic_operations.py (SITE_IDS there is the same
# moil_sites.json, just read directly rather than via geo_utils).
# ---------------------------------------------------------------------
from geo_utils import SITE_AOIS, SITE_BBOXES  # noqa: E402

SITES = {
    key: {
        "target_output": SITE_AOIS[key]["target_output"],
        "lat_range": box["lat_range"],
        "lon_range": box["lon_range"],
    }
    for key, box in SITE_BBOXES.items()
}
SITE_IDS = list(SITES.keys())


# =====================================================================
# 1 & 2. production_history.csv / equipment_downtime_log.csv / blast_events.csv
# now live in scripts/synthetic_operations.py (Stage 1: downtime renewal
# process; Stage 2: causal production model). Imported above and called
# from main() below rather than duplicated here.
# =====================================================================


# =====================================================================
# 3. deposit_ground_truth.csv
# =====================================================================
def _zscore(a):
    a = np.asarray(a, dtype=float)
    sd = a.std()
    return (a - a.mean()) / sd if sd > 0 else np.zeros_like(a)


def _confirmation_probability(features: dict, noise: np.ndarray) -> np.ndarray:
    """P(is_confirmed_deposit) for each point, from a noisy logistic score
    over its z-scored features. `noise[:, k]` is the pre-added Gaussian noise
    for the k-th feature in LABEL_FEATURE_WEIGHTS order."""
    logit = np.zeros(len(noise))
    for k, (name, weight) in enumerate(LABEL_FEATURE_WEIGHTS.items()):
        logit += weight * (_zscore(features[name]) + noise[:, k])
    return 1.0 / (1.0 + np.exp(-logit))


def generate_deposit_ground_truth(n_total=40):
    # Everything below draws from this isolated stream, not synthetic_operations.py's RNGs.
    deposit_rng = np.random.default_rng(DEPOSIT_RNG_SEED)

    per_site = {"balaghat": 13, "nagpur": 13, "bhandara": 14}  # sums to 40

    # --- 1. draw locations FIRST; the label is conditioned on their features
    site_ids: list[str] = []
    lats: list[float] = []
    lons: list[float] = []
    depths: list[float] = []
    for site_id, n_points in per_site.items():
        lat_lo, lat_hi = SITES[site_id]["lat_range"]
        lon_lo, lon_hi = SITES[site_id]["lon_range"]
        for _ in range(n_points):
            lats.append(float(deposit_rng.uniform(lat_lo, lat_hi)))
            lons.append(float(deposit_rng.uniform(lon_lo, lon_hi)))
            depths.append(float(deposit_rng.uniform(20, 300)))  # depth: label-independent
            site_ids.append(site_id)

    lat_arr = np.array(lats)
    lon_arr = np.array(lons)

    # --- 2. compute the SAME 4 features generate_features.py will use, by
    #        reusing its own structural-line + random-field builders. Those
    #        have their own internal RNGs (seed 7 / 101 / 202), independent of
    #        deposit_rng, so this does not perturb the deposit draw sequence.
    lines_df = _gf.generate_structural_lines()
    ndvi_field, elevation_field = _gf.build_and_save_fields()

    min_dist_m, density = compute_structural_features(
        lon_arr, lat_arr, lines_df, density_radius_km=2.0
    )
    synthetic_ndvi = sample_field(ndvi_field, lon_arr, lat_arr) * 2 - 1
    synthetic_elevation = 300 + sample_field(elevation_field, lon_arr, lat_arr) * (650 - 300)

    features = {
        "dist_to_nearest_structure": np.asarray(min_dist_m, dtype=float),
        "structural_density": np.asarray(density, dtype=float),
        "synthetic_ndvi": np.asarray(synthetic_ndvi, dtype=float),
        "synthetic_elevation": np.asarray(synthetic_elevation, dtype=float),
    }

    # --- 3. feature-conditioned label: Bernoulli(p), p from the logistic rule.
    #        Class balance is NOT forced -- it falls out of the scores.
    noise = deposit_rng.normal(
        0.0, LABEL_ZSCORE_NOISE_SD, size=(len(site_ids), len(LABEL_FEATURE_WEIGHTS))
    )
    prob = _confirmation_probability(features, noise)
    is_confirmed = deposit_rng.random(len(site_ids)) < prob

    # --- 4. assemble rows; grade_percent still branches on the label, as before
    rows = []
    for i, site_id in enumerate(site_ids):
        confirmed = bool(is_confirmed[i])
        grade_percent = (
            deposit_rng.uniform(15, 45) if confirmed else deposit_rng.uniform(1, 14)
        )
        rows.append(
            {
                "deposit_id": f"dep_{i + 1:03d}",
                "site_id": site_id,
                "latitude": round(float(lat_arr[i]), 5),
                "longitude": round(float(lon_arr[i]), 5),
                "depth_m": round(float(depths[i]), 1),
                "grade_percent": round(float(grade_percent), 2),
                "is_confirmed_deposit": confirmed,
            }
        )

    df = pd.DataFrame(rows)
    path = os.path.join(OUT_DIR, "deposit_ground_truth.csv")
    df.to_csv(path, index=False)
    return df


# =====================================================================
# Main
# =====================================================================
def main():
    deposit_path = DATA_DIR / "deposit_ground_truth.csv"
    hash_before = sha256_of(deposit_path) if deposit_path.exists() else None

    downtime_df, overdue_ids = generate_equipment_downtime_log()
    downtime_df.to_csv(os.path.join(OUT_DIR, "equipment_downtime_log.csv"), index=False)

    prod_df, blast_df, diagnostics = generate_production_history()
    prod_df.to_csv(os.path.join(OUT_DIR, "production_history.csv"), index=False)
    blast_df.to_csv(os.path.join(OUT_DIR, "blast_events.csv"), index=False)

    deposit_df = generate_deposit_ground_truth()
    hash_after = sha256_of(deposit_path)

    print("=" * 70)
    print("MOIL Reserve Intelligence - synthetic dataset summary")
    print("=" * 70)

    print_downtime_summary(downtime_df, overdue_ids)
    print_production_summary(prod_df, blast_df, diagnostics)

    print("\n[deposit_ground_truth.csv]")
    print(f"  rows: {len(deposit_df)}")
    print(f"  points per site:\n{deposit_df['site_id'].value_counts().to_string()}")
    class_balance = deposit_df["is_confirmed_deposit"].value_counts(normalize=True)
    print(f"  class balance (is_confirmed_deposit):\n{class_balance.to_string()}")
    print(f"  sha256: {hash_after}")
    if hash_before is not None:
        print(f"  unchanged from before this run: {hash_before == hash_after}")

    print("\nAll CSVs written to:", OUT_DIR)
    print("=" * 70)


if __name__ == "__main__":
    main()
