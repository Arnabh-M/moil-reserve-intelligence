"""Shortfall-forecaster feature engineering + a machine-checked look-ahead guard.

Kept separate from train_shortfall_model.py (numpy/pandas only, no XGBoost) so
the leakage check can be imported and run on its own, including from the
backend test suite.

FEATURES (one row per site per day t; target is shortfall_pct on day t)
  rain_today_mm             day t's rain. THE ONE DELIBERATE EXCEPTION to the
                            look-ahead rule: in training this is the observed
                            value, i.e. a "perfect forecast". Reported accuracy
                            is therefore an optimistic ceiling relative to live
                            use with a real (noisy) forecast.
                            [NO CAUSAL TERM IN SYNTHETIC GENERATOR - see below]
  rain_3d_mm, rain_7d_mm    rain summed over days t-3..t-1 / t-7..t-1
  heavy_rain_lag1           1.0 if rain on t-1 >= HEAVY_RAIN_MM (35mm; 64.5mm
                            fires on ~2 site-days in 631, useless as a feature)
  soil_moisture_m3m3        SMAP L4 surface soil moisture from day t-1
                            [NO CAUSAL TERM IN SYNTHETIC GENERATOR - see below]
  rolling_7d_downtime_pct   machine-hours down over days t-7..t-1 / (machines *
                            168h). Only hours falling inside the window count,
                            so an outage still running at the end of t-1 gets
                            no credit for recovery time after the window.
  equipment_down_today_pct  hours of day t already covered by outages that
                            STARTED BEFORE day t, / (machines * 24h), using the
                            outage's recorded return-to-service time. Outages
                            that begin during day t (including scheduled
                            maintenance dated t) are excluded: they are rows
                            dated >= t. See "JUDGEMENT CALLS" below.
  days_since_last_maintenance
                            site-level MAX over machines of days since that
                            machine's last scheduled maintenance dated < t
                            (i.e. the most overdue machine, which is what the
                            three deliberately-overdue machines are for). NaN
                            until at least one machine has been serviced.
                            [NO CAUSAL TERM IN SYNTHETIC GENERATOR - see below]
  backlog_t                 decayed cumulative unmet tonnage through t-1,
                            normalised by target: b_t = max(0, DECAY*b_{t-1} +
                            shortfall_{t-1}), b_first = 0. Recomputed here from
                            observed shortfalls, NOT read from the generator's
                            `backlog` column.
  blast_delay_days_lag      number of blast-delay days in t-7..t-1. Computed by
                            app.services.shortfall_features.blast_delay_days_lag,
                            the SAME function the API calls at inference (reading
                            the blast_events table); this module never
                            re-implements it.
  dow_*, month_*            sin/cos encodings of the calendar date

DEMO-NARRATIVE GUARDRAIL - features with NO causal term in the synthetic generator
  rain_today_mm, soil_moisture_m3m3, days_since_last_maintenance (and the dow/month
  encodings beyond what real rainfall implies) are kept because they are physically
  plausible and would matter against real data. But scripts/synthetic_operations.py
  gives none of them any effect on production, so whatever slope the model learned
  for them is a DATASET ARTIFACT, not a finding. Do not say "the model learned that
  overdue maintenance raises shortfall": we did not put that in the world it learned
  from. FEATURE_PROVENANCE below is written into model_metrics.json so the caveat
  travels with the artifact.

DROPPED vs the old model: the cosine rainfall_proxy (a calendar guess standing
in for real rain) and the 14-day trailing-shortfall-mean schedule_pressure.

JUDGEMENT CALLS worth challenging
  * equipment_down_today_pct uses outage END times for outages already under
    way at the start of the day. That is "as scheduled at the start of t"
    (operations knows an expected return time) but it is the closest this
    feature comes to future information. A stricter alternative is to assume
    every ongoing outage lasts the whole day.
  * backlog_t uses the world's true decay (0.85). The model is handed a
    correctly-specified state variable, so "can it recover the backlog effect"
    is a somewhat generous test.
  * In the synthetic world today's rain has NO direct effect on today's loss
    (loss uses rain lags 1 and 2). rain_today_mm can only help through rain
    autocorrelation. Same for soil moisture and days_since_last_maintenance:
    none of them has a causal term in the generator.

LOOK-AHEAD DISCIPLINE
assert_no_lookahead() re-derives every feature (except rain_today_mm and the
pure-calendar encodings) for EVERY retained row with an independent, loop-based
reference that is only ever handed input rows dated strictly before t, then
demands exact agreement with the vectorised pipeline. If the vectorised code
leaned on any row dated >= t the two could not agree. It also runs canaries:
deliberately leaky variants of several features that the check must reject, so
a vacuous "always passes" check cannot slip through.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import sys

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Features that training AND inference compute live in ONE module inside the
# backend package, so the API and this pipeline execute the same function.
try:
    from app.services import shortfall_features as shared
except ImportError:  # running from the repo root, backend not on sys.path yet
    sys.path.insert(0, str(BASE_DIR / "oresight-backend"))
    from app.services import shortfall_features as shared

WARMUP_DAYS = 14  # first ~2 weeks per site: backlog starts at 0, rolling windows need history
HEAVY_RAIN_MM = 35.0
BACKLOG_DECAY = 0.85  # feature definition; equals the generator's true decay (see JUDGEMENT CALLS)
ROLLING_DOWNTIME_WINDOW_DAYS = 7
BLAST_LAG_WINDOW_DAYS = shared.BLAST_LAG_WINDOW_DAYS
MAINTENANCE_REASON = "scheduled maintenance"

FEATURE_COLUMNS = [
    "rain_today_mm",
    "rain_3d_mm",
    "rain_7d_mm",
    "heavy_rain_lag1",
    "soil_moisture_m3m3",
    "rolling_7d_downtime_pct",
    "equipment_down_today_pct",
    "days_since_last_maintenance",
    "backlog_t",
    "blast_delay_days_lag",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
]
TARGET_COLUMN = "shortfall_pct"
LOOKAHEAD_EXEMPT_FEATURES = ("rain_today_mm",)
CALENDAR_FEATURES = ("dow_sin", "dow_cos", "month_sin", "month_cos")
HISTORY_FEATURES = [
    c for c in FEATURE_COLUMNS if c not in LOOKAHEAD_EXEMPT_FEATURES and c not in CALENDAR_FEATURES
]

# Ground-truth columns written by scripts/synthetic_operations.py. Carried through
# ONLY so the evaluation can grade the model against the known formulas; never
# fed to the model.
TRUTH_COLUMNS = ["backlog", "loss_rain", "loss_downtime", "loss_backlog", "loss_blast", "loss_total"]

NO_CAUSAL_TERM_NOTE = (
    "no causal term in synthetic generator; learned effect is a dataset artifact, "
    "do not cite as a finding"
)
# Per-feature honesty annotations, written into model_metrics.json. A feature can
# be physically plausible against real data and still have NO effect in the
# synthetic world the model learned from; the demo narrative must not present
# such a learned slope as a discovered relationship.
FEATURE_PROVENANCE = {
    "rain_today_mm": {
        "causal_term_in_generator": False,
        "note": NO_CAUSAL_TERM_NOTE + ". The generator's rain loss uses lags 1 and 2 only, so today's "
        "rain helps only through rain autocorrelation. Also trained on OBSERVED same-day rain "
        "(a perfect forecast): reported accuracy is an optimistic ceiling.",
    },
    "rain_3d_mm": {"causal_term_in_generator": True, "note": "proxies the lag-1/lag-2 rain terms and the wet-pit trigger (3-day rain > 60mm)"},
    "rain_7d_mm": {"causal_term_in_generator": True, "note": "indirect: correlates with the causal rain lags; no term of its own"},
    "heavy_rain_lag1": {"causal_term_in_generator": True, "note": "proxies the lag-1 rain term (rain on t-1 >= 35mm)"},
    "soil_moisture_m3m3": {"causal_term_in_generator": False, "note": NO_CAUSAL_TERM_NOTE + ". Real SMAP data that merely co-varies with rain."},
    "rolling_7d_downtime_pct": {"causal_term_in_generator": True, "note": "indirect: outages persist, so trailing downtime co-varies with today's causal downtime term; not monotone in the learned model"},
    "equipment_down_today_pct": {"causal_term_in_generator": True, "note": "direct: class-weighted hours down today (unweighted here)"},
    "days_since_last_maintenance": {
        "causal_term_in_generator": False,
        "note": NO_CAUSAL_TERM_NOTE + ". The generator's overdue machines simply stop being serviced; "
        "failure rates do not depend on maintenance age. Do NOT claim the model learned that overdue "
        "maintenance raises shortfall.",
    },
    "backlog_t": {"causal_term_in_generator": True, "note": "direct but weak (0.02 x backlog, ~1.8pp mean); learned slope is roughly a quarter of the truth"},
    "blast_delay_days_lag": {"causal_term_in_generator": True, "note": "direct: +0.06 loss per delay-day on the following 5 days; feature window is 7 days"},
    "dow_sin": {"causal_term_in_generator": False, "note": NO_CAUSAL_TERM_NOTE + " (no day-of-week effect exists in the generator)"},
    "dow_cos": {"causal_term_in_generator": False, "note": NO_CAUSAL_TERM_NOTE + " (no day-of-week effect exists in the generator)"},
    "month_sin": {"causal_term_in_generator": False, "note": "seasonality enters only through real rainfall; any month effect beyond rain is an artifact"},
    "month_cos": {"causal_term_in_generator": False, "note": "seasonality enters only through real rainfall; any month effect beyond rain is an artifact"},
}
assert set(FEATURE_PROVENANCE) == set(FEATURE_COLUMNS)


@dataclass
class Inputs:
    production: pd.DataFrame
    weather: pd.DataFrame
    downtime: pd.DataFrame
    blast: pd.DataFrame


def load_inputs(data_dir: Path = DATA_DIR) -> Inputs:
    production = pd.read_csv(data_dir / "production_history.csv", parse_dates=["date"])
    weather = pd.read_csv(
        data_dir / "satellite_daily_features.csv",
        usecols=["site_id", "date", "rainfall_mm", "soil_moisture_m3m3"],
        parse_dates=["date"],
    )
    downtime = pd.read_csv(
        data_dir / "equipment_downtime_log.csv", parse_dates=["down_start", "down_end"]
    )
    blast = pd.read_csv(data_dir / "blast_events.csv", parse_dates=["planned_date"])
    return Inputs(production, weather, downtime, blast)


_GENERATOR_MODULE = None


def load_generator_module():
    """scripts/synthetic_operations.py, loaded by file path. Not `import
    scripts.synthetic_operations`: oresight-backend/ has its own `scripts`
    package, and the two collide whenever this runs under the backend's pytest."""
    global _GENERATOR_MODULE
    if _GENERATOR_MODULE is None:
        import importlib.util

        path = BASE_DIR / "scripts" / "synthetic_operations.py"
        spec = importlib.util.spec_from_file_location("moil_synthetic_operations", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _GENERATOR_MODULE = module
    return _GENERATOR_MODULE


def machines_per_site() -> dict[str, int]:
    """Machine count per site from the seed_graph.cypher roster (5/5/9), so
    nothing here assumes 5 machines per site."""
    counts: dict[str, int] = {}
    for site_id in load_generator_module().EQUIPMENT_SITE_BY_ID.values():
        counts[site_id] = counts.get(site_id, 0) + 1
    return counts


# ---------------------------------------------------------------------
# Vectorised pipeline
# ---------------------------------------------------------------------
def _daily_machine_hours_down(
    events: pd.DataFrame, date_index: pd.DatetimeIndex, carry_only: bool
) -> np.ndarray:
    """Machine-hours down inside each calendar day of `date_index`. With
    carry_only, an outage contributes only to days AFTER the one it started on
    (i.e. only outages that began before the day in question)."""
    hours = np.zeros(len(date_index))
    d0 = date_index[0]
    n = len(date_index)
    one_day = pd.Timedelta(days=1)
    for start, end in zip(events["down_start"], events["down_end"]):
        first_day = start.normalize()
        day = first_day
        last_day = end.normalize()
        while day <= last_day:
            i = (day - d0).days
            if 0 <= i < n and not (carry_only and day == first_day):
                overlap = min(end, day + one_day) - max(start, day)
                hours[i] += max(0.0, overlap.total_seconds() / 3600.0)
            day += one_day
    return hours


def _days_since_last_maintenance(
    maint_site: pd.DataFrame, date_index: pd.DatetimeIndex
) -> np.ndarray:
    per_machine = []
    for _, grp in maint_site.groupby("equipment_id"):
        dates = np.sort(grp["down_start"].dt.normalize().to_numpy())
        pos = np.searchsorted(dates, date_index.to_numpy(), side="left") - 1  # dates strictly < t
        days = np.full(len(date_index), np.nan)
        ok = pos >= 0
        days[ok] = (date_index.to_numpy()[ok] - dates[pos[ok]]) / np.timedelta64(1, "D")
        per_machine.append(days)
    if not per_machine:
        return np.full(len(date_index), np.nan)
    stacked = np.vstack(per_machine)
    out = np.full(len(date_index), np.nan)
    has_any = ~np.all(np.isnan(stacked), axis=0)
    out[has_any] = np.nanmax(stacked[:, has_any], axis=0)
    return out


def _backlog_series(shortfall: np.ndarray) -> np.ndarray:
    b = np.zeros(len(shortfall))
    for i in range(1, len(shortfall)):
        b[i] = max(0.0, BACKLOG_DECAY * b[i - 1] + shortfall[i - 1])
    return b


def build_feature_frame(inputs: Inputs, n_machines: dict[str, int]) -> pd.DataFrame:
    """One row per (site, day) with FEATURE_COLUMNS, the target, the persistence
    input (prev_shortfall), the warm-up flag, and TRUTH_COLUMNS for grading."""
    frames = []
    for site_id, prod in inputs.production.groupby("site_id"):
        prod = prod.sort_values("date").reset_index(drop=True)
        idx = pd.DatetimeIndex(prod["date"])
        assert (idx[1:] - idx[:-1] == pd.Timedelta(days=1)).all(), f"{site_id}: date gap in production"

        wx = inputs.weather[inputs.weather["site_id"] == site_id].set_index("date").reindex(idx)
        rain = wx["rainfall_mm"]
        assert rain.notna().all(), f"{site_id}: NaN rain inside the production span"
        sm = wx["soil_moisture_m3m3"]

        ev = inputs.downtime[inputs.downtime["site_id"] == site_id]
        maint = ev[ev["reason"] == MAINTENANCE_REASON]
        bl = inputs.blast[inputs.blast["site_id"] == site_id]
        n = n_machines[site_id]

        shortfall = ((prod["target_output"] - prod["actual_output"]) / prod["target_output"]).to_numpy()
        month = idx.month.to_numpy()
        dow = idx.dayofweek.to_numpy()

        hours_all = pd.Series(_daily_machine_hours_down(ev, idx, carry_only=False), index=idx)
        hours_carry = _daily_machine_hours_down(ev, idx, carry_only=True)
        blast_events = [(p.date(), int(d)) for p, d in zip(bl["planned_date"], bl["delay_days"])]

        out = pd.DataFrame(
            {
                "site_id": site_id,
                "date": idx,
                "target_output": prod["target_output"].to_numpy(),
                "actual_output": prod["actual_output"].to_numpy(),
                TARGET_COLUMN: shortfall,
                "prev_shortfall": np.r_[np.nan, shortfall[:-1]],
                "rain_today_mm": rain.to_numpy(),
                "rain_3d_mm": rain.shift(1).rolling(3, min_periods=3).sum().to_numpy(),
                "rain_7d_mm": rain.shift(1).rolling(7, min_periods=7).sum().to_numpy(),
                "heavy_rain_lag1": np.where(
                    rain.shift(1).isna(), np.nan, (rain.shift(1) >= HEAVY_RAIN_MM).astype(float)
                ),
                "soil_moisture_m3m3": sm.shift(1).to_numpy(),
                "rolling_7d_downtime_pct": (
                    hours_all.shift(1)
                    .rolling(ROLLING_DOWNTIME_WINDOW_DAYS, min_periods=ROLLING_DOWNTIME_WINDOW_DAYS)
                    .sum()
                    / (n * ROLLING_DOWNTIME_WINDOW_DAYS * 24)
                ).to_numpy(),
                "equipment_down_today_pct": hours_carry / (n * 24),
                "days_since_last_maintenance": _days_since_last_maintenance(maint, idx),
                "backlog_t": _backlog_series(shortfall),
                # the SAME function the API calls at inference (app.services.shortfall_features)
                "blast_delay_days_lag": [shared.blast_delay_days_lag(blast_events, t) for t in idx],
                "dow_sin": np.sin(2 * np.pi * dow / 7),
                "dow_cos": np.cos(2 * np.pi * dow / 7),
                "month_sin": np.sin(2 * np.pi * month / 12),
                "month_cos": np.cos(2 * np.pi * month / 12),
                "rain_lag1_mm": rain.shift(1).to_numpy(),  # grading only, never a model input
            }
        )
        for col in TRUTH_COLUMNS:
            out[f"true_{col}"] = prod[col].to_numpy()
        out["in_warmup"] = (out["date"] - out["date"].min()).dt.days < WARMUP_DAYS
        frames.append(out)

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------
# Look-ahead guard
# ---------------------------------------------------------------------
class _SiteArrays:
    """Per-site views of the raw inputs, extracted once so the per-row
    reference check does not re-filter DataFrames thousands of times."""

    def __init__(self, inputs: Inputs, site_id: str):
        prod = inputs.production[inputs.production["site_id"] == site_id].sort_values("date")
        self.prod_dates = prod["date"].to_numpy()
        self.prod_shortfall = (
            (prod["target_output"] - prod["actual_output"]) / prod["target_output"]
        ).to_numpy()
        wx = inputs.weather[inputs.weather["site_id"] == site_id]
        self.rain = dict(zip(wx["date"], wx["rainfall_mm"]))
        self.sm = dict(zip(wx["date"], wx["soil_moisture_m3m3"]))
        ev = inputs.downtime[inputs.downtime["site_id"] == site_id]
        self.ev_start = ev["down_start"].to_numpy()
        self.ev_end = ev["down_end"].to_numpy()
        self.ev_machine = ev["equipment_id"].to_numpy()
        self.ev_is_maint = (ev["reason"] == MAINTENANCE_REASON).to_numpy()
        bl = inputs.blast[inputs.blast["site_id"] == site_id]
        self.bl_planned = bl["planned_date"].to_numpy()
        self.bl_days = bl["delay_days"].to_numpy()


def _hours_between(a: np.datetime64, b: np.datetime64) -> float:
    return max(0.0, float((b - a) / np.timedelta64(1, "h")))


def reference_features_at(site: _SiteArrays, t: pd.Timestamp, n_machines: int) -> dict[str, float]:
    """Deliberately simple, loop-based re-derivation of every history feature
    for day t, using ONLY input rows dated strictly before t."""
    t64 = np.datetime64(t)
    day = np.timedelta64(1, "D")
    nan = float("nan")

    # rows dated < t (the only rows this function is allowed to see)
    prod_mask = site.prod_dates < t64
    shortfall_hist = site.prod_shortfall[prod_mask]
    ev_mask = site.ev_start < t64
    ev_start, ev_end = site.ev_start[ev_mask], site.ev_end[ev_mask]
    ev_machine, ev_is_maint = site.ev_machine[ev_mask], site.ev_is_maint[ev_mask]
    bl_mask = site.bl_planned < t64
    bl_planned, bl_days = site.bl_planned[bl_mask], site.bl_days[bl_mask]
    assert (site.prod_dates[prod_mask] < t64).all() and (ev_start < t64).all() and (bl_planned < t64).all()

    def rain_on(k: int) -> float:  # rain k days before t; only ever called with k >= 1
        assert k >= 1
        return float(site.rain.get(t - pd.Timedelta(days=k), nan))

    out: dict[str, float] = {}
    out["rain_3d_mm"] = sum(rain_on(k) for k in range(1, 4))
    out["rain_7d_mm"] = sum(rain_on(k) for k in range(1, 8))
    r1 = rain_on(1)
    out["heavy_rain_lag1"] = nan if np.isnan(r1) else float(r1 >= HEAVY_RAIN_MM)
    out["soil_moisture_m3m3"] = float(site.sm.get(t - pd.Timedelta(days=1), nan))

    window_start = t64 - ROLLING_DOWNTIME_WINDOW_DAYS * day
    down_hours = 0.0
    for s, e in zip(ev_start, ev_end):
        down_hours += _hours_between(max(s, window_start), min(e, t64))
    out["rolling_7d_downtime_pct"] = down_hours / (n_machines * ROLLING_DOWNTIME_WINDOW_DAYS * 24)

    today_hours = 0.0
    for s, e in zip(ev_start, ev_end):  # every event here started before t
        today_hours += _hours_between(t64, min(e, t64 + day))
    out["equipment_down_today_pct"] = today_hours / (n_machines * 24)

    last_by_machine: dict[str, np.datetime64] = {}
    for s, m, is_m in zip(ev_start, ev_machine, ev_is_maint):
        if is_m:
            d = s.astype("datetime64[D]").astype("datetime64[ns]")
            if m not in last_by_machine or d > last_by_machine[m]:
                last_by_machine[m] = d
    out["days_since_last_maintenance"] = (
        max(float((t64 - d) / day) for d in last_by_machine.values()) if last_by_machine else nan
    )

    b = 0.0
    for s in shortfall_hist:
        b = max(0.0, BACKLOG_DECAY * b + s)
    out["backlog_t"] = b

    delay_days: set[np.datetime64] = set()
    for planned, dur in zip(bl_planned, bl_days):
        for k in range(int(dur)):
            d = planned + k * day
            if d < t64:
                delay_days.add(d)
    lo = t64 - BLAST_LAG_WINDOW_DAYS * day
    out["blast_delay_days_lag"] = float(sum(1 for d in delay_days if d >= lo))
    return out


def _canary_variants(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Deliberately leaky versions of features; assert_no_lookahead must reject each."""
    return {
        "rain_3d_mm": frame["rain_3d_mm"] + frame["rain_today_mm"],  # window includes day t
        "backlog_t": frame["backlog_t"] + frame[TARGET_COLUMN],  # includes day t's own shortfall
        "rolling_7d_downtime_pct": frame["rolling_7d_downtime_pct"] + frame["equipment_down_today_pct"],
        "heavy_rain_lag1": (frame["rain_today_mm"] >= HEAVY_RAIN_MM).astype(float),  # today's rain, not t-1's
    }


def _check_frame(
    frame: pd.DataFrame, inputs: Inputs, n_machines: dict[str, int], features: list[str], stride: int = 1
) -> dict[str, int]:
    """Number of mismatching rows per feature, over every `stride`-th post-warm-up row per site."""
    mismatches = {f: 0 for f in features}
    checked = 0
    for site_id, site_frame in frame[~frame["in_warmup"]].groupby("site_id"):
        arrays = _SiteArrays(inputs, site_id)
        for row in site_frame.iloc[::stride].itertuples(index=False):
            ref = reference_features_at(arrays, row.date, n_machines[site_id])
            checked += 1
            for f in features:
                if not np.isclose(getattr(row, f), ref[f], rtol=1e-9, atol=1e-9, equal_nan=True):
                    mismatches[f] += 1
    mismatches["_rows_checked"] = checked
    return mismatches


def assert_no_lookahead(
    frame: pd.DataFrame, inputs: Inputs, n_machines: dict[str, int], verbose: bool = True, stride: int = 1
) -> dict:
    """Raise AssertionError unless every non-exempt feature for day t is
    reproducible from input rows dated strictly before t. Also proves the check
    is not vacuous by requiring it to reject deliberately leaky canaries."""
    real = _check_frame(frame, inputs, n_machines, HISTORY_FEATURES, stride)
    rows_checked = real.pop("_rows_checked")
    bad = {f: c for f, c in real.items() if c}
    assert not bad, f"LOOK-AHEAD LEAK: features disagree with the strictly-past reference: {bad}"

    # calendar encodings are functions of the date label alone
    d = frame["date"]
    assert np.allclose(frame["dow_sin"], np.sin(2 * np.pi * d.dt.dayofweek / 7))
    assert np.allclose(frame["month_cos"], np.cos(2 * np.pi * d.dt.month / 12))

    canary_results = {}
    for name, leaky in _canary_variants(frame).items():
        probe = frame[~frame["in_warmup"]].copy()
        probe[name] = leaky.loc[probe.index]
        # sample sparsely: enough to catch a systematic leak, keeps the self-test fast
        result = _check_frame(probe, inputs, n_machines, [name], stride=max(stride, 1) * 5)
        canary_results[name] = result[name]
        assert result[name] > 0, f"canary '{name}' was NOT flagged: the look-ahead check is vacuous"

    if verbose:
        print(
            f"  look-ahead check: {rows_checked} rows x {len(HISTORY_FEATURES)} history features "
            f"agree with the strictly-past reference (0 mismatches)"
        )
        print(f"  exempt by design: {list(LOOKAHEAD_EXEMPT_FEATURES)}; calendar encodings checked against the date label")
        print(f"  canaries rejected (mismatching rows flagged): {canary_results}")
    return {"rows_checked": rows_checked, "canaries_flagged": canary_results}
