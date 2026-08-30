"""
MOIL Reserve Intelligence (SIH26009) — Synthetic Dataset Generator
====================================================================
Generates three CSVs consistent with seed_graph.cypher's node IDs:

  1. production_history.csv     — 6 months of daily output per site
  2. equipment_downtime_log.csv — ~30-40 downtime events, matching
                                    Equipment IDs from the graph
  3. deposit_ground_truth.csv   — 40 labeled points for tomorrow's
                                    deposit classifier

Run:  python generate_datasets.py
Output: ./data/*.csv
"""

import os
import numpy as np
import pandas as pd

RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# Shared site config — kept consistent with seed_graph.cypher
# ---------------------------------------------------------------------
SITES = {
    "balaghat": {"target_output": 1200, "lat_range": (21.7, 22.0), "lon_range": (80.1, 80.4)},
    "nagpur":   {"target_output": 900,  "lat_range": (21.0, 21.3), "lon_range": (79.0, 79.3)},
    "bhandara": {"target_output": 700,  "lat_range": (21.1, 21.4), "lon_range": (79.5, 79.8)},
}
SITE_IDS = list(SITES.keys())

# Equipment IDs/types must match seed_graph.cypher exactly
EQUIPMENT = {
    "balaghat": [
        ("eq_bal_01", "Excavator"), ("eq_bal_02", "Drill"), ("eq_bal_03", "Conveyor"),
        ("eq_bal_04", "Loader"), ("eq_bal_05", "Compressor"),
    ],
    "nagpur": [
        ("eq_nag_01", "Excavator"), ("eq_nag_02", "Drill"), ("eq_nag_03", "Conveyor"),
        ("eq_nag_04", "Loader"), ("eq_nag_05", "Compressor"),
    ],
    "bhandara": [
        ("eq_bhd_01", "Excavator"), ("eq_bhd_02", "Drill"), ("eq_bhd_03", "Conveyor"),
        ("eq_bhd_04", "Loader"), ("eq_bhd_05", "Compressor"),
    ],
}

END_DATE = pd.Timestamp("2026-08-30")
START_DATE = END_DATE - pd.Timedelta(days=182)  # ~6 months, daily


# =====================================================================
# 1. production_history.csv
# =====================================================================
def generate_production_history():
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    rows = []

    for site_id in SITE_IDS:
        base_target = SITES[site_id]["target_output"]

        # Week-to-week variation in target: a slow random walk on a
        # per-week basis, smoothed back out to daily.
        n_weeks = int(np.ceil(len(dates) / 7)) + 1
        weekly_drift = rng.normal(0, 0.03, n_weeks).cumsum()
        weekly_drift = np.clip(weekly_drift, -0.12, 0.12)
        daily_drift = np.repeat(weekly_drift, 7)[: len(dates)]
        target_series = base_target * (1 + daily_drift)

        # Light seasonal dip during monsoon months (Jun-Sep)
        month = dates.month
        seasonal_factor = np.where(np.isin(month, [6, 7, 8, 9]), 0.90, 1.0)

        # Actual output tracks target with normal noise
        noise = rng.normal(0, 0.05, len(dates))
        actual_series = target_series * seasonal_factor * (1 + noise)

        # Inject 2-3 shortfall events (5-10 day windows), 20-40% below target
        n_events = rng.integers(2, 4)  # 2 or 3
        used_ranges = []  # list of (start_idx, end_idx) half-open intervals
        for _ in range(n_events):
            duration = int(rng.integers(5, 11))  # 5-10 days
            for _attempt in range(50):
                start_idx = int(rng.integers(0, len(dates) - duration))
                end_idx = start_idx + duration
                overlaps = any(start_idx < e and s < end_idx for s, e in used_ranges)
                if not overlaps:
                    used_ranges.append((start_idx, end_idx))
                    break
            else:
                continue
            drop_pct = rng.uniform(0.20, 0.40)
            actual_series[start_idx:end_idx] *= (1 - drop_pct)

        actual_series = np.clip(actual_series, a_min=0, a_max=None)

        for d, tgt, act in zip(dates, target_series, actual_series):
            rows.append(
                {
                    "site_id": site_id,
                    "date": d.strftime("%Y-%m-%d"),
                    "actual_output": round(float(act), 1),
                    "target_output": round(float(tgt), 1),
                }
            )

    df = pd.DataFrame(rows)
    path = os.path.join(OUT_DIR, "production_history.csv")
    df.to_csv(path, index=False)
    return df


# =====================================================================
# 2. equipment_downtime_log.csv
# =====================================================================
DOWNTIME_REASONS = [
    "scheduled maintenance",
    "mechanical failure",
    "weather delay",
    "electrical fault",
    "spare parts unavailable",
    "operator shift gap",
    "hydraulic leak",
]


def generate_equipment_downtime_log(n_events=36):
    all_equipment = [
        (eq_id, eq_type, site_id)
        for site_id, items in EQUIPMENT.items()
        for eq_id, eq_type in items
    ]

    rows = []
    span_days = (END_DATE - START_DATE).days

    for _ in range(n_events):
        eq_id, eq_type, site_id = all_equipment[rng.integers(0, len(all_equipment))]
        start_offset = rng.integers(0, span_days - 1)
        down_start = START_DATE + pd.Timedelta(days=int(start_offset))
        down_start += pd.Timedelta(hours=int(rng.integers(0, 24)))

        reason = DOWNTIME_REASONS[rng.integers(0, len(DOWNTIME_REASONS))]
        if reason == "scheduled maintenance":
            duration_hours = rng.uniform(2, 8)
        elif reason == "weather delay":
            duration_hours = rng.uniform(6, 48)
        else:
            duration_hours = rng.uniform(1, 24)

        down_end = down_start + pd.Timedelta(hours=float(duration_hours))

        rows.append(
            {
                "equipment_id": eq_id,
                "site_id": site_id,
                "down_start": down_start.strftime("%Y-%m-%d %H:%M:%S"),
                "down_end": down_end.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_hours": round(float(duration_hours), 2),
                "reason": reason,
            }
        )

    df = pd.DataFrame(rows).sort_values("down_start").reset_index(drop=True)
    path = os.path.join(OUT_DIR, "equipment_downtime_log.csv")
    df.to_csv(path, index=False)
    return df


# =====================================================================
# 3. deposit_ground_truth.csv
# =====================================================================
def generate_deposit_ground_truth(n_total=40):
    per_site = {"balaghat": 13, "nagpur": 13, "bhandara": 14}  # sums to 40
    rows = []
    deposit_counter = 1

    for site_id, n_points in per_site.items():
        lat_lo, lat_hi = SITES[site_id]["lat_range"]
        lon_lo, lon_hi = SITES[site_id]["lon_range"]

        n_confirmed = int(round(n_points * 0.6))
        n_negative = n_points - n_confirmed
        labels = [True] * n_confirmed + [False] * n_negative
        rng.shuffle(labels)

        for is_confirmed in labels:
            lat = rng.uniform(lat_lo, lat_hi)
            lon = rng.uniform(lon_lo, lon_hi)
            depth_m = rng.uniform(20, 300)

            if is_confirmed:
                grade_percent = rng.uniform(15, 45)
            else:
                grade_percent = rng.uniform(1, 14)

            rows.append(
                {
                    "deposit_id": f"dep_{deposit_counter:03d}",
                    "site_id": site_id,
                    "latitude": round(float(lat), 5),
                    "longitude": round(float(lon), 5),
                    "depth_m": round(float(depth_m), 1),
                    "grade_percent": round(float(grade_percent), 2),
                    "is_confirmed_deposit": bool(is_confirmed),
                }
            )
            deposit_counter += 1

    df = pd.DataFrame(rows)
    path = os.path.join(OUT_DIR, "deposit_ground_truth.csv")
    df.to_csv(path, index=False)
    return df


# =====================================================================
# Main
# =====================================================================
def main():
    prod_df = generate_production_history()
    downtime_df = generate_equipment_downtime_log()
    deposit_df = generate_deposit_ground_truth()

    print("=" * 70)
    print("MOIL Reserve Intelligence - synthetic dataset summary")
    print("=" * 70)

    print("\n[production_history.csv]")
    print(f"  rows: {len(prod_df)}")
    print(f"  date range: {prod_df['date'].min()} -> {prod_df['date'].max()}")
    print(f"  sites: {sorted(prod_df['site_id'].unique().tolist())}")
    print("  avg actual/target ratio by site:")
    ratio = prod_df.groupby("site_id")[["actual_output", "target_output"]].apply(
        lambda g: (g["actual_output"] / g["target_output"]).mean()
    )
    for site_id, val in ratio.items():
        print(f"    {site_id}: {val:.2%}")

    print("\n[equipment_downtime_log.csv]")
    print(f"  rows: {len(downtime_df)}")
    print(f"  date range: {downtime_df['down_start'].min()} -> {downtime_df['down_start'].max()}")
    print(f"  events per site:\n{downtime_df['site_id'].value_counts().to_string()}")
    print(f"  reason counts:\n{downtime_df['reason'].value_counts().to_string()}")

    print("\n[deposit_ground_truth.csv]")
    print(f"  rows: {len(deposit_df)}")
    print(f"  points per site:\n{deposit_df['site_id'].value_counts().to_string()}")
    class_balance = deposit_df["is_confirmed_deposit"].value_counts(normalize=True)
    print(f"  class balance (is_confirmed_deposit):\n{class_balance.to_string()}")

    print("\nAll CSVs written to:", OUT_DIR)
    print("=" * 70)


if __name__ == "__main__":
    main()
