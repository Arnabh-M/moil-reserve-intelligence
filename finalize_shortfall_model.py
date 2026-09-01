"""
MOIL Reserve Intelligence (SIH26009) — Shortfall Forecaster, finalized
=======================================================================
Supersedes train_shortfall_model.py for the final ML/agent-layer pass.
The feature engineering, model, and split strategy are UNCHANGED from that
script (they were already correct — see its own module docstring for the
full feature-by-feature rationale) — this run exists to (a) produce a
fresh, dated set of real measured numbers for methodology.md rather than
reuse Day 3's saved artifact uncritically, and (b) make an explicit,
reasoned call on whether the fit is good enough for a demo instead of
silently shipping whatever comes out.

Features:
  - rolling_7day_downtime_pct, days_since_last_maintenance, rainfall_proxy,
    schedule_pressure, dow_sin/cos, month_sin/cos — see
    train_shortfall_model.py's docstring for how each is derived.

Target: shortfall_pct = (target_output - actual_output) / target_output

Run: python finalize_shortfall_model.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "oresight-backend", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

EQUIPMENT_COUNT_PER_SITE = 5
ROLLING_DOWNTIME_WINDOW_DAYS = 7
SCHEDULE_PRESSURE_WINDOW_DAYS = 14
TEST_FRACTION = 0.2

FEATURE_COLUMNS = [
    "rolling_7day_downtime_pct",
    "days_since_last_maintenance",
    "rainfall_proxy",
    "schedule_pressure",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
]
TARGET_COLUMN = "shortfall_pct"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    production = pd.read_csv(os.path.join(DATA_DIR, "production_history.csv"), parse_dates=["date"])
    downtime = pd.read_csv(
        os.path.join(DATA_DIR, "equipment_downtime_log.csv"),
        parse_dates=["down_start", "down_end"],
    )
    return production, downtime


def add_shortfall_pct(production: pd.DataFrame) -> pd.DataFrame:
    production = production.sort_values(["site_id", "date"]).reset_index(drop=True)
    production[TARGET_COLUMN] = (
        (production["target_output"] - production["actual_output"]) / production["target_output"]
    )
    return production


def add_rolling_downtime_pct(production: pd.DataFrame, downtime: pd.DataFrame) -> pd.DataFrame:
    downtime = downtime.copy()
    downtime["down_date"] = downtime["down_start"].dt.normalize()
    daily_hours = downtime.groupby(["site_id", "down_date"])["duration_hours"].sum()

    frames = []
    for site_id, site_df in production.groupby("site_id"):
        date_index = pd.date_range(site_df["date"].min(), site_df["date"].max(), freq="D")
        site_daily_hours = daily_hours.get(site_id, pd.Series(dtype=float)).reindex(date_index, fill_value=0.0)

        rolling_hours = site_daily_hours.rolling(ROLLING_DOWNTIME_WINDOW_DAYS, min_periods=1).sum()
        available_hours = EQUIPMENT_COUNT_PER_SITE * ROLLING_DOWNTIME_WINDOW_DAYS * 24
        rolling_pct = (rolling_hours / available_hours).clip(0, 1)

        site_out = site_df.copy()
        site_out["rolling_7day_downtime_pct"] = site_out["date"].map(rolling_pct)
        frames.append(site_out)

    return pd.concat(frames, ignore_index=True)


def add_days_since_last_maintenance(production: pd.DataFrame, downtime: pd.DataFrame) -> pd.DataFrame:
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


def add_rainfall_proxy(production: pd.DataFrame) -> pd.DataFrame:
    days_in_month = production["date"].dt.days_in_month
    fractional_month = production["date"].dt.month + (production["date"].dt.day - 1) / days_in_month
    proxy = 0.5 * (1 + np.cos(2 * np.pi * (fractional_month - 7.5) / 12))
    production = production.copy()
    production["rainfall_proxy"] = proxy.round(4)
    return production


def add_schedule_pressure(production: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for site_id, site_df in production.groupby("site_id"):
        site_df = site_df.sort_values("date").copy()
        pressure = (
            site_df[TARGET_COLUMN]
            .shift(1)
            .rolling(SCHEDULE_PRESSURE_WINDOW_DAYS, min_periods=1)
            .mean()
            .clip(lower=0, upper=1)
        )
        site_df["schedule_pressure"] = pressure
        frames.append(site_df)
    return pd.concat(frames, ignore_index=True)


def add_seasonality(production: pd.DataFrame) -> pd.DataFrame:
    production = production.copy()
    dow = production["date"].dt.dayofweek
    month = production["date"].dt.month
    production["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    production["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    production["month_sin"] = np.sin(2 * np.pi * month / 12)
    production["month_cos"] = np.cos(2 * np.pi * month / 12)
    return production


def time_based_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.sort(df["date"].unique())
    cutoff_idx = int(len(dates) * (1 - TEST_FRACTION))
    cutoff_date = dates[cutoff_idx]
    train = df[df["date"] < cutoff_date]
    test = df[df["date"] >= cutoff_date]
    return train, test


def main() -> None:
    print("=" * 70)
    print("Finalize Shortfall Forecaster")
    print("=" * 70)

    production, downtime = load_inputs()
    print(f"\nLoaded production_history.csv: {len(production)} rows")
    print(f"Loaded equipment_downtime_log.csv: {len(downtime)} rows")

    df = add_shortfall_pct(production)
    df = add_rolling_downtime_pct(df, downtime)
    df = add_days_since_last_maintenance(df, downtime)
    df = add_rainfall_proxy(df)
    df = add_schedule_pressure(df)
    df = add_seasonality(df)

    train_df, test_df = time_based_split(df)
    print(f"\nTime-based split: train={len(train_df)} rows (up to {train_df['date'].max().date()}), "
          f"test={len(test_df)} rows (from {test_df['date'].min().date()} to {test_df['date'].max().date()})")

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COLUMN]

    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae = float(mean_absolute_error(y_test, preds))
    target_mean = float(y_test.mean())
    target_std = float(y_test.std())

    print(f"\nTest RMSE: {rmse:.4f}")
    print(f"Test MAE:  {mae:.4f}")
    print(f"(target shortfall_pct test-set mean={target_mean:.4f}, std={target_std:.4f})")

    print("\nFeature importances:")
    importances = sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda t: -t[1])
    for feat, imp in importances:
        print(f"  {feat}: {imp:.3f}")

    # --- explicit, reasoned judgment on fit quality, not a silent pass ------
    print("\n" + "-" * 70)
    print("Fit-quality judgment (not a fixed threshold — reasoned from the data):")
    rmse_to_std = rmse / target_std if target_std else float("inf")
    if rmse_to_std >= 0.9:
        verdict = (
            f"UNRELIABLE for demo purposes: RMSE ({rmse:.4f}) is {rmse_to_std:.2f}x the "
            f"test-set target's own std dev ({target_std:.4f}) — the model is barely better "
            "than predicting the mean shortfall_pct for every day. Don't lean on absolute "
            "before/after numbers in a live demo; the RELATIVE direction (worse when a "
            "scenario is simulated) is more defensible than the magnitude."
        )
    elif rmse_to_std >= 0.6:
        verdict = (
            f"MARGINAL: RMSE ({rmse:.4f}) is {rmse_to_std:.2f}x the target std dev "
            f"({target_std:.4f}) — meaningfully better than the mean but the error band is "
            "wide relative to the signal. Fine for a demo narrative (directionally correct, "
            "plausible magnitudes) but don't quote these numbers as validated forecasts."
        )
    else:
        verdict = (
            f"ACCEPTABLE for demo purposes: RMSE ({rmse:.4f}) is {rmse_to_std:.2f}x the "
            f"target std dev ({target_std:.4f}), a real reduction in error versus a "
            "mean-only baseline."
        )
    print(verdict)
    top_feat, top_imp = importances[0]
    if top_imp > 0.6:
        print(
            f"\nNote: '{top_feat}' alone accounts for {top_imp:.0%} of feature importance — "
            "the model is substantially a seasonality/rainfall proxy. See "
            "train_shortfall_model.py's KNOWN LIMITATION note for why "
            "schedule_pressure/rolling_7day_downtime_pct carry weak or counter-intuitive "
            "learned effects on this synthetic dataset (isolated shortfall-injection windows, "
            "no autocorrelated backlog dynamics)."
        )
    print("-" * 70)

    model_path = os.path.join(MODELS_DIR, "shortfall_forecaster.pkl")
    columns_path = os.path.join(MODELS_DIR, "feature_columns.json")
    joblib.dump(model, model_path)
    with open(columns_path, "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)

    print(f"\nSaved model to {model_path}")
    print(f"Saved feature column order to {columns_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
