"""
MOIL Reserve Intelligence (SIH26009) — Part 5: Shortfall Forecaster
feature engineering (WORK IN PROGRESS — no model trained here)
====================================================================
Loads data/production_history.csv and data/equipment_downtime_log.csv
(Day 1) and engineers per site-day features for tomorrow's shortfall
forecaster:
  - rolling_7day_downtime_pct
  - days_since_last_maintenance
  - rainfall_proxy (smooth seasonal proxy, monsoon-weighted)
  - shortfall_pct (target)

Saves data/shortfall_features_wip.csv. Model training is deliberately
NOT done here — that's Day 3.

Run: python shortfall_features_wip.py
"""

import os

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# All 3 sites have 5 pieces of equipment each (Day 1 seed_graph.cypher).
EQUIPMENT_COUNT_PER_SITE = 5
ROLLING_WINDOW_DAYS = 7


def load_inputs():
    production = pd.read_csv(os.path.join(DATA_DIR, "production_history.csv"), parse_dates=["date"])
    downtime = pd.read_csv(
        os.path.join(DATA_DIR, "equipment_downtime_log.csv"),
        parse_dates=["down_start", "down_end"],
    )
    return production, downtime


def add_shortfall_pct(production):
    production = production.sort_values(["site_id", "date"]).reset_index(drop=True)
    production["shortfall_pct"] = (
        (production["target_output"] - production["actual_output"]) / production["target_output"]
    )
    return production


def add_rolling_downtime_pct(production, downtime):
    downtime = downtime.copy()
    downtime["down_date"] = downtime["down_start"].dt.normalize()

    daily_hours = downtime.groupby(["site_id", "down_date"])["duration_hours"].sum()

    frames = []
    for site_id, site_df in production.groupby("site_id"):
        date_index = pd.date_range(site_df["date"].min(), site_df["date"].max(), freq="D")
        site_daily_hours = daily_hours.get(site_id, pd.Series(dtype=float)).reindex(date_index, fill_value=0.0)

        # Trailing 7-day sum of downtime hours / hours available in a
        # 7-day window across all equipment at the site. min_periods=1
        # means the first few days of the series use a shorter window
        # while the denominator still assumes a full 7 days — a small,
        # acceptable edge effect for feature-prep purposes.
        rolling_hours = site_daily_hours.rolling(ROLLING_WINDOW_DAYS, min_periods=1).sum()
        available_hours = EQUIPMENT_COUNT_PER_SITE * ROLLING_WINDOW_DAYS * 24
        rolling_pct = (rolling_hours / available_hours).clip(0, 1)

        site_out = site_df.copy()
        site_out["rolling_7day_downtime_pct"] = site_out["date"].map(rolling_pct)
        frames.append(site_out)

    return pd.concat(frames, ignore_index=True)


def add_days_since_last_maintenance(production, downtime):
    maintenance = downtime[downtime["reason"] == "scheduled maintenance"].copy()
    maintenance["maint_date"] = maintenance["down_start"].dt.normalize()
    maintenance = maintenance.sort_values(["site_id", "maint_date"])[["site_id", "maint_date"]]

    frames = []
    for site_id, site_df in production.groupby("site_id"):
        site_df = site_df.sort_values("date")
        site_maint = maintenance[maintenance["site_id"] == site_id].drop_duplicates("maint_date")

        if site_maint.empty:
            site_df = site_df.copy()
            site_df["days_since_last_maintenance"] = np.nan
        else:
            merged = pd.merge_asof(
                site_df, site_maint.rename(columns={"maint_date": "last_maintenance"}),
                left_on="date", right_on="last_maintenance",
                direction="backward",
            )
            merged["days_since_last_maintenance"] = (merged["date"] - merged["last_maintenance"]).dt.days
            merged = merged.drop(columns=["last_maintenance", "site_id_y"], errors="ignore")
            merged = merged.rename(columns={"site_id_x": "site_id"}) if "site_id_x" in merged.columns else merged
            site_df = merged

        frames.append(site_df)

    return pd.concat(frames, ignore_index=True)


def add_rainfall_proxy(production):
    # Smooth seasonal proxy in [0, 1], peaking ~August (fractional
    # month 7.5) and troughing ~mid-January - mirrors the monsoon
    # dip (Jun-Sep) already baked into production_history.csv's
    # actual_output generation logic (see generate_datasets.py).
    days_in_month = production["date"].dt.days_in_month
    fractional_month = production["date"].dt.month + (production["date"].dt.day - 1) / days_in_month
    proxy = 0.5 * (1 + np.cos(2 * np.pi * (fractional_month - 7.5) / 12))
    production = production.copy()
    production["rainfall_proxy"] = proxy.round(4)
    return production


def main():
    print("=" * 70)
    print("Part 5: Shortfall Forecaster feature engineering (WIP)")
    print("=" * 70)

    production, downtime = load_inputs()
    print(f"\nLoaded production_history.csv: {len(production)} rows")
    print(f"Loaded equipment_downtime_log.csv: {len(downtime)} rows")

    production = add_shortfall_pct(production)
    production = add_rolling_downtime_pct(production, downtime)
    production = add_days_since_last_maintenance(production, downtime)
    production = add_rainfall_proxy(production)

    out_cols = [
        "site_id", "date", "target_output", "actual_output", "shortfall_pct",
        "rolling_7day_downtime_pct", "days_since_last_maintenance", "rainfall_proxy",
    ]
    result = production[out_cols].sort_values(["site_id", "date"]).reset_index(drop=True)

    out_path = os.path.join(DATA_DIR, "shortfall_features_wip.csv")
    result.to_csv(out_path, index=False)

    print(f"\n[shortfall_features_wip.csv] {len(result)} rows written to {out_path}")
    print(f"Date range: {result['date'].min().date()} -> {result['date'].max().date()}")
    print("\nFeature summary:")
    print(
        result[["shortfall_pct", "rolling_7day_downtime_pct", "days_since_last_maintenance", "rainfall_proxy"]]
        .describe().round(3).to_string()
    )
    n_missing_maint = result["days_since_last_maintenance"].isna().sum()
    print(f"\nRows with no prior maintenance event yet (NaN days_since_last_maintenance): {n_missing_maint}")
    print("\nNo model trained in this script (Day 3 task). Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
