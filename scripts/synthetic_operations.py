"""Synthetic operations data generator — extends production/downtime data to
2025-01-01..2026-09-22 and adds a causal structure driven by real satellite
rainfall (data/satellite_daily_features.csv via
oresight-backend/app/services/weather_history.py) instead of the purely
calendar-seasonal proxy generate_datasets.py used before.

STAGE 1 (this pass): equipment_downtime_log.csv only, via a per-machine
renewal process (scheduled maintenance + type-conditioned exponential
failures) independent of rainfall. production_history.csv and its causal
terms (rain lag, wet-pit, downtime-loss, backlog, blast-delay) are Stage 2
and land in this same file as a second pass.

Run: python -m scripts.synthetic_operations   (from repo root)
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CYPHER_SEED_PATH = REPO_ROOT / "seed_graph.cypher"

RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)

START_DATE = pd.Timestamp("2025-01-01")
END_DATE = pd.Timestamp("2026-09-22")

# ---------------------------------------------------------------------
# Equipment roster — parsed from seed_graph.cypher with the SAME regex as
# oresight-backend/scripts/import_p2_data.py's _parse_equipment_roster, so
# every equipment_id/site_id/type emitted here is guaranteed to match what
# backfill_equipment_status_log.py resolves against. Reimplemented (not
# imported) to keep this script free of a backend/DB import dependency,
# matching generate_datasets.py's existing style.
# ---------------------------------------------------------------------
_EQUIPMENT_BLOCK_RE = re.compile(r"CREATE\s*\(:Equipment\s*\{(?P<body>[^}]*)\}\)")
_FIELD_RE = re.compile(r"(\w+):\s*(?:'([^']*)'|datetime\('([^']*)'\))")


def parse_equipment_roster(cypher_path: Path = CYPHER_SEED_PATH) -> list[dict[str, str]]:
    text = cypher_path.read_text(encoding="utf-8")
    roster: list[dict[str, str]] = []
    for block in _EQUIPMENT_BLOCK_RE.finditer(text):
        fields: dict[str, str] = {}
        for fm in _FIELD_RE.finditer(block.group("body")):
            key = fm.group(1)
            value = fm.group(2) if fm.group(2) is not None else fm.group(3)
            fields[key] = value
        roster.append(fields)
    return roster


ROSTER = parse_equipment_roster()
EQUIPMENT_IDS = [e["id"] for e in ROSTER]
EQUIPMENT_TYPE_BY_ID = {e["id"]: e["type"] for e in ROSTER}
EQUIPMENT_SITE_BY_ID = {e["id"]: e["site_id"] for e in ROSTER}

# ======================================================================
# ASSUMPTION constants — equipment reliability model (STAGE 1)
# No real MOIL maintenance/failure-rate data is available yet. Every
# provisional constant governing the renewal process lives in this one
# block so it can be swapped for real figures later without hunting
# through the simulation logic below.
# ======================================================================

# Scheduled maintenance: every 30 +/- 5 days (uniform jitter), 2-8h each —
# matches oresight-backend/app/constants/equipment_assumptions.py's default
# EQUIPMENT_MAINTENANCE_INTERVAL_DAYS=30.
MAINTENANCE_INTERVAL_DAYS = (25.0, 35.0)  # uniform (low, high)
MAINTENANCE_DURATION_HOURS = (2.0, 8.0)  # uniform (low, high)
MAINTENANCE_REASON = "scheduled maintenance"

# ASSUMPTION: mean days between unscheduled failures, by equipment type
# (exponential inter-arrival gaps). Lower = less reliable. Ordering
# reflects duty-cycle intuition (Excavator/Loader see the heaviest
# continuous digging/hauling load; Compressor is the most reliable
# rotating equipment) -- not measured MOIL MTBF. Tuned so the resulting
# per-machine availability lands in TARGET_AVAILABILITY_LOW/HIGH below.
FAILURE_MTBF_DAYS_BY_TYPE = {
    "Excavator": 9.0,
    "Drill": 10.5,
    "Loader": 9.5,
    "Conveyor": 13.0,
    "Compressor": 14.0,
}

# ASSUMPTION: failure reason mix (weights, sum to 1.0) and per-reason
# duration range in hours (uniform). "spare parts unavailable" runs long
# (procurement/logistics wait); "operator shift gap" is short. Reason
# vocabulary matches
# oresight-backend/app/constants/equipment_assumptions.py::REASON_CATEGORIES
# exactly (excluding "scheduled maintenance", handled separately above).
FAILURE_REASONS: dict[str, dict] = {
    "mechanical failure": {"weight": 0.30, "duration_hours": (4.0, 72.0)},
    "weather delay": {"weight": 0.15, "duration_hours": (6.0, 48.0)},
    "electrical fault": {"weight": 0.15, "duration_hours": (2.0, 24.0)},
    "spare parts unavailable": {"weight": 0.15, "duration_hours": (24.0, 120.0)},
    "operator shift gap": {"weight": 0.15, "duration_hours": (1.0, 8.0)},
    "hydraulic leak": {"weight": 0.10, "duration_hours": (4.0, 48.0)},
}
ALLOWED_REASONS = {MAINTENANCE_REASON, *FAILURE_REASONS.keys()}
_REASON_NAMES = list(FAILURE_REASONS.keys())
_REASON_WEIGHTS = np.array([FAILURE_REASONS[r]["weight"] for r in _REASON_NAMES])
_REASON_WEIGHTS = _REASON_WEIGHTS / _REASON_WEIGHTS.sum()

# Target per-machine availability band this model is tuned to land in.
TARGET_AVAILABILITY_LOW = 0.80
TARGET_AVAILABILITY_HIGH = 0.92

# Machines deliberately left "overdue" for maintenance as of END_DATE
# (their last scheduled service predates the normal 30+/-5 day cadence by
# more than one interval). Count fixed by the plan; which 3 machines is an
# RNG draw from RNG_SEED, not a hardcoded ID list, so it tracks the roster.
N_OVERDUE_MACHINES = 3


# ---------------------------------------------------------------------
# Per-machine renewal-process simulation
# ---------------------------------------------------------------------
def _simulate_machine_events(
    eq_type: str, overdue: bool, machine_rng: np.random.Generator
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """Scheduled maintenance on a jittered ~30-day cadence, plus type-
    conditioned exponential-gap failures, with a failure shifted past any
    window it would otherwise collide with (maintenance or an
    earlier-placed failure) so no machine ever has two overlapping events.
    """
    occupied: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []

    # -- scheduled maintenance --
    cursor = START_DATE + pd.Timedelta(
        days=float(machine_rng.uniform(0, MAINTENANCE_INTERVAL_DAYS[1]))
    )
    maintenance_cutoff = (
        END_DATE
        - pd.Timedelta(days=float(machine_rng.uniform(1.5, 2.5) * MAINTENANCE_INTERVAL_DAYS[1]))
        if overdue
        else END_DATE
    )
    while cursor <= maintenance_cutoff:
        duration = float(machine_rng.uniform(*MAINTENANCE_DURATION_HOURS))
        down_start, down_end = cursor, cursor + pd.Timedelta(hours=duration)
        occupied.append((down_start, down_end, MAINTENANCE_REASON))
        cursor = down_start + pd.Timedelta(
            days=float(machine_rng.uniform(*MAINTENANCE_INTERVAL_DAYS))
        )

    # -- unscheduled failures --
    mtbf = FAILURE_MTBF_DAYS_BY_TYPE[eq_type]
    cursor = START_DATE + pd.Timedelta(days=float(machine_rng.exponential(mtbf)))
    while cursor <= END_DATE:
        reason = _REASON_NAMES[machine_rng.choice(len(_REASON_NAMES), p=_REASON_WEIGHTS)]
        duration = float(machine_rng.uniform(*FAILURE_REASONS[reason]["duration_hours"]))
        down_start, down_end = cursor, cursor + pd.Timedelta(hours=duration)

        moved, guard = True, 0
        while moved and guard < 50:
            moved = False
            for e_start, e_end, _ in occupied:
                if down_start < e_end and e_start < down_end:
                    shift = e_end - down_start
                    down_start += shift
                    down_end += shift
                    moved = True
            guard += 1

        if down_start <= END_DATE:
            occupied.append((down_start, down_end, reason))

        cursor = down_start + pd.Timedelta(days=float(machine_rng.exponential(mtbf)))

    occupied.sort(key=lambda e: e[0])
    return occupied


def generate_equipment_downtime_log() -> tuple[pd.DataFrame, set[str]]:
    overdue_ids = set(
        rng.choice(np.array(EQUIPMENT_IDS), size=N_OVERDUE_MACHINES, replace=False).tolist()
    )

    rows = []
    for eq_id in EQUIPMENT_IDS:
        eq_type = EQUIPMENT_TYPE_BY_ID[eq_id]
        site_id = EQUIPMENT_SITE_BY_ID[eq_id]
        machine_rng = np.random.default_rng(rng.integers(0, 2**32 - 1))
        events = _simulate_machine_events(eq_type, eq_id in overdue_ids, machine_rng)
        for down_start, down_end, reason in events:
            rows.append(
                {
                    "equipment_id": eq_id,
                    "site_id": site_id,
                    "down_start": down_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "down_end": down_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_hours": round((down_end - down_start).total_seconds() / 3600.0, 2),
                    "reason": reason,
                }
            )

    df = pd.DataFrame(rows).sort_values(["equipment_id", "down_start"]).reset_index(drop=True)
    _validate_downtime_log(df)
    return df, overdue_ids


# ---------------------------------------------------------------------
# Validation — CSV contract, zero self-overlaps, roster match
# ---------------------------------------------------------------------
def _validate_downtime_log(df: pd.DataFrame) -> None:
    expected_columns = ["equipment_id", "site_id", "down_start", "down_end", "duration_hours", "reason"]
    assert list(df.columns) == expected_columns, f"column mismatch: {list(df.columns)}"

    unknown_ids = set(df["equipment_id"]) - set(EQUIPMENT_IDS)
    assert not unknown_ids, f"equipment_id(s) not in seed_graph.cypher roster: {unknown_ids}"

    bad_reasons = set(df["reason"]) - ALLOWED_REASONS
    assert not bad_reasons, f"reason(s) outside the allowed vocabulary: {bad_reasons}"

    mismatched_site = df[df.apply(lambda r: EQUIPMENT_SITE_BY_ID[r["equipment_id"]] != r["site_id"], axis=1)]
    assert mismatched_site.empty, f"site_id doesn't match roster for rows:\n{mismatched_site}"

    starts = pd.to_datetime(df["down_start"])
    ends = pd.to_datetime(df["down_end"])
    assert (ends > starts).all(), "found down_end <= down_start"

    for eq_id, grp in df.groupby("equipment_id"):
        grp = grp.sort_values("down_start")
        g_starts = pd.to_datetime(grp["down_start"]).to_numpy()
        g_ends = pd.to_datetime(grp["down_end"]).to_numpy()
        assert (g_starts[1:] >= g_ends[:-1]).all(), f"self-overlap found for {eq_id}"


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------
def print_downtime_summary(df: pd.DataFrame, overdue_ids: set[str]) -> None:
    span_hours = ((END_DATE - START_DATE).days + 1) * 24

    print("=" * 78)
    print("equipment_downtime_log.csv -- Stage 1 regeneration summary")
    print("=" * 78)
    print(f"\nSpan: {START_DATE.date()} -> {END_DATE.date()}  ({span_hours // 24} days, {span_hours} hours)")
    print(f"Machines: {len(EQUIPMENT_IDS)}   Events: {len(df)}")

    print("\nPer-machine availability:")
    hours_by_machine = df.groupby("equipment_id")["duration_hours"].sum()
    out_of_band = []
    for eq_id in EQUIPMENT_IDS:
        down_hours = float(hours_by_machine.get(eq_id, 0.0))
        availability = 1 - down_hours / span_hours
        in_band = TARGET_AVAILABILITY_LOW <= availability <= TARGET_AVAILABILITY_HIGH
        if not in_band:
            out_of_band.append(eq_id)
        flags = []
        if eq_id in overdue_ids:
            flags.append("OVERDUE")
        if not in_band:
            flags.append("OUTSIDE 80-92% TARGET")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(
            f"  {eq_id:<10} ({EQUIPMENT_TYPE_BY_ID[eq_id]:<10}) "
            f"down={down_hours:8.1f}h  availability={availability:6.1%}{flag_str}"
        )

    print("\nReason-code distribution:")
    print(df["reason"].value_counts().to_string())

    print("\nDays-since-last-maintenance at END_DATE:")
    maint = df[df["reason"] == MAINTENANCE_REASON]
    for eq_id in EQUIPMENT_IDS:
        m = maint[maint["equipment_id"] == eq_id]
        flag = " [OVERDUE]" if eq_id in overdue_ids else ""
        if m.empty:
            print(f"  {eq_id}: no maintenance events{flag}")
            continue
        last = pd.to_datetime(m["down_start"]).max()
        days_since = (END_DATE - last).days
        print(f"  {eq_id}: last service {last.date()}, {days_since}d ago{flag}")

    print(f"\nOverdue machines ({len(overdue_ids)}): {sorted(overdue_ids)}")
    print(f"Machines outside 80-92% availability target: {out_of_band or 'none'}")
    print("\nValidation: zero self-overlaps -- OK (asserted in _validate_downtime_log)")
    print("Validation: CSV contract (columns/reasons/down_end>down_start/roster match) -- OK")
    print("=" * 78)


# ======================================================================
# STAGE 2 -- CAUSAL PRODUCTION MODEL
# ======================================================================
# Replaces the old cause-free production series (a weekly-drift target
# with independent noise, plus a handful of randomly-placed "shortfall
# injection" windows with no driving cause) with one where each day's loss
# is the SUM of four documented causal terms -- rain, equipment downtime
# (read from the Stage 1 log above, never re-simulated), accumulated
# backlog, and delayed blasts -- so a model trained on this data can
# actually learn the relationships the Simulator agent claims to
# simulate. Nothing here is tuned to make a model look good; it's tuned
# so the data has honest, checkable structure.
#
#   actual_t = target_t * (1 - loss_t) * (1 + eps),  eps ~ N(0, PRODUCTION_NOISE_SD)
#   loss_t   = min(LOSS_CAP, loss_rain_t + loss_downtime_t + loss_backlog_t + loss_blast_t)
#
# target_t keeps generate_datasets.py's original weekly-random-walk drift
# unchanged. There is no separate monsoon-dip constant any more --
# monsoon seasonality now emerges from the real CHIRPS/IMERG rainfall
# series via loss_rain, not an artificial calendar multiplier.

import hashlib
import json
import sys

MOIL_SITES_PATH = DATA_DIR / "moil_sites.json"
BACKEND_ROOT = REPO_ROOT / "oresight-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_site_config() -> dict[str, dict]:
    data = json.loads(MOIL_SITES_PATH.read_text(encoding="utf-8"))
    return {s["key"]: s for s in data["sites"]}


SITE_CONFIG = _load_site_config()
SITE_IDS = list(SITE_CONFIG.keys())  # moil_sites.json order: balaghat, nagpur, bhandara

# ======================================================================
# ASSUMPTION constants -- causal production model (STAGE 2)
# No real MOIL production-loss figures exist yet; every provisional
# constant below is a documented placeholder, kept in this one block so a
# mentor's pushback means changing a number here, not hunting through the
# simulation code that uses it.
# ======================================================================

PRODUCTION_NOISE_SD = 0.03  # ASSUMPTION: 3% day-to-day output noise, independent of any causal term (measurement/operational jitter)
LOSS_CAP = 0.9  # ASSUMPTION: a maximal compound-bad-day still leaves >=10% of target achievable

# -- 1. RAIN (real CHIRPS/IMERG per site via weather_history.py -- never a cosine/climatology proxy) --
RAIN_LAG1_COEF = 0.004  # ASSUMPTION: mm of R_{t-1} -> loss. A 50mm day costs ~20% of next day's output (0.004*50=0.20)
RAIN_LAG2_COEF = 0.002  # ASSUMPTION: mm of R_{t-2} -> loss; half the lag-1 weight, a fading one-day-later effect
RAIN_LAG_CAP_MM = 50.0  # ASSUMPTION: per-day rain contribution saturates above 50mm -- a soaked pit doesn't get proportionally worse
WET_PIT_ROLLING_DAYS = 3  # rolling window (t-1..t-3) checked for the wet-pit trigger, same window used by the blast-delay rain gate below
WET_PIT_THRESHOLD_MM = 60.0  # ASSUMPTION: 3-day rain total above which pit ACCESS itself (not just haul-road slowdown) becomes the binding constraint
WET_PIT_LOSS = 0.08  # ASSUMPTION: flat wet-pit loss add-on once triggered -- "two consecutive heavy days keep costing ~8%"

# -- 2. DOWNTIME (reads equipment_downtime_log.csv written by Stage 1 above; never re-simulated, never re-draws that RNG) --
DOWNTIME_LOSS_WEIGHTS_BY_TYPE = {
    # ASSUMPTION: relative production impact of one full day of a given
    # equipment class being down, e.g. one Excavator down all day costs
    # 10% of that site's target. The 4 extra Bhandara BHD-2 units
    # (eq_bhd_06..09) map to the SAME weight as their class -- an
    # additional unit of that class, not a different one -- which means
    # Bhandara's site-level downtime loss saturates against
    # DOWNTIME_LOSS_CAP less easily than the 5-machine sites for the same
    # single-machine failure, since it carries more spare capacity per
    # class. That's a real, physically-correct emergent property of
    # having 9 machines instead of 5, not special-cased for Bhandara.
    #
    # CALIBRATION NOTE: the first pass used 0.30/0.20/0.15/0.25/0.10 (each
    # weight = "share of target lost if that class is down all day",
    # summing to 1.0 across one of each type). Combined with Stage 1's
    # realistic 80-92% per-machine availability (~14% mean per-machine
    # downtime), that summed to a 16.85pp mean downtime-loss contribution
    # BY ITSELF -- already exceeding the entire 12-14% target band before
    # rain/backlog/blast were even added, because linearly summing
    # per-machine weighted downtime with weights totaling ~1.0 against a
    # ~14%-down machine fleet mechanically produces ~14% expected loss
    # from this term alone. Those original weights were sized for a much
    # lower downtime frequency than the equipment reliability model this
    # module now generates; scaled down by 1/3 here so downtime keeps its
    # relative per-class ordering but contributes a plausible SHARE of
    # total loss (see STAGE 2 report: ~43% of the 13.4% mean) instead of
    # dwarfing the other three causal terms combined.
    "Excavator": 0.100,
    "Loader": 0.067,
    "Drill": 0.050,
    "Conveyor": 0.083,
    "Compressor": 0.033,
}
DOWNTIME_LOSS_CAP = 0.6  # ASSUMPTION: no single machine failure alone can zero a site's output

# -- 3. BACKLOG --
BACKLOG_DECAY = 0.85  # ASSUMPTION: 15%/day backlog decay -- a catch-up effort works off most of a backlog within 1-2 weeks
BACKLOG_LOSS_COEF = 0.02  # ASSUMPTION: backlog RAISES loss. Sign is deliberate: a site under catch-up
# pressure runs fatigued crews and cuts corners, so accumulated backlog measurably HURTS the next
# day's output rather than being "worked off" for free. This is the least intuitive term in the
# model and the one most likely to get challenged -- if MOIL's real operational data shows the
# opposite (backlog pressure improving short-term throughput at the cost of quality/safety
# elsewhere), this coefficient's sign should flip, not just its magnitude.
#
# CALIBRATION NOTE: backlog->loss->shortfall->backlog is a feedback loop with
# gain BACKLOG_LOSS_COEF / (1 - BACKLOG_DECAY). The first pass used 0.10,
# giving gain 0.10/0.15 = 0.667 -- close enough to 1.0 that the loop
# AMPLIFIES total external loss (rain+downtime+blast) by 1/(1-0.667) = 3x.
# With downtime alone at ~16.85pp pre-calibration, that amplification
# alone produced a 60.6% mean loss. 0.02 gives gain 0.02/0.15 = 0.133 ->
# a modest 1.15x amplification, which is what "backlog is a secondary
# compounding factor" should mean -- not a 3x multiplier on everything
# else in the model.
BACKLOG_WARMUP_DAYS = 14  # informational only: ~14-18 days for backlog to approach steady state under BACKLOG_DECAY; not excluded from the data, just noted as low-signal early rows

# -- 4. DELAYED BLASTS --
BLAST_DELAY_PROB_BASELINE = 0.03  # ASSUMPTION: daily probability a blast gets delayed, dry conditions
BLAST_DELAY_PROB_RAIN_ELEVATED = 0.08  # ASSUMPTION: daily probability when the rolling rain gate below fires
BLAST_DELAY_RAIN_ROLLING_DAYS = 3
BLAST_DELAY_RAIN_THRESHOLD_MM = 40.0  # ASSUMPTION: lower bar than WET_PIT_THRESHOLD_MM -- a blast plan is disrupted by less rain than it takes to shut the pit itself
BLAST_DELAY_DURATION_DAYS = (1, 4)  # ASSUMPTION: uniform integer 1-4 day delays
BLAST_DELAY_EFFECT_LOSS = 0.06  # ASSUMPTION: each delay-day adds this much loss on each of the following BLAST_DELAY_EFFECT_WINDOW_DAYS days
BLAST_DELAY_EFFECT_WINDOW_DAYS = 5  # forward-looking ONLY -- a delayed blast cuts FUTURE tonnage, never today's

# BlastDelayReason values -- mirrors oresight-backend/app/models/blast_event.py's
# BlastDelayReason enum (.value strings), reimplemented as plain constants
# rather than imported so this CSV generator stays free of the backend's
# DB/settings import chain (same reasoning as the equipment-roster parser
# above). Keep in sync if that enum changes.
BLAST_REASON_WEATHER_HOLD = "weather_hold"
BLAST_REASON_OTHER = ["permit_pending", "safety_hold", "equipment_unavailable", "explosive_supply"]
# ASSUMPTION: the non-weather delay reasons are equally likely (25% each) -- no real MOIL
# permit/safety/supply-chain incident-rate data exists yet.

PRODUCTION_RNG_SEED = 43
# Separate stream from the downtime generator's RNG_SEED=42 above, so
# re-running Stage 1 alone never perturbs Stage 2's draws (or vice
# versa). Distinct from generate_datasets.py's DEPOSIT_RNG_SEED=2026,
# which this module never touches -- deposit_ground_truth.csv's
# generation uses its own isolated np.random.default_rng and is
# unaffected by anything in this module.


# ---------------------------------------------------------------------
# Rain series (via the Stage 1 weather loader)
# ---------------------------------------------------------------------
def _load_rain_series() -> tuple[dict[str, "pd.Series"], dict[str, "pd.Series"], int]:
    """Returns (rain_mm_by_site, rain_source_by_site, total_missing_days)."""
    from app.services.weather_history import MISSING_SOURCE, load_rainfall_history

    rain_df = load_rainfall_history(SITE_IDS, START_DATE.date(), END_DATE.date())
    rain_mm_by_site = {}
    rain_source_by_site = {}
    for s in SITE_IDS:
        site_df = rain_df[rain_df["site_id"] == s].set_index("date")
        rain_mm_by_site[s] = site_df["rainfall_mm"]
        rain_source_by_site[s] = site_df["rain_source"]
    total_missing = int((rain_df["rain_source"] == MISSING_SOURCE).sum())
    return rain_mm_by_site, rain_source_by_site, total_missing


def _rain_on(rain_series: pd.Series, date: pd.Timestamp) -> float:
    """Rain on `date`, or 0.0 if it's outside the series' range or NaN/missing.
    Per the plan: a missing/out-of-range day contributes 0.0, never invented
    or interpolated -- genuinely missing days are separately counted."""
    val = rain_series.get(date)
    if val is None or pd.isna(val):
        return 0.0
    return float(val)


def _rolling_rain(rain_series: pd.Series, date: pd.Timestamp, lookback_days: int) -> float:
    return sum(_rain_on(rain_series, date - pd.Timedelta(days=k)) for k in range(1, lookback_days + 1))


# ---------------------------------------------------------------------
# Downtime loss (reads Stage 1's CSV from disk; does not regenerate it)
# ---------------------------------------------------------------------
def _load_downtime_events() -> pd.DataFrame:
    path = DATA_DIR / "equipment_downtime_log.csv"
    return pd.read_csv(path, parse_dates=["down_start", "down_end"])


def _compute_downtime_loss_by_site(
    downtime_df: pd.DataFrame, date_index: pd.DatetimeIndex
) -> dict[str, pd.Series]:
    loss = {s: pd.Series(0.0, index=date_index) for s in SITE_IDS}
    for row in downtime_df.itertuples(index=False):
        eq_type = EQUIPMENT_TYPE_BY_ID.get(row.equipment_id)
        weight = DOWNTIME_LOSS_WEIGHTS_BY_TYPE.get(eq_type)
        if weight is None or row.site_id not in loss:
            continue
        start, end = row.down_start, row.down_end
        day = start.normalize()
        last_day = end.normalize()
        while day <= last_day:
            day_start, day_end = day, day + pd.Timedelta(days=1)
            overlap_start, overlap_end = max(start, day_start), min(end, day_end)
            overlap_hours = max(0.0, (overlap_end - overlap_start).total_seconds() / 3600.0)
            if overlap_hours > 0 and day in loss[row.site_id].index:
                loss[row.site_id].loc[day] += (overlap_hours / 24.0) * weight
            day += pd.Timedelta(days=1)
    for s in SITE_IDS:
        loss[s] = loss[s].clip(upper=DOWNTIME_LOSS_CAP)
    return loss


# ---------------------------------------------------------------------
# Delayed blasts
# ---------------------------------------------------------------------
def _generate_blast_events(
    site_id: str,
    date_index: pd.DatetimeIndex,
    rain_series: pd.Series,
    production_rng: np.random.Generator,
) -> tuple[list[dict], pd.Series]:
    blast_loss = pd.Series(0.0, index=date_index)
    records: list[dict] = []
    in_delay_until: pd.Timestamp | None = None

    for day in date_index:
        if in_delay_until is not None and day < in_delay_until:
            continue

        rolling3 = _rolling_rain(rain_series, day, BLAST_DELAY_RAIN_ROLLING_DAYS)
        weather_triggered = rolling3 >= BLAST_DELAY_RAIN_THRESHOLD_MM
        p_delay = BLAST_DELAY_PROB_RAIN_ELEVATED if weather_triggered else BLAST_DELAY_PROB_BASELINE

        if production_rng.random() >= p_delay:
            continue

        duration = int(
            production_rng.integers(BLAST_DELAY_DURATION_DAYS[0], BLAST_DELAY_DURATION_DAYS[1] + 1)
        )
        reason = (
            BLAST_REASON_WEATHER_HOLD
            if weather_triggered
            else BLAST_REASON_OTHER[production_rng.integers(0, len(BLAST_REASON_OTHER))]
        )

        delay_days = [day + pd.Timedelta(days=k) for k in range(duration)]
        records.append(
            {
                "site_id": site_id,
                "planned_date": day.strftime("%Y-%m-%d"),
                "delay_days": duration,
                "delay_reason": reason,
                "weather_triggered": weather_triggered,
            }
        )
        for d in delay_days:
            for k in range(1, BLAST_DELAY_EFFECT_WINDOW_DAYS + 1):
                effect_day = d + pd.Timedelta(days=k)
                assert effect_day > d, "blast effect landed on/before the delay day itself"
                if effect_day in blast_loss.index:
                    blast_loss.loc[effect_day] += BLAST_DELAY_EFFECT_LOSS

        in_delay_until = day + pd.Timedelta(days=duration)

    return records, blast_loss


# ---------------------------------------------------------------------
# Target series (unchanged weekly-random-walk drift from the old generator)
# ---------------------------------------------------------------------
def _compute_target_series(
    site_id: str, date_index: pd.DatetimeIndex, production_rng: np.random.Generator
) -> pd.Series:
    base_target = float(SITE_CONFIG[site_id]["target_output"])
    n_weeks = int(np.ceil(len(date_index) / 7)) + 1
    weekly_drift = production_rng.normal(0, 0.03, n_weeks).cumsum()
    weekly_drift = np.clip(weekly_drift, -0.12, 0.12)
    daily_drift = np.repeat(weekly_drift, 7)[: len(date_index)]
    return pd.Series(base_target * (1 + daily_drift), index=date_index)


# ---------------------------------------------------------------------
# Sequential per-site simulation (backlog is a true recursion; everything
# else here is precomputed and just looked up day by day)
# ---------------------------------------------------------------------
def _simulate_site_production(
    site_id: str,
    date_index: pd.DatetimeIndex,
    target_series: pd.Series,
    rain_series: pd.Series,
    downtime_loss_series: pd.Series,
    blast_loss_series: pd.Series,
    production_rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    backlog_state = 0.0  # backlog_0 = 0.0
    prev_shortfall = 0.0  # no day-0 shortfall exists to carry into day 1

    for t in date_index:
        backlog_t = max(0.0, BACKLOG_DECAY * backlog_state + prev_shortfall)
        loss_backlog = BACKLOG_LOSS_COEF * backlog_t

        r1 = _rain_on(rain_series, t - pd.Timedelta(days=1))
        r2 = _rain_on(rain_series, t - pd.Timedelta(days=2))
        loss_rain = RAIN_LAG1_COEF * min(r1, RAIN_LAG_CAP_MM) + RAIN_LAG2_COEF * min(r2, RAIN_LAG_CAP_MM)
        if _rolling_rain(rain_series, t, WET_PIT_ROLLING_DAYS) > WET_PIT_THRESHOLD_MM:
            loss_rain += WET_PIT_LOSS

        loss_downtime = float(downtime_loss_series.get(t, 0.0))
        loss_blast = float(blast_loss_series.get(t, 0.0))

        loss_t = min(LOSS_CAP, loss_rain + loss_downtime + loss_backlog + loss_blast)

        eps = float(production_rng.normal(0, PRODUCTION_NOISE_SD))
        target_t = float(target_series.loc[t])
        actual_t = max(0.0, target_t * (1 - loss_t) * (1 + eps))

        shortfall_t = (target_t - actual_t) / target_t

        rows.append(
            {
                "site_id": site_id,
                "date": t.strftime("%Y-%m-%d"),
                "actual_output": round(actual_t, 1),
                "target_output": round(target_t, 1),
                "backlog": round(backlog_t, 5),
                "loss_rain": round(loss_rain, 5),
                "loss_downtime": round(loss_downtime, 5),
                "loss_backlog": round(loss_backlog, 5),
                "loss_blast": round(loss_blast, 5),
                "loss_total": round(loss_t, 5),
            }
        )

        backlog_state = backlog_t
        prev_shortfall = shortfall_t

    return pd.DataFrame(rows)


def _validate_production_history(df: pd.DataFrame) -> None:
    assert (df["actual_output"] >= 0).all(), "negative actual_output found"
    assert df["loss_total"].between(0, LOSS_CAP).all(), "loss_total outside [0, LOSS_CAP]"
    na_counts = df.isna().sum()
    assert not na_counts.any(), f"NaN found in production_history.csv: {na_counts[na_counts > 0].to_dict()}"

    expected_days = (END_DATE - START_DATE).days + 1
    expected_rows = len(SITE_IDS) * expected_days
    assert len(df) == expected_rows, f"expected {expected_rows} rows, got {len(df)}"

    dup = df.duplicated(subset=["site_id", "date"])
    assert not dup.any(), f"duplicate (site_id, date) pairs found"

    date_counts = df.groupby("site_id")["date"].nunique()
    for site_id, count in date_counts.items():
        assert count == expected_days, f"{site_id} has {count} unique dates, expected {expected_days} (date gap?)"

    assert (df["backlog"] >= 0).all(), "negative backlog found"


def generate_production_history() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """STAGE 2 causal production generator. Reads equipment_downtime_log.csv
    (already written by Stage 1; never re-simulated) and real CHIRPS/IMERG
    rainfall via weather_history.load_rainfall_history. Writes
    production_history.csv with the original 4-column contract (site_id,
    date, actual_output, target_output) plus 6 new diagnostic columns:
    backlog, loss_rain, loss_downtime, loss_backlog, loss_blast, loss_total.

    Also returns blast_df: a new artifact (data/blast_events.csv) -- there
    was previously no seeding path for blast delays at all -- with columns
    site_id, planned_date, delay_days, delay_reason, weather_triggered.
    """
    date_index = pd.date_range(START_DATE, END_DATE, freq="D")
    production_rng = np.random.default_rng(PRODUCTION_RNG_SEED)

    rain_mm_by_site, rain_source_by_site, rain_missing_total = _load_rain_series()
    downtime_df = _load_downtime_events()
    downtime_loss_by_site = _compute_downtime_loss_by_site(downtime_df, date_index)

    all_rows = []
    all_blast_records = []
    diagnostics = {
        "rain_missing_total": rain_missing_total,
        "rain_missing_by_site": {},
        "wet_pit_days_by_site": {},
    }

    for site_id in SITE_IDS:
        target_series = _compute_target_series(site_id, date_index, production_rng)
        rain_series = rain_mm_by_site[site_id]

        blast_records, blast_loss_series = _generate_blast_events(
            site_id, date_index, rain_series, production_rng
        )
        all_blast_records.extend(blast_records)

        site_df = _simulate_site_production(
            site_id,
            date_index,
            target_series,
            rain_series,
            downtime_loss_by_site[site_id],
            blast_loss_series,
            production_rng,
        )
        all_rows.append(site_df)

        diagnostics["rain_missing_by_site"][site_id] = int(
            (rain_source_by_site[site_id] == "missing").sum()
        )
        diagnostics["wet_pit_days_by_site"][site_id] = sum(
            1 for t in date_index if _rolling_rain(rain_series, t, WET_PIT_ROLLING_DAYS) > WET_PIT_THRESHOLD_MM
        )

    production_df = pd.concat(all_rows, ignore_index=True)
    blast_df = pd.DataFrame(
        all_blast_records,
        columns=["site_id", "planned_date", "delay_days", "delay_reason", "weather_triggered"],
    )

    _validate_production_history(production_df)

    return production_df, blast_df, diagnostics


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def print_production_summary(production_df: pd.DataFrame, blast_df: pd.DataFrame, diagnostics: dict) -> None:
    print("=" * 78)
    print("production_history.csv -- Stage 2 causal regeneration summary")
    print("=" * 78)

    mean_total = production_df["loss_total"].mean()
    mean_rain = production_df["loss_rain"].mean()
    mean_downtime = production_df["loss_downtime"].mean()
    mean_backlog = production_df["loss_backlog"].mean()
    mean_blast = production_df["loss_blast"].mean()

    print(f"\nSpan: {START_DATE.date()} -> {END_DATE.date()}  ({len(production_df)} rows, {len(SITE_IDS)} sites)")
    print(f"\nOverall mean loss: {mean_total:.2%}  (target band 12-14%, hard stop band 10-16%)")

    print("\nCausal term contributions (share of mean total loss / absolute pp of target):")
    for name, val in [
        ("rain", mean_rain),
        ("downtime", mean_downtime),
        ("backlog", mean_backlog),
        ("blast delay", mean_blast),
    ]:
        share = val / mean_total if mean_total else float("nan")
        print(f"  {name:<12}: {share:6.1%} of total loss   ({val * 100:5.2f}pp of target)")
    component_sum = mean_rain + mean_downtime + mean_backlog + mean_blast
    print(
        f"  {'sum of components':<12}: {component_sum * 100:5.2f}pp vs mean_total {mean_total * 100:5.2f}pp "
        f"(gap = LOSS_CAP binding on high-loss days)"
    )

    print("\nBlast delay events:")
    if blast_df.empty:
        print("  none generated")
    else:
        print(blast_df.groupby(["site_id", "delay_reason"]).size().to_string())
        print(f"  total events: {len(blast_df)}   total delay-days: {int(blast_df['delay_days'].sum())}")

    print("\nWet-pit trigger days (3-day rain > 60mm) by site:")
    for s in SITE_IDS:
        print(f"  {s}: {diagnostics['wet_pit_days_by_site'][s]}")

    print(f"\nrain_missing_days total: {diagnostics['rain_missing_total']}")
    for s in SITE_IDS:
        print(f"  {s}: {diagnostics['rain_missing_by_site'][s]}")

    print("\nPer-site mean loss and mean actual/target ratio:")
    for s in SITE_IDS:
        site_rows = production_df[production_df["site_id"] == s]
        ratio = (site_rows["actual_output"] / site_rows["target_output"]).mean()
        print(f"  {s:<10}: mean loss={site_rows['loss_total'].mean():.2%}   mean actual/target={ratio:.2%}")

    print("\nLoss distribution:")
    print(
        f"  min={production_df['loss_total'].min():.4f}  max={production_df['loss_total'].max():.4f}  "
        f"std={production_df['loss_total'].std():.4f}"
    )
    at_cap = int((production_df["loss_total"] >= LOSS_CAP - 1e-9).sum())
    print(f"  days at/above cap ({LOSS_CAP}): {at_cap}  ({at_cap / len(production_df):.2%})")
    print("=" * 78)


def main() -> None:
    df, overdue_ids = generate_equipment_downtime_log()
    path = DATA_DIR / "equipment_downtime_log.csv"
    df.to_csv(path, index=False)
    print_downtime_summary(df, overdue_ids)
    print(f"\nWrote {len(df)} rows to {path}")

    production_df, blast_df, diagnostics = generate_production_history()
    production_path = DATA_DIR / "production_history.csv"
    blast_path = DATA_DIR / "blast_events.csv"
    production_df.to_csv(production_path, index=False)
    blast_df.to_csv(blast_path, index=False)
    print_production_summary(production_df, blast_df, diagnostics)
    print(f"\nWrote {len(production_df)} rows to {production_path}")
    print(f"Wrote {len(blast_df)} rows to {blast_path}")


if __name__ == "__main__":
    main()
