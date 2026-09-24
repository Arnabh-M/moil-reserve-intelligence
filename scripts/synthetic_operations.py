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


def main() -> None:
    df, overdue_ids = generate_equipment_downtime_log()
    path = DATA_DIR / "equipment_downtime_log.csv"
    df.to_csv(path, index=False)
    print_downtime_summary(df, overdue_ids)
    print(f"\nWrote {len(df)} rows to {path}")


if __name__ == "__main__":
    main()
