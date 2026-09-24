"""
MOIL Reserve Intelligence (SIH26009) — Shortfall Forecaster (Stage 3 retrain)
====================================================================
Trains an XGBoost regressor of shortfall_pct = (target - actual) / target on the
causal synthetic data from scripts/synthetic_operations.py, and answers one
question honestly: does it beat BOTH naive baselines? This script reports the
answer; it does not tune toward one.

Features and the look-ahead guard live in shortfall_feature_engineering.py
(read its docstring for the per-feature definitions and the judgement calls).

PERFECT-FORECAST CAVEAT (also written into model_metrics.json)
  rain_today_mm is day t's OBSERVED rain, i.e. the model is given a perfect
  same-day forecast. It is the one feature exempt from the look-ahead rule. The
  accuracy reported here is therefore an OPTIMISTIC CEILING relative to live use,
  where the same feature would come from a real, noisy forecast. Note also that
  in the synthetic world today's rain has no direct causal effect (loss uses
  rain lags 1 and 2), so rain_today_mm can only help via rain autocorrelation.

EVALUATION DESIGN — fixed BEFORE any result was seen
  Data     first WARMUP_DAYS (14) of each site are dropped (backlog starts at 0,
           rolling windows need history). Pooled model, no site identifier.
  Holdout  time-ordered, last 20% of dates, all sites split at the same date.
  Rolling  3 expanding windows: train on dates before the 55% / 70% / 85% mark of
  origin  the date range, test on the following 15% of dates each.
  Model    XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
           subsample=0.8, colsample_bytree=0.8, random_state=42) — identical to
           the previous model. One run. No tuning, no feature changes after
           seeing results, no re-splitting.
  Baseline (a) predict-the-train-mean (pooled mean of the training rows);
           (b) persistence: yesterday's shortfall for that site.
           Informational extra: per-site train mean.
  Metrics  RMSE and MAE for model and baselines on the identical rows, pooled and
           per site; R^2 (vs the test slice's own mean) and R^2 gain over
           persistence; test-target std dev alongside.
  SHIP GATE (primary criterion, RMSE on the holdout): the model must beat BOTH
           baselines pooled AND on each of the three sites. Artifacts always go to
           models/candidate/; the shipped model/feature_columns.json/
           model_metrics.json are only overwritten when the gate passed AND
           --ship is given (the simulator must be updated in the same change, or
           its feature dict no longer matches the model). MAE and the
           rolling-origin windows are reported; any disagreement with the RMSE
           verdict is flagged rather than gated.

KNOWN LIMITATION (recorded in model_metrics.json; not something this script tries to remove)
  The model's edge over persistence is largest in monsoon periods and can fall
  below persistence in dry windows at high-downtime sites (observed: Bhandara in
  the 2026-03-22..2026-06-21 rolling-origin window). The rolling-origin windows are
  a stability check, not the gate.

PARTIAL-DEPENDENCE GRADING against the known generator constants
  For rain, downtime, backlog and blast-delay the model's learned response is
  compared with the ground truth in scripts/synthetic_operations.py. Backlog
  verdict thresholds, fixed in advance (truth = BACKLOG_LOSS_COEF = 0.02):
    RECOVERED             PD slope positive and within [0.5x, 2x] of truth
    DETECTED, MIS-SIZED   PD slope positive, >= 0.25x truth, outside that range
    NOT RECOVERED         PD slope < 0.25x truth, or negative
  ("too weak to learn" is an acceptable answer and is reported, not fixed.)

XGBOOST VERSION MATTERS. Train with the SAME interpreter the backend runs
(oresight-backend/venv). A pickle written by a newer xgboost and loaded by an
older one does not raise: it silently mispredicts (observed: max abs prediction
difference 0.37 between xgboost 3.4.1 and 2.1.4). The reverse direction (older
pickle, newer xgboost) is fine. Fitting XGBRegressor needs scikit-learn, which comes from
oresight-backend/requirements-train.txt (installed into that same venv); the API itself
never imports it. A retrain under that venv reproduces the shipped pickle byte for byte.

Run: oresight-backend/venv/Scripts/python train_shortfall_model.py           # evaluate, write models/candidate/
     oresight-backend/venv/Scripts/python train_shortfall_model.py --ship    # also install over the shipped artifacts (only if gate passed)
"""

import json
import os
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBRegressor

import shortfall_feature_engineering as fe
from shortfall_feature_engineering import FEATURE_COLUMNS, TARGET_COLUMN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "oresight-backend", "models")
CANDIDATE_DIR = os.path.join(MODELS_DIR, "candidate")

TEST_FRACTION = 0.2
ROLLING_ORIGIN_STARTS = (0.55, 0.70, 0.85)
ROLLING_ORIGIN_TEST_FRACTION = 0.15
MODEL_PARAMS = dict(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42,
)

# PD verdict thresholds (fixed in advance; see module docstring)
RAINY_WINDOW_MM = 2.5  # IMD "rainy day" threshold, applied to a 3-day total for the Simulator's severity levels
BACKLOG_RECOVERED_BAND = (0.5, 2.0)
BACKLOG_DETECTED_FLOOR = 0.25
PD_DECREASE_TOLERANCE = 0.0005  # a PD step down by more than this counts as a monotonicity violation
SITES = ("balaghat", "nagpur", "bhandara")


REQUIREMENTS_TXT = os.path.join(BASE_DIR, "oresight-backend", "requirements.txt")


def required_xgboost_version() -> str:
    """The exact xgboost the backend pins (oresight-backend/requirements.txt)."""
    with open(REQUIREMENTS_TXT, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*xgboost(?:-cpu)?==([0-9][0-9.]*)", line)
            if m:
                return m.group(1)
    raise SystemExit(f"{REQUIREMENTS_TXT} has no exact 'xgboost==X.Y.Z' / 'xgboost-cpu==X.Y.Z' pin")


def enforce_pinned_xgboost() -> None:
    """Refuse to train under any xgboost but the backend's pin: a model pickled
    by a newer xgboost silently mispredicts (0.37 max error measured) when the
    API loads it under the pinned one."""
    required = required_xgboost_version()
    if xgboost.__version__ != required:
        raise SystemExit(
            f"Refusing to train: this interpreter has xgboost {xgboost.__version__} but the backend pins "
            f"{required}. Train with the backend venv (pip install -r oresight-backend/requirements-train.txt, "
            f"then oresight-backend/venv/Scripts/python train_shortfall_model.py)."
        )


def make_model() -> XGBRegressor:
    return XGBRegressor(**MODEL_PARAMS)


# ---------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------
def time_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.sort(df["date"].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    return df[df["date"] < cutoff], df[df["date"] >= cutoff]


def rolling_origin_splits(df: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    dates = np.sort(df["date"].unique())
    n = len(dates)
    splits = []
    for start_frac in ROLLING_ORIGIN_STARTS:
        lo = dates[int(n * start_frac)]
        hi_idx = int(n * (start_frac + ROLLING_ORIGIN_TEST_FRACTION))
        train = df[df["date"] < lo]
        test = df[(df["date"] >= lo) & ((df["date"] < dates[hi_idx]) if hi_idx < n else True)]
        splits.append((train, test))
    return splits


# ---------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------
def _scores(y: np.ndarray, pred: np.ndarray) -> dict:
    sse = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    return {
        "rmse": float(np.sqrt(np.mean((y - pred) ** 2))),
        "mae": float(np.mean(np.abs(y - pred))),
        "r2": 1.0 - sse / sst if sst > 0 else float("nan"),
    }


def evaluate_split(train: pd.DataFrame, test: pd.DataFrame, features: list[str] | None = None) -> dict:
    """Fit on `train`, score model + baselines on `test`, pooled and per site."""
    features = features or FEATURE_COLUMNS
    model = make_model()
    model.fit(train[features], train[TARGET_COLUMN])
    test = test.copy()
    test["pred_model"] = model.predict(test[features])
    test["pred_mean"] = float(train[TARGET_COLUMN].mean())
    test["pred_persistence"] = test["prev_shortfall"]
    test["pred_site_mean"] = test["site_id"].map(train.groupby("site_id")[TARGET_COLUMN].mean())
    assert test["pred_persistence"].notna().all(), "persistence baseline has NaN rows after warm-up"

    slices = {"pooled": test}
    slices.update({s: test[test["site_id"] == s] for s in SITES})
    table = {}
    for name, sl in slices.items():
        y = sl[TARGET_COLUMN].to_numpy()
        entry = {
            "n": int(len(sl)),
            "target_mean": float(y.mean()),
            "target_std": float(y.std(ddof=1)),
            "model": _scores(y, sl["pred_model"].to_numpy()),
            "train_mean": _scores(y, sl["pred_mean"].to_numpy()),
            "persistence": _scores(y, sl["pred_persistence"].to_numpy()),
            "site_train_mean": _scores(y, sl["pred_site_mean"].to_numpy()),
        }
        entry["r2_gain_over_persistence"] = entry["model"]["r2"] - entry["persistence"]["r2"]
        table[name] = entry
    return {"model": model, "test": test, "table": table}


def beats_both(entry: dict, metric: str = "rmse") -> bool:
    return (
        entry["model"][metric] < entry["train_mean"][metric]
        and entry["model"][metric] < entry["persistence"][metric]
    )


def print_table(title: str, table: dict) -> None:
    print(f"\n{title}")
    header = f"  {'slice':<9}{'n':>5}{'y_std':>8} | {'model':>15} | {'train-mean':>15} | {'persistence':>15} | {'site-mean(info)':>15} | {'R2 gain vs pers':>15}"
    print(header)
    print(f"  {'':<9}{'':>5}{'':>8} | {'RMSE   MAE':>15} | {'RMSE   MAE':>15} | {'RMSE   MAE':>15} | {'RMSE   MAE':>15} |")
    for name, e in table.items():
        def cell(k):
            return f"{e[k]['rmse']:.4f} {e[k]['mae']:.4f}"
        print(
            f"  {name:<9}{e['n']:>5}{e['target_std']:>8.4f} | {cell('model'):>15} | {cell('train_mean'):>15} | "
            f"{cell('persistence'):>15} | {cell('site_train_mean'):>15} | {e['r2_gain_over_persistence']:>+15.4f}"
        )
    print("  R2 (model / train-mean / persistence): " + "; ".join(
        f"{n}: {e['model']['r2']:.3f} / {e['train_mean']['r2']:.3f} / {e['persistence']['r2']:.3f}"
        for n, e in table.items()
    ))


# ---------------------------------------------------------------------
# Partial dependence, graded against the generator's true constants
# ---------------------------------------------------------------------
def partial_dependence(model, x_ref: pd.DataFrame, feature: str, grid: np.ndarray) -> np.ndarray:
    out = np.empty(len(grid))
    for i, v in enumerate(grid):
        x = x_ref.copy()
        x[feature] = v
        out[i] = float(np.mean(model.predict(x)))
    return out


def _grid(values: pd.Series, n: int = 19) -> np.ndarray:
    g = np.unique(np.quantile(values.dropna(), np.linspace(0.05, 0.95, n)))
    return g


def pd_summary(model, x_ref: pd.DataFrame, feature: str) -> dict:
    vals = x_ref[feature]
    grid = np.array([0.0, 1.0]) if vals.dropna().nunique() <= 2 else _grid(vals)
    curve = partial_dependence(model, x_ref, feature, grid)
    diffs = np.diff(curve)
    slope = float(np.polyfit(grid, curve, 1)[0]) if len(grid) > 1 else float("nan")
    rank_corr = float(pd.Series(curve).corr(pd.Series(grid), method="spearman")) if len(grid) > 2 else float("nan")
    return {
        "grid": grid.tolist(),
        "pd": curve.tolist(),
        "slope": slope,
        "range": float(curve.max() - curve.min()),
        "net_rise": float(curve[-1] - curve[0]),
        "n_decreases": int((diffs < -PD_DECREASE_TOLERANCE).sum()),
        "max_drop": float(-diffs.min()) if (diffs < 0).any() else 0.0,
        "spearman": rank_corr,
    }


def _ols_slope(x: pd.Series, y: pd.Series) -> float:
    m = x.notna() & y.notna()
    return float(np.polyfit(x[m], y[m], 1)[0])


def grade_against_truth(model, frame: pd.DataFrame, oos: pd.DataFrame) -> dict:
    """`frame`: all retained rows (PD reference set). `oos`: out-of-sample
    predictions pooled across the rolling-origin windows (for calibration)."""
    gen = fe.load_generator_module()
    BACKLOG_LOSS_COEF = gen.BACKLOG_LOSS_COEF
    BLAST_DELAY_EFFECT_LOSS = gen.BLAST_DELAY_EFFECT_LOSS
    DOWNTIME_LOSS_WEIGHTS_BY_TYPE = gen.DOWNTIME_LOSS_WEIGHTS_BY_TYPE
    RAIN_LAG1_COEF = gen.RAIN_LAG1_COEF
    RAIN_LAG2_COEF = gen.RAIN_LAG2_COEF
    EQUIPMENT_SITE_BY_ID = gen.EQUIPMENT_SITE_BY_ID
    EQUIPMENT_TYPE_BY_ID = gen.EQUIPMENT_TYPE_BY_ID

    x_ref = frame[FEATURE_COLUMNS]
    res: dict = {"pd": {f: pd_summary(model, x_ref, f) for f in [
        "rain_today_mm", "rain_3d_mm", "rain_7d_mm", "heavy_rain_lag1",
        "rolling_7d_downtime_pct", "equipment_down_today_pct",
        "backlog_t", "blast_delay_days_lag", "days_since_last_maintenance", "soil_moisture_m3m3",
    ]}}

    # ---- rain ------------------------------------------------------------
    rain = {"structural_lag1_coef": RAIN_LAG1_COEF, "structural_lag2_coef": RAIN_LAG2_COEF}
    rain["empirical_slope_true_loss_rain_vs_rain_3d"] = _ols_slope(frame["rain_3d_mm"], frame["true_loss_rain"])
    heavy = frame["heavy_rain_lag1"] == 1.0
    rain["empirical_step_true_loss_rain_heavy_lag1"] = float(
        frame.loc[heavy, "true_loss_rain"].mean() - frame.loc[~heavy, "true_loss_rain"].mean()
    )
    edges = [-np.inf, 0.5, 5, 15, 30, 50, np.inf]
    o = oos.copy()
    o["bin"] = pd.cut(o["rain_lag1_mm"], edges)
    cal = o.groupby("bin", observed=True).agg(
        n=("rain_lag1_mm", "size"),
        mean_rain_lag1=("rain_lag1_mm", "mean"),
        mean_pred_shortfall=("pred_model", "mean"),
        mean_true_shortfall=(TARGET_COLUMN, "mean"),
        mean_true_loss_rain=("true_loss_rain", "mean"),
    ).reset_index()
    rain["lag1_calibration"] = cal.assign(bin=cal["bin"].astype(str)).to_dict("records")
    in_range = cal[cal["mean_rain_lag1"] <= 50]
    rain["lag1_slope_pred_per_mm_0_50"] = float(np.polyfit(in_range["mean_rain_lag1"], in_range["mean_pred_shortfall"], 1)[0])
    rain["lag1_slope_true_shortfall_per_mm_0_50"] = float(np.polyfit(in_range["mean_rain_lag1"], in_range["mean_true_shortfall"], 1)[0])
    rain["lag1_slope_true_loss_rain_per_mm_0_50"] = float(np.polyfit(in_range["mean_rain_lag1"], in_range["mean_true_loss_rain"], 1)[0])
    res["rain"] = rain

    # ---- downtime ------------------------------------------------------------
    site_weight_sum = {}
    for eq, site in EQUIPMENT_SITE_BY_ID.items():
        site_weight_sum[site] = site_weight_sum.get(site, 0.0) + DOWNTIME_LOSS_WEIGHTS_BY_TYPE[EQUIPMENT_TYPE_BY_ID[eq]]
    res["downtime"] = {
        "structural_slope_true_loss_per_unit_pct_by_site": site_weight_sum,
        "empirical_slope_true_loss_downtime_vs_equipment_down_today_pct": _ols_slope(frame["equipment_down_today_pct"], frame["true_loss_downtime"]),
        "empirical_slope_true_loss_downtime_vs_rolling_7d": _ols_slope(frame["rolling_7d_downtime_pct"], frame["true_loss_downtime"]),
    }

    # ---- backlog ------------------------------------------------------------
    b = res["pd"]["backlog_t"]
    q05, q95 = frame["backlog_t"].quantile([0.05, 0.95])
    ratio = b["slope"] / BACKLOG_LOSS_COEF
    if b["slope"] > 0 and BACKLOG_RECOVERED_BAND[0] <= ratio <= BACKLOG_RECOVERED_BAND[1]:
        verdict = "RECOVERED"
    elif b["slope"] > 0 and ratio >= BACKLOG_DETECTED_FLOOR:
        verdict = "DETECTED, MIS-SIZED"
    else:
        verdict = "NOT RECOVERED"
    res["backlog"] = {
        "true_coef": BACKLOG_LOSS_COEF,
        "pd_slope": b["slope"],
        "pd_slope_over_truth": ratio,
        "verdict": verdict,
        "backlog_q05_q95": [float(q05), float(q95)],
        "true_effect_across_q05_q95": float(BACKLOG_LOSS_COEF * (q95 - q05)),
        "pd_rise_across_q05_q95": float(np.interp(q95, b["grid"], b["pd"]) - np.interp(q05, b["grid"], b["pd"])),
        "sd_true_loss_backlog": float(frame["true_loss_backlog"].std()),
        "sd_irreducible_noise": 0.03,
        "corr_backlog_with": {
            f: float(frame["backlog_t"].corr(frame[f]))
            for f in ("rolling_7d_downtime_pct", "equipment_down_today_pct", "rain_7d_mm", "blast_delay_days_lag")
        },
    }

    # ---- blast delay ------------------------------------------------------------
    res["blast"] = {
        "structural_loss_per_delay_day": BLAST_DELAY_EFFECT_LOSS,
        "empirical_slope_true_loss_blast_vs_feature": _ols_slope(frame["blast_delay_days_lag"], frame["true_loss_blast"]),
        "note": "feature counts delay-days in t-7..t-1 but the true effect window is t-5..t-1, so the empirical slope is attenuated below 0.06",
    }
    return res


def print_grading(g: dict) -> None:
    p = g["pd"]

    def line(name, s):
        print(f"    {name:<28} slope={s['slope']:+.5f}  net_rise={s['net_rise']:+.4f}  "
              f"decreases={s['n_decreases']}  max_drop={s['max_drop']:.4f}  spearman={s['spearman']:+.2f}")

    print("\nPARTIAL DEPENDENCE (reference set = all retained rows; model trained on the 80% split)")
    for f in p:
        line(f, p[f])

    r = g["rain"]
    print("\n  RAIN")
    print(f"    structural: {r['structural_lag1_coef']}/mm at lag 1, {r['structural_lag2_coef']}/mm at lag 2, +0.08 wet-pit if 3-day rain > 60mm")
    print(f"    empirical slope of TRUE loss_rain on rain_3d_mm : {r['empirical_slope_true_loss_rain_vs_rain_3d']:+.5f}/mm")
    print(f"    model PD slope on rain_3d_mm                   : {p['rain_3d_mm']['slope']:+.5f}/mm")
    print(f"    empirical step in TRUE loss_rain when heavy_lag1 : {r['empirical_step_true_loss_rain_heavy_lag1']:+.4f}   model PD step: {p['heavy_rain_lag1']['net_rise']:+.4f}")
    print("    out-of-sample calibration by ACTUAL rain on t-1 (R_{t-1} is not a model input):")
    print(f"      {'bin':<16}{'n':>5}{'R_{t-1}':>9}{'pred':>9}{'true':>9}{'true_rain_loss':>16}")
    for row in r["lag1_calibration"]:
        print(f"      {row['bin']:<16}{row['n']:>5}{row['mean_rain_lag1']:>9.1f}{row['mean_pred_shortfall']:>9.4f}{row['mean_true_shortfall']:>9.4f}{row['mean_true_loss_rain']:>16.4f}")
    print(f"      slope over 0-50mm (per mm): model pred {r['lag1_slope_pred_per_mm_0_50']:+.5f} | true shortfall {r['lag1_slope_true_shortfall_per_mm_0_50']:+.5f} | true loss_rain {r['lag1_slope_true_loss_rain_per_mm_0_50']:+.5f} | structural lag-1 coef {r['structural_lag1_coef']}")

    d = g["downtime"]
    print("\n  DOWNTIME")
    print(f"    structural loss per unit of unweighted down-pct, by site (sum of class weights): { {k: round(v, 3) for k, v in d['structural_slope_true_loss_per_unit_pct_by_site'].items()} }")
    print(f"    empirical slope TRUE loss_downtime on equipment_down_today_pct: {d['empirical_slope_true_loss_downtime_vs_equipment_down_today_pct']:+.4f}   model PD slope: {p['equipment_down_today_pct']['slope']:+.4f}")
    print(f"    empirical slope TRUE loss_downtime on rolling_7d_downtime_pct : {d['empirical_slope_true_loss_downtime_vs_rolling_7d']:+.4f}   model PD slope: {p['rolling_7d_downtime_pct']['slope']:+.4f}")
    s = p["rolling_7d_downtime_pct"]
    print(f"    rolling_7d_downtime_pct monotonic non-decreasing? decreases={s['n_decreases']} of {len(s['grid']) - 1} steps, spearman={s['spearman']:+.2f}, net rise={s['net_rise']:+.4f}")

    b = g["backlog"]
    print("\n  BACKLOG")
    print(f"    true coef {b['true_coef']}; PD slope {b['pd_slope']:+.5f} ({b['pd_slope_over_truth']:.2f}x truth) -> {b['verdict']}")
    print(f"    across backlog q05..q95 = {b['backlog_q05_q95'][0]:.3f}..{b['backlog_q05_q95'][1]:.3f}: true effect {b['true_effect_across_q05_q95']:+.4f}, PD rise {b['pd_rise_across_q05_q95']:+.4f}")
    print(f"    sd(true loss_backlog)={b['sd_true_loss_backlog']:.4f} vs irreducible target noise sd={b['sd_irreducible_noise']}")
    print(f"    backlog_t correlation with other features: { {k: round(v, 2) for k, v in b['corr_backlog_with'].items()} }")

    bl = g["blast"]
    print("\n  BLAST DELAY")
    print(f"    structural +{bl['structural_loss_per_delay_day']} per delay-day; empirical slope TRUE loss_blast on feature {bl['empirical_slope_true_loss_blast_vs_feature']:+.4f}; model PD slope {p['blast_delay_days_lag']['slope']:+.4f}")
    print(f"    monotonic? decreases={p['blast_delay_days_lag']['n_decreases']}, spearman={p['blast_delay_days_lag']['spearman']:+.2f}")
    print(f"    ({bl['note']})")


# ---------------------------------------------------------------------
# Training-data ranges for the Simulator UI hints
# ---------------------------------------------------------------------
def _compute_training_data_ranges(
    production: pd.DataFrame, downtime: pd.DataFrame, blast: pd.DataFrame, frame: pd.DataFrame,
    n_machines: dict[str, int],
) -> dict:
    """Per-condition-type severity/duration statistics from the training CSVs,
    surfaced in the Simulator UI as "typical range in training data" hints.

    Changes vs the previous version: equipment severity divides by each site's
    real machine count (5/5/9) instead of a hardcoded 5; delay_blasting duration
    comes from the real blast-event durations instead of the deleted 5-10 day
    injection windows; rainfall_event severity is now REAL 3-day rain in mm
    instead of the cosine 0-100 index (see severity_unit)."""
    def q(series, p):
        return round(float(series.quantile(p)), 1)

    dur_days = downtime["duration_hours"] / 24.0
    denom = downtime["site_id"].map(lambda s: n_machines[s] * 7 * 24)
    equip_pct = (downtime["duration_hours"] / denom) * 100
    equip = {
        "severity_min_pct": 0,
        "severity_max_pct": round(float(equip_pct.max()), 1),
        "severity_p25_pct": q(equip_pct, 0.25), "severity_p50_pct": q(equip_pct, 0.50),
        "severity_p75_pct": q(equip_pct, 0.75), "severity_p95_pct": q(equip_pct, 0.95),
        "severity_levels": {"low": q(equip_pct, 0.25), "medium": q(equip_pct, 0.50), "high": q(equip_pct, 0.75), "severe": q(equip_pct, 0.95)},
        "duration_min_days": round(float(dur_days.min()), 1), "duration_max_days": round(float(dur_days.max()), 1),
        "duration_p25_days": q(dur_days, 0.25), "duration_p50_days": q(dur_days, 0.50),
        "duration_p75_days": q(dur_days, 0.75), "duration_p95_days": q(dur_days, 0.95),
        "event_count": int(len(downtime)),
    }
    by_reason: dict = {}
    for reason, grp in downtime.groupby("reason"):
        rdur = grp["duration_hours"] / 24.0
        by_reason[reason] = {
            "duration_min_days": round(float(rdur.min()), 1), "duration_max_days": round(float(rdur.max()), 1),
            "severity_min_hours": round(float(grp["duration_hours"].min()), 1),
            "severity_max_hours": round(float(grp["duration_hours"].max()), 1),
            "count": int(len(grp)),
        }

    shortfall = ((production["target_output"] - production["actual_output"]) / production["target_output"]).clip(lower=0) * 100
    bd = blast["delay_days"]
    blast_r = {
        "severity_min_pct": q(shortfall, 0.25), "severity_max_pct": q(shortfall, 0.95),
        "severity_p25_pct": q(shortfall, 0.25), "severity_p50_pct": q(shortfall, 0.50),
        "severity_p75_pct": q(shortfall, 0.75), "severity_p95_pct": q(shortfall, 0.95),
        "severity_levels": {"low": q(shortfall, 0.25), "medium": q(shortfall, 0.50), "high": q(shortfall, 0.75), "severe": q(shortfall, 0.95)},
        "duration_min_days": int(bd.min()), "duration_max_days": int(bd.max()),
        "duration_p25_days": q(bd, 0.25), "duration_p50_days": q(bd, 0.50),
        "duration_p75_days": q(bd, 0.75), "duration_p95_days": q(bd, 0.95),
    }

    rain3_all = frame["rain_3d_mm"].dropna()
    # Levels and "typical" bands describe rain EVENTS, so they are percentiles over the 3-day windows that
    # had measurable rain (>= the IMD 2.5 mm rainy-day threshold): over all windows the median is 0.9 mm
    # and a "Medium" rainfall event would be a non-event. The OOD bound stays the full range seen.
    rain3 = rain3_all[rain3_all >= RAINY_WINDOW_MM]
    rain = {
        "severity_unit": "mm of rain over the preceding 3 days (was: 0-100 cosine index)",
        "severity_basis": (
            f"percentiles over the {len(rain3)} of {len(rain3_all)} training 3-day windows with >= {RAINY_WINDOW_MM} mm "
            "(IMD rainy-day threshold); min/max are over all windows"
        ),
        "severity_min_pct": round(float(rain3_all.min()), 1), "severity_max_pct": round(float(rain3_all.max()), 1),
        "severity_p25_pct": q(rain3, 0.25), "severity_p50_pct": q(rain3, 0.50),
        "severity_p75_pct": q(rain3, 0.75), "severity_p95_pct": q(rain3, 0.95),
        "severity_levels": {"low": q(rain3, 0.25), "medium": q(rain3, 0.50), "high": q(rain3, 0.75), "severe": q(rain3, 0.95)},
        # placeholders carried over unchanged from the previous version; not measured
        "duration_min_days": 1, "duration_max_days": 30,
        "duration_p25_days": 7, "duration_p50_days": 14, "duration_p75_days": 21, "duration_p95_days": 30,
        "monsoon_months": "Jun–Sep",
    }
    return {
        "data_source": "synthetic",
        "data_generator": "scripts/synthetic_operations.py via generate_datasets.py",
        "date_range": f"{production['date'].min().date()} to {production['date'].max().date()}",
        "equipment_down": equip,
        "equipment_down_by_reason": by_reason,
        "delay_blasting": blast_r,
        "rainfall_event": rain,
    }


# ---------------------------------------------------------------------
KNOWN_LIMITATION_ROLLING_ORIGIN = (
    "Rolling-origin stability check (a stability check, NOT the ship gate): the model's edge over "
    "persistence is largest in monsoon periods and can fall below persistence in dry windows at "
    "high-downtime sites. Recorded, not fixed: no re-split, re-tune or re-framing was done to remove it."
)


def rolling_origin_losses(rolling: list[dict]) -> list[dict]:
    """Every (window, slice) where the model's RMSE was not below persistence's or the train mean's."""
    out = []
    for w in rolling:
        for name, e in w["table"].items():
            if not beats_both(e, "rmse"):
                out.append({
                    "window": w["window"], "test_period": f"{w['test_start']} .. {w['test_end']}", "slice": name,
                    "model_rmse": round(e["model"]["rmse"], 4),
                    "persistence_rmse": round(e["persistence"]["rmse"], 4),
                    "train_mean_rmse": round(e["train_mean"]["rmse"], 4),
                    "r2_gain_over_persistence": round(e["r2_gain_over_persistence"], 4),
                })
    return out


def write_regression_fixture(model, df: pd.DataFrame, out_dir: str, n_rows: int = 24) -> None:
    """Inputs + the trained model's own predictions, stored beside the artifact.
    tests/test_model_artifact_regression.py reloads the artifact in the backend
    venv and requires these numbers back: the check that catches silent drift
    in xgboost (or anything else that changes what the pickle computes)."""
    rows = df.iloc[np.linspace(0, len(df) - 1, n_rows).astype(int)]
    nan_rows = df[df["soil_moisture_m3m3"].isna()].head(2)  # keep the NaN-handling path covered
    rows = pd.concat([rows, nan_rows]).drop_duplicates(subset=["site_id", "date"])
    x = rows[FEATURE_COLUMNS]
    fixture = {
        "xgboost_version": xgboost.__version__,
        "feature_columns": FEATURE_COLUMNS,
        "inputs": [[None if pd.isna(v) else float(v) for v in r] for r in x.to_numpy()],
        "expected": [float(v) for v in model.predict(x)],
    }
    with open(os.path.join(out_dir, "shortfall_regression_fixture.json"), "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)


def run_ablation(feature: str) -> int:
    """DIAGNOSTIC ONLY. Retrain without `feature` on the identical split and
    report how much of the win depends on it. Not a selection step: the full
    model is what ships. Pre-declared 'alarming' outcome: the ablated model fails
    to beat either baseline on the pooled holdout."""
    enforce_pinned_xgboost()
    assert feature in FEATURE_COLUMNS, feature
    inputs = fe.load_inputs()
    frame = fe.build_feature_frame(inputs, fe.machines_per_site())
    df = frame[~frame["in_warmup"]].reset_index(drop=True)
    train, test = time_split(df)
    full = evaluate_split(train, test)
    abl = evaluate_split(train, test, features=[f for f in FEATURE_COLUMNS if f != feature])

    print("=" * 78)
    print(f"DIAGNOSTIC ABLATION: retrain WITHOUT {feature} (same split, same hyperparameters)")
    print("=" * 78)
    print_table("FULL MODEL (all 14 features), holdout", full["table"])
    print_table(f"ABLATED (no {feature}), holdout", abl["table"])
    print(f"\n  {'slice':<9}{'RMSE full':>11}{'RMSE ablated':>14}{'delta':>9}   {'MAE full':>9}{'MAE abl':>9}   {'R2gain full':>12}{'R2gain abl':>11}   beats both (ablated)")
    for name in full["table"]:
        f, a = full["table"][name], abl["table"][name]
        print(f"  {name:<9}{f['model']['rmse']:>11.4f}{a['model']['rmse']:>14.4f}{a['model']['rmse'] - f['model']['rmse']:>+9.4f}   "
              f"{f['model']['mae']:>9.4f}{a['model']['mae']:>9.4f}   {f['r2_gain_over_persistence']:>+12.3f}{a['r2_gain_over_persistence']:>+11.3f}   "
              f"RMSE={'YES' if beats_both(a, 'rmse') else 'NO'} MAE={'YES' if beats_both(a, 'mae') else 'NO'}")
    alarming = not beats_both(abl["table"]["pooled"], "rmse")
    print(f"\n  ALARMING (ablated model fails a baseline on the pooled holdout)? {'YES - STOP AND REPORT' if alarming else 'no'}")

    os.makedirs(CANDIDATE_DIR, exist_ok=True)
    with open(os.path.join(CANDIDATE_DIR, f"ablation_{feature}.json"), "w", encoding="utf-8") as fh:
        json.dump({"ablated_feature": feature, "diagnostic_only": True, "alarming": alarming,
                   "full": full["table"], "ablated": abl["table"]}, fh, indent=2, default=float)
    return 0


def main() -> int:
    if "--ablate" in sys.argv:
        return run_ablation(sys.argv[sys.argv.index("--ablate") + 1])
    enforce_pinned_xgboost()
    print("=" * 78)
    print("Stage 3: Shortfall Forecaster — causal data, honest evaluation")
    print("=" * 78)

    inputs = fe.load_inputs()
    n_machines = fe.machines_per_site()
    print(f"\nmachines per site (from seed_graph.cypher roster): {n_machines}")

    frame = fe.build_feature_frame(inputs, n_machines)
    print(f"feature frame: {len(frame)} rows; dropping first {fe.WARMUP_DAYS} days per site as warm-up")
    print("\nLook-ahead guard:")
    fe.assert_no_lookahead(frame, inputs, n_machines)

    csv_backlog_gap = float((frame["backlog_t"] - frame["true_backlog"]).abs().max())
    print(f"  recomputed backlog_t vs generator's stored backlog column: max abs diff {csv_backlog_gap:.5f}")

    df = frame[~frame["in_warmup"]].reset_index(drop=True)
    print(f"retained rows: {len(df)} ({df['date'].min().date()} .. {df['date'].max().date()})")

    train, test = time_split(df)
    print(f"\nholdout split: train={len(train)} rows (< {test['date'].min().date()}), test={len(test)} rows "
          f"({test['date'].min().date()} .. {test['date'].max().date()})")

    hold = evaluate_split(train, test)
    print_table("HOLDOUT (last 20% of dates)", hold["table"])

    gate_detail = {name: {"rmse": beats_both(e, "rmse"), "mae": beats_both(e, "mae")} for name, e in hold["table"].items()}
    ship = all(v["rmse"] for v in gate_detail.values())
    print("\n  beats BOTH baselines?   " + "   ".join(f"{k}: RMSE={'YES' if v['rmse'] else 'NO'} MAE={'YES' if v['mae'] else 'NO'}" for k, v in gate_detail.items()))

    print("\nROLLING-ORIGIN (expanding train window; 15% test blocks)")
    rolling = []
    oos_frames = []
    for i, (tr, te) in enumerate(rolling_origin_splits(df), start=1):
        r = evaluate_split(tr, te)
        oos_frames.append(r["test"])
        rolling.append({"window": i, "train_end": str(te["date"].min().date()), "test_start": str(te["date"].min().date()),
                        "test_end": str(te["date"].max().date()), "table": r["table"]})
        print_table(f"  window {i}: train < {te['date'].min().date()}, test {te['date'].min().date()} .. {te['date'].max().date()}", r["table"])
    rolling_pass = [all(beats_both(e, "rmse") for e in w["table"].values()) for w in rolling]
    print(f"\n  rolling-origin: every slice beats both baselines (RMSE), per window: {rolling_pass}")

    oos = pd.concat(oos_frames, ignore_index=True)
    imp = sorted(zip(FEATURE_COLUMNS, hold["model"].feature_importances_), key=lambda t: -t[1])
    print("\nFeature importances (gain-based, holdout model):")
    for f, v in imp:
        print(f"  {f:<30}{v:.3f}")

    grading = grade_against_truth(hold["model"], df, oos)
    print_grading(grading)

    # ---- artifacts ------------------------------------------------------------
    install = ship and "--ship" in sys.argv
    out_dir = MODELS_DIR if install else CANDIDATE_DIR
    os.makedirs(out_dir, exist_ok=True)
    pooled = hold["table"]["pooled"]
    residuals = hold["test"][TARGET_COLUMN] - hold["test"]["pred_model"]
    metrics = {
        "rmse": round(pooled["model"]["rmse"], 4),
        "mae": round(pooled["model"]["mae"], 4),
        "residual_std": round(float(residuals.std()), 4),
        "target_shortfall_mean": round(pooled["target_mean"], 4),
        "target_shortfall_std": round(pooled["target_std"], 4),
        "test_sample_count": pooled["n"],
        "baseline_train_mean_rmse": round(pooled["train_mean"]["rmse"], 4),
        "baseline_persistence_rmse": round(pooled["persistence"]["rmse"], 4),
        "r2_gain_over_persistence": round(pooled["r2_gain_over_persistence"], 4),
        "perfect_forecast_caveat": (
            "rain_today_mm is trained on OBSERVED same-day rain (a perfect forecast). Reported accuracy "
            "is an optimistic ceiling relative to live use with a real forecast."
        ),
        "data_source": "synthetic (causal generator: scripts/synthetic_operations.py)",
        "features": FEATURE_COLUMNS,
        "evaluation": "time-ordered 20% holdout; 14-day warm-up dropped per site; see train_shortfall_model.py docstring",
        "ship_gate_passed": ship,
        "xgboost_version": xgboost.__version__,
        # the feature definitions' constants, so live inference (app/services/live_features.py) uses exactly
        # the ones the model was trained with
        "feature_constants": {
            "machines_per_site": n_machines,
            "heavy_rain_mm": fe.HEAVY_RAIN_MM,
            "backlog_decay": fe.BACKLOG_DECAY,
            "rolling_downtime_window_days": fe.ROLLING_DOWNTIME_WINDOW_DAYS,
            "maintenance_reason": fe.MAINTENANCE_REASON,
        },
        "feature_provenance": fe.FEATURE_PROVENANCE,
        "known_limitations": [
            KNOWN_LIMITATION_ROLLING_ORIGIN,
            "Features with NO causal term in the synthetic generator (rain_today_mm, soil_moisture_m3m3, "
            "days_since_last_maintenance, dow/month beyond rainfall) have learned effects that are dataset "
            "artifacts; do not cite them as findings. See feature_provenance.",
            "backlog_t: the true effect (0.02 x backlog) is too weak for the model to recover reliably; the "
            "learned slope is about a quarter of the truth.",
        ],
        "rolling_origin_pooled_rmse": [
            {"window": w["window"], "test_period": f"{w['test_start']} .. {w['test_end']}",
             "model": round(w["table"]["pooled"]["model"]["rmse"], 4),
             "persistence": round(w["table"]["pooled"]["persistence"]["rmse"], 4),
             "train_mean": round(w["table"]["pooled"]["train_mean"]["rmse"], 4)} for w in rolling
        ],
        "rolling_origin_slices_not_beating_both_baselines": rolling_origin_losses(rolling),
    }
    # the training-time xgboost version travels INSIDE the artifact; the loader
    # (app/services/forecast_model.py) refuses to load it under a different major.minor
    hold["model"].moil_training_meta = {"xgboost_version": xgboost.__version__, "feature_columns": FEATURE_COLUMNS}
    joblib.dump(hold["model"], os.path.join(out_dir, "shortfall_forecaster.pkl"))
    write_regression_fixture(hold["model"], df, out_dir)
    with open(os.path.join(out_dir, "feature_columns.json"), "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)
    with open(os.path.join(out_dir, "model_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    report = {"holdout": hold["table"], "rolling_origin": rolling, "gate": gate_detail, "grading": grading,
              "feature_importances": dict(imp)}
    with open(os.path.join(out_dir, "evaluation_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    ranges = _compute_training_data_ranges(
        inputs.production, inputs.downtime, inputs.blast, df, n_machines
    )
    with open(os.path.join(out_dir, "training_data_ranges.json"), "w", encoding="utf-8") as f:
        json.dump(ranges, f, indent=2)

    print("\n" + "=" * 78)
    if install:
        print(f"SHIP GATE: PASSED, --ship given — artifacts INSTALLED to {out_dir}")
    elif ship:
        print(f"SHIP GATE: PASSED — candidate written to {out_dir}; shipped artifacts untouched (re-run with --ship to install)")
    else:
        print(f"SHIP GATE: FAILED — candidate written to {out_dir}; shipped artifacts untouched")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
