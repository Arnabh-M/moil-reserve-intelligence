"""Inference-time feature vector for the shortfall forecaster, built from live sources.

The trained model (see shortfall_feature_engineering.py at the repo root for the
authoritative definition of every feature) takes one row per site per day t, computed
from history STRICTLY BEFORE t (rain_today_mm is the single, deliberate exception).
This module rebuilds that row for the API:

  rain_*, heavy_rain_lag1   data/satellite_daily_features.csv (CHIRPS/IMERG), then
                            weather_history's existing Open-Meteo archive fallback for
                            dates the CSV does not have
  soil_moisture_m3m3        the same CSV (SMAP); no fallback source exists, so a date SMAP
                            has not delivered yet is NaN
  rolling_7d_downtime_pct,  equipment_status_log (outages reconstructed from its down/up rows)
  equipment_down_today_pct,
  days_since_last_maintenance
  backlog_t                 production_records (decayed cumulative unmet tonnage)
  blast_delay_days_lag      blast_events, through the SAME function training calls
                            (app.services.shortfall_features.blast_delay_days_lag)
  dow_*, month_*            the calendar date

NOTHING IS INVENTED. A value no source can supply is NaN (XGBoost handles NaN natively) and is
listed in `LiveFeatures.missing`; there is no imputation, carry-forward or default. Note the model
never saw NaN in the features it was trained on for soil moisture, so a NaN there is a
(low-importance, 0.017) departure from its training distribution: see LIMITATIONS in the
Simulator module docstring.

AS-OF DATE. The row is for a calendar day t. With as_of=None t is the latest FINISHED day (yesterday
or earlier) whose own rain and previous seven days of rain are all observed (the satellite record lags
~1-3 days, so that is usually 1-3 days before today). It is reported to the caller, never hidden. An explicit
as_of (used by the parity test and the sweep) is honoured as given, with missing inputs -> NaN.

TRAINING/INFERENCE PARITY is machine-checked by tests/test_live_feature_parity.py: for sampled
(site, date) pairs the live row must equal the training frame's row. There is deliberately no
second copy of blast_delay_days_lag; the others are re-implemented here (the training versions are
vectorised over a whole frame) and held to the training frame by that test.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EquipmentStatusLog, ProductionRecord, Site
from app.services.blast_features import blast_delay_events_for_site
from app.services.shortfall_features import blast_delay_days_lag

logger = logging.getLogger("oresight.live_features")

NAN = float("nan")

# The fallback (Open-Meteo archive) is a network call on a request path: bound how long it can stall
# an API call, and do not re-ask for a date it just failed to supply.
FALLBACK_HTTP_TIMEOUT_SECONDS = 5.0
FALLBACK_RETRY_AFTER_SECONDS = 30 * 60
AS_OF_LOOKBACK_DAYS = 30

RainLookup = Callable[[str, date, date], dict[date, float]]


class LiveDataUnavailableError(RuntimeError):
    """A live input the forecaster cannot run without is not available (as opposed to a single
    missing value, which is passed to the model as NaN)."""


@dataclass(frozen=True)
class FeatureConstants:
    """The feature definitions' constants, carried in model_metrics.json so they travel with the
    artifact (written by train_shortfall_model.py from shortfall_feature_engineering.py, which
    stays their single source)."""

    machines_per_site: dict[str, int]
    heavy_rain_mm: float
    backlog_decay: float
    rolling_downtime_window_days: int
    maintenance_reason: str

    @classmethod
    def from_metrics(cls, metrics: dict) -> "FeatureConstants":
        raw = metrics.get("feature_constants")
        if not raw:
            raise LiveDataUnavailableError(
                "model_metrics.json has no feature_constants: the artifact predates them. "
                "Retrain with train_shortfall_model.py (--ship to install)."
            )
        return cls(
            machines_per_site={k: int(v) for k, v in raw["machines_per_site"].items()},
            heavy_rain_mm=float(raw["heavy_rain_mm"]),
            backlog_decay=float(raw["backlog_decay"]),
            rolling_downtime_window_days=int(raw["rolling_downtime_window_days"]),
            maintenance_reason=str(raw["maintenance_reason"]),
        )


@dataclass
class LiveFeatures:
    site_key: str
    as_of: date
    values: dict[str, float]
    rain_lag1_mm: float  # rain on as_of-1 (NaN if unobserved). Not a model input; scenario perturbation needs it.
    blast_events: list[tuple[date, int]]  # inputs of blast_delay_days_lag, for the scenario perturbation
    n_machines: int
    constants: FeatureConstants
    missing: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Rain: satellite CSV, then weather_history's Open-Meteo fallback
# ---------------------------------------------------------------------
_fallback_failed_at: dict[tuple[str, date], float] = {}


def satellite_rain_lookup(site_key: str, start: date, end: date) -> dict[date, float]:
    """Observed daily rain (mm) in [start, end], as {date: mm}. A date no source has is ABSENT."""
    try:
        from app.services import weather_history  # lazy: it reads data/ at import time
    except Exception as exc:  # noqa: BLE001 - e.g. data dir not mounted in the container
        raise LiveDataUnavailableError(
            f"The satellite rainfall record could not be loaded ({exc}). Set MOIL_DATA_DIR to the repo's data/ folder."
        ) from exc

    frame = weather_history.load_rainfall_history([site_key], start, end, use_fallback=False)
    observed = {row.date.date(): float(row.rainfall_mm) for row in frame.itertuples() if not math.isnan(row.rainfall_mm)}

    now = time.monotonic()
    gaps = [
        d
        for d in (start + timedelta(days=k) for k in range((end - start).days + 1))
        if d not in observed and now - _fallback_failed_at.get((site_key, d), -math.inf) > FALLBACK_RETRY_AFTER_SECONDS
    ]
    if gaps:
        filled = weather_history.load_rainfall_history(
            [site_key], min(gaps), max(gaps), http_timeout=FALLBACK_HTTP_TIMEOUT_SECONDS
        )
        wanted = set(gaps)
        for row in filled.itertuples():
            d = row.date.date()
            if d not in wanted:
                continue
            if math.isnan(row.rainfall_mm):
                _fallback_failed_at[(site_key, d)] = now
            else:
                observed[d] = float(row.rainfall_mm)
    return observed


def resolve_as_of(site_key: str, today: date, rain_lookup: RainLookup) -> tuple[date, dict[date, float]]:
    """Latest day d <= today whose own rain and the seven days before it are all observed."""
    observed = rain_lookup(site_key, today - timedelta(days=AS_OF_LOOKBACK_DAYS + 7), today)
    d = today
    for _ in range(AS_OF_LOOKBACK_DAYS + 1):
        if all((d - timedelta(days=k)) in observed for k in range(8)):
            return d, observed
        d -= timedelta(days=1)
    raise LiveDataUnavailableError(
        f"No day in the last {AS_OF_LOOKBACK_DAYS} days up to {today} has a complete observed rain window "
        f"for {site_key}: the satellite rainfall record has stopped updating."
    )


def _rain_sum(observed: dict[date, float], as_of: date, first_lag: int, last_lag: int) -> float:
    days = [as_of - timedelta(days=k) for k in range(first_lag, last_lag + 1)]
    return sum(observed[d] for d in days) if all(d in observed for d in days) else NAN


# ---------------------------------------------------------------------
# Equipment downtime, from equipment_status_log
# ---------------------------------------------------------------------
def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def reconstruct_outages(rows: Iterable[EquipmentStatusLog]) -> list[tuple[datetime, datetime | None, str | None, int]]:
    """(start, end or None, reason, equipment_id) per outage: a `down` row opens one and the next
    non-down row for that machine closes it. An outage with no closing row is still running (end None).
    Times are naive UTC, as in equipment_downtime_log.csv."""
    by_machine: dict[int, list[EquipmentStatusLog]] = defaultdict(list)
    for row in rows:
        by_machine[row.equipment_id].append(row)
    outages: list[tuple[datetime, datetime | None, str | None, int]] = []
    for equipment_id, events in by_machine.items():
        events.sort(key=lambda r: (r.changed_at, r.id))
        opened: EquipmentStatusLog | None = None
        for row in events:
            if row.new_status == "down":
                opened = opened or row  # a repeated `down` does not restart the outage
            elif opened is not None:
                outages.append((_utc_naive(opened.changed_at), _utc_naive(row.changed_at), opened.reason, equipment_id))
                opened = None
        if opened is not None:
            outages.append((_utc_naive(opened.changed_at), None, opened.reason, equipment_id))
    return outages


def _hours(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 3600.0)


def downtime_features(
    outages: list[tuple[datetime, datetime | None, str | None, int]],
    as_of: date,
    n_machines: int,
    constants: FeatureConstants,
) -> tuple[float, float, float]:
    """(rolling_7d_downtime_pct, equipment_down_today_pct, days_since_last_maintenance) at the start
    of `as_of`, from outages that STARTED BEFORE it (the definitions in shortfall_feature_engineering).
    An outage still running (no return time yet) is assumed to last the rest of the day."""
    t = datetime(as_of.year, as_of.month, as_of.day)
    day = timedelta(days=1)
    window = constants.rolling_downtime_window_days
    window_start = t - window * day
    rolling_hours = today_hours = 0.0
    last_maintenance: dict[int, date] = {}
    for start, end, reason, equipment_id in outages:
        if start >= t:
            continue
        end_eff = end if end is not None else t + day
        rolling_hours += _hours(max(start, window_start), min(end_eff, t))
        today_hours += _hours(t, min(end_eff, t + day))
        if reason == constants.maintenance_reason:
            last_maintenance[equipment_id] = max(start.date(), last_maintenance.get(equipment_id, start.date()))
    since = max(((as_of - d).days for d in last_maintenance.values()), default=NAN)
    return rolling_hours / (n_machines * window * 24), today_hours / (n_machines * 24), float(since)


def backlog_t(db: Session, site_id: int, as_of: date, decay: float) -> float:
    """b_t = max(0, decay * b_{t-1} + shortfall_{t-1}) folded over every production record before as_of."""
    rows = db.execute(
        select(ProductionRecord.target_output, ProductionRecord.actual_output)
        .where(ProductionRecord.site_id == site_id, ProductionRecord.date < as_of)
        .order_by(ProductionRecord.date)
    ).all()
    b = 0.0
    for target, actual in rows:
        if target:
            b = max(0.0, decay * b + (float(target) - float(actual)) / float(target))
    return b


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def site_key_for(site: Site) -> str:
    return site.name.strip().lower()


def build_live_features(
    db: Session,
    site: Site,
    constants: FeatureConstants,
    *,
    as_of: date | None = None,
    today: date | None = None,
    rain_lookup: RainLookup | None = None,
    soil_lookup: Callable[[str, date, date], dict[date, float]] | None = None,
) -> LiveFeatures:
    """The model's feature row for `site`, as of `as_of` (default: see the module docstring)."""
    site_key = site_key_for(site)
    if site_key not in constants.machines_per_site:
        raise LiveDataUnavailableError(f"No machine count for site {site_key!r} in the model's feature constants.")
    n_machines = constants.machines_per_site[site_key]
    rain_lookup = rain_lookup or satellite_rain_lookup
    if soil_lookup is None:
        def soil_lookup(key: str, start: date, end: date) -> dict[date, float]:
            from app.services import weather_history

            return weather_history.load_soil_moisture(key, start, end)

    if as_of is None:
        # Today's rain is a day in progress (the Open-Meteo archive will return a partial or modelled value
        # for it, and weather_history caches successes permanently), so only FINISHED days count as observed.
        latest_finished_day = (today or datetime.now(timezone.utc).date()) - timedelta(days=1)
        as_of, observed = resolve_as_of(site_key, latest_finished_day, rain_lookup)
    else:
        observed = rain_lookup(site_key, as_of - timedelta(days=7), as_of)

    rain_lag1 = observed.get(as_of - timedelta(days=1), NAN)
    soil = soil_lookup(site_key, as_of - timedelta(days=1), as_of - timedelta(days=1)).get(as_of - timedelta(days=1), NAN)

    log_rows = db.scalars(select(EquipmentStatusLog).where(EquipmentStatusLog.site_id == site.id)).all()
    rolling_down, down_today, since_maintenance = downtime_features(
        reconstruct_outages(log_rows), as_of, n_machines, constants
    )
    blast_events = blast_delay_events_for_site(db, site.id, as_of)

    values = {
        "rain_today_mm": observed.get(as_of, NAN),
        "rain_3d_mm": _rain_sum(observed, as_of, 1, 3),
        "rain_7d_mm": _rain_sum(observed, as_of, 1, 7),
        "heavy_rain_lag1": NAN if math.isnan(rain_lag1) else float(rain_lag1 >= constants.heavy_rain_mm),
        "soil_moisture_m3m3": soil,
        "rolling_7d_downtime_pct": rolling_down,
        "equipment_down_today_pct": down_today,
        "days_since_last_maintenance": since_maintenance,
        "backlog_t": backlog_t(db, site.id, as_of, constants.backlog_decay),
        "blast_delay_days_lag": blast_delay_days_lag(blast_events, as_of),
        "dow_sin": math.sin(2 * math.pi * as_of.weekday() / 7),
        "dow_cos": math.cos(2 * math.pi * as_of.weekday() / 7),
        "month_sin": math.sin(2 * math.pi * as_of.month / 12),
        "month_cos": math.cos(2 * math.pi * as_of.month / 12),
    }
    missing = sorted(k for k, v in values.items() if isinstance(v, float) and math.isnan(v))
    if missing:
        logger.info("live features for %s as of %s: no observed value for %s (passed as NaN)", site_key, as_of, missing)
    return LiveFeatures(
        site_key=site_key,
        as_of=as_of,
        values=values,
        rain_lag1_mm=rain_lag1,
        blast_events=blast_events,
        n_machines=n_machines,
        constants=constants,
        missing=missing,
    )
