"""
MOIL Reserve Intelligence (SIH26009) — Day 3 Part 0: Shortfall Forecaster
====================================================================
Finishes what shortfall_features_wip.py started: engineers the full
feature set from data/production_history.csv and
data/equipment_downtime_log.csv, trains an XGBoost regressor on a
time-based (not random) split, and saves the model + its exact
feature column order for the Simulator agent to reuse.

Features:
  - rolling_7day_downtime_pct : trailing 7-day equipment downtime %
  - days_since_last_maintenance : days since the site's last
    scheduled-maintenance event (NaN before the first one; XGBoost
    handles missing values natively, so this is left as NaN rather
    than filled with an arbitrary sentinel)
  - rainfall_proxy : smooth monsoon-weighted seasonal proxy in [0, 1]
  - schedule_pressure : trailing 14-day mean shortfall_pct (shifted by
    1 day so the current day's own actual/target never leak into its
    own feature), representing production backlog/schedule strain.
    This is what the Simulator agent's 'delay_blasting' scenario
    pushes up — there's no real blast-plan delay signal in this
    synthetic CSV data, so this is a principled proxy grounded in the
    site's own recent shortfall history, not an arbitrary constant.
  - dow_sin/cos, month_sin/cos : cyclical day-of-week / month encoding

Target: shortfall_pct = (target_output - actual_output) / target_output

KNOWN LIMITATION (confirmed by directly probing the trained model from
app/agents/simulator.py, not just eyeballing feature_importances_):
rolling_7day_downtime_pct saturates almost immediately — forcing it to its
theoretical max (1.0) barely moves the prediction versus a realistic small
value, because 6 months of synthetic downtime data has very few severe
events for the trees to split on. schedule_pressure is worse: it has a
*negative* learned relationship with shortfall_pct, the opposite of the
intended "backlog begets more shortfall" story — most likely because the
synthetic shortfall-injection windows in generate_datasets.py are isolated
5-10 day events with no real autocorrelated backlog dynamics, so periods
of elevated recent-shortfall (high schedule_pressure) are statistically
followed by mean-reversion back to normal, not more shortfall. rainfall_
proxy/seasonality behaves correctly and dominates, since that IS a real,
strong signal baked into generate_datasets.py. Net effect: the Simulator's
'equipment_down' and 'delay_blasting' scenarios currently show weak or
counter-intuitive before/after deltas; 'rainfall_event' behaves as
expected. This is an honest property of training on 6 months of synthetic
data shaped this way, not a bug in the Watcher/Simulator/Planner agents
built on top of it — worth a feature-engineering revisit (or real
blast-plan/downtime history) before leaning on it for a demo.

Run: python train_shortfall_model.py
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

EQUIPMENT_COUNT_PER_SITE = 5  # Day 1 seed_graph.cypher: 5 equipment per site
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
        # shift(1) excludes the current day's own shortfall from its own feature
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
    print("Day 3 Part 0: Train Shortfall Forecaster")
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

    print(f"\nTest RMSE: {rmse:.4f}")
    print(f"Test MAE:  {mae:.4f}")
    print(f"(target shortfall_pct test-set mean={y_test.mean():.4f}, std={y_test.std():.4f})")

    print("\nFeature importances:")
    for feat, imp in sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda t: -t[1]):
        print(f"  {feat}: {imp:.3f}")

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
