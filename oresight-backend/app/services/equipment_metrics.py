"""Equipment performance metrics — availability, failures, MTBF, MTTR, and a
maintenance-due flag, per machine and per site (Task 6, backend).

Downtime-interval reconstruction and the metric arithmetic are pure
functions (prefixed `_`, taking plain lists of `_StatusEvent` and returning
dicts/dataclasses) so they're testable without a database — see
tests/test_equipment_metrics.py. `get_fleet_metrics` and
`get_equipment_metrics` are the thin SQLAlchemy-backed entry points routers
call; both return exactly the shapes documented in docs/EQUIPMENT_METRICS.md
(the CONTRACT the frontend is built against).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.equipment_assumptions import (
    CATEGORY_KEYS,
    DEFAULT_WINDOW_DAYS,
    DUE_SOON_DAYS,
    KEYWORD_RULES,
    MAINTENANCE_INTERVAL_DAYS,
    MAX_WINDOW_DAYS,
    REASON_CATEGORIES,
    UTILISATION_NOTE,
)
from app.models import Equipment, EquipmentStatusLog

DATA_NOTE = (
    "Downtime history loaded from the downtime log and field entries; demo "
    "data is synthetic until MOIL maintenance records are connected."
)


class InvalidWindowError(ValueError):
    """start is after end."""


class WindowTooLongError(ValueError):
    """Resolved window exceeds MAX_WINDOW_DAYS."""


# --------------------------------------------------------------------------
# Pure data types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _StatusEvent:
    changed_at: datetime
    new_status: str  # "up" | "down"
    reason: str | None
    source: str


@dataclass(frozen=True)
class _DowntimeInterval:
    start: datetime
    end: datetime
    reason: str | None
    source: str
    open: bool  # True: no observed "up" event yet (ended at min(now, window_end))
    category: str = ""


def _empty_category_hours() -> dict[str, float]:
    return {key: 0.0 for key in CATEGORY_KEYS}


def _interval_hours(interval: _DowntimeInterval) -> float:
    return (interval.end - interval.start).total_seconds() / 3600


# --------------------------------------------------------------------------
# Pure functions — reason categorization
# --------------------------------------------------------------------------


def _categorize_reason(reason: str | None) -> str:
    """Exact REASON_CATEGORIES match first (case-insensitive), then
    KEYWORD_RULES (case-insensitive substring, first match wins), else "other".
    """
    if not reason:
        return "other"
    normalized = reason.strip().lower()
    for category, exact_reasons in REASON_CATEGORIES.items():
        if normalized in exact_reasons:
            return category
    for keywords, category in KEYWORD_RULES:
        if any(keyword in normalized for keyword in keywords):
            return category
    return "other"


# --------------------------------------------------------------------------
# Pure functions — interval reconstruction
# --------------------------------------------------------------------------


def _build_downtime_intervals(
    events: list[_StatusEvent], *, window_end: datetime, now: datetime
) -> tuple[list[_DowntimeInterval], list[str]]:
    """Rebuild downtime intervals for one machine from its full status-change
    history. Pairs each change to "down" with the next change to "up". A
    trailing "down" with no following "up" is an open interval, ended at
    min(now, window_end). Duplicate consecutive statuses (e.g. re-posting
    "down" while already down, just to update the reason) are skipped and
    logged rather than starting a spurious new interval.

    Caller doesn't need to pre-sort `events`.
    """
    sorted_events = sorted(events, key=lambda e: e.changed_at)
    intervals: list[_DowntimeInterval] = []
    warnings: list[str] = []

    open_start: datetime | None = None
    open_reason: str | None = None
    open_source: str = "manual"
    last_status: str | None = None

    for event in sorted_events:
        if event.new_status == last_status:
            warnings.append(
                f"duplicate consecutive status {event.new_status!r} at "
                f"{event.changed_at.isoformat()} — skipped"
            )
            continue

        if event.new_status == "down":
            open_start = event.changed_at
            open_reason = event.reason
            open_source = event.source
        elif event.new_status == "up" and open_start is not None:
            intervals.append(
                _DowntimeInterval(
                    start=open_start,
                    end=event.changed_at,
                    reason=open_reason,
                    source=open_source,
                    open=False,
                    category=_categorize_reason(open_reason),
                )
            )
            open_start = None

        last_status = event.new_status

    if open_start is not None:
        end = min(now, window_end)
        if end < open_start:
            end = open_start
        intervals.append(
            _DowntimeInterval(
                start=open_start,
                end=end,
                reason=open_reason,
                source=open_source,
                open=True,
                category=_categorize_reason(open_reason),
            )
        )

    return intervals, warnings


def _clip_interval(
    interval: _DowntimeInterval, window_start: datetime, window_end: datetime
) -> _DowntimeInterval | None:
    """Clip one interval to [window_start, window_end]. None if no overlap."""
    start = max(interval.start, window_start)
    end = min(interval.end, window_end)
    if start >= end:
        return None
    return replace(interval, start=start, end=end)


def _clip_intervals(
    intervals: list[_DowntimeInterval], window_start: datetime, window_end: datetime
) -> list[_DowntimeInterval]:
    clipped = (_clip_interval(i, window_start, window_end) for i in intervals)
    return [i for i in clipped if i is not None]


# --------------------------------------------------------------------------
# Pure functions — metric arithmetic
# --------------------------------------------------------------------------


def _compute_window_metrics(intervals: list[_DowntimeInterval], window_hours: float) -> dict:
    """physical/overall availability, failures, MTBF, MTTR, downtime hours by
    category, and top_failure_reason for one machine (or a pre-pooled fleet),
    from its window-clipped downtime intervals.

    DEFINITIONS (see docs/EQUIPMENT_METRICS.md):
      physical_availability = (window_hours - planned_maintenance - failure -
                                spare_parts_wait) / window_hours
      overall_availability  = (window_hours - all downtime) / window_hours
      mtbf_hours = (window_hours - all downtime) / failures; null if failures==0
      mttr_hours = mean duration of failure-category intervals; null if failures==0
    Weather and operator-shift-gap downtime never reduce physical
    availability — the machine itself wasn't broken, it was externally
    blocked — but they do reduce overall availability, same as everything else.
    """
    hours_by_category = _empty_category_hours()
    failure_intervals: list[_DowntimeInterval] = []
    # reason -> (occurrence count, total hours), for top_failure_reason
    failure_reason_stats: dict[str, tuple[int, float]] = {}

    for interval in intervals:
        hours = _interval_hours(interval)
        hours_by_category[interval.category] = hours_by_category.get(interval.category, 0.0) + hours
        if interval.category == "failure":
            failure_intervals.append(interval)
            reason_key = interval.reason or "unspecified"
            count, total_hours = failure_reason_stats.get(reason_key, (0, 0.0))
            failure_reason_stats[reason_key] = (count + 1, total_hours + hours)

    total_downtime_hours = sum(hours_by_category.values())
    physical_deduction = (
        hours_by_category["planned_maintenance"]
        + hours_by_category["failure"]
        + hours_by_category["spare_parts_wait"]
    )

    if window_hours <= 0:
        # No time in the window at all (e.g. a zero-machine fleet) — nothing
        # to be unavailable from. Defined as perfect availability, not an
        # error: there's no denominator to divide a real number of downtime
        # hours by.
        physical_pct = 100.0
        overall_pct = 100.0
    else:
        physical_pct = (window_hours - physical_deduction) / window_hours * 100
        overall_pct = (window_hours - total_downtime_hours) / window_hours * 100

    failures = len(failure_intervals)
    if failures == 0:
        mtbf_hours: float | None = None
        mttr_hours: float | None = None
    else:
        uptime_hours = max(0.0, window_hours - total_downtime_hours)
        mtbf_hours = round(uptime_hours / failures, 2)
        mttr_hours = round(hours_by_category["failure"] / failures, 2)

    top_failure_reason = None
    if failure_reason_stats:
        # Most occurrences, tie-broken by most hours, then alphabetically —
        # deterministic regardless of dict iteration order.
        top_failure_reason = min(
            failure_reason_stats.items(),
            key=lambda item: (-item[1][0], -item[1][1], item[0]),
        )[0]

    return {
        "physical_availability_pct": round(physical_pct, 1),
        "overall_availability_pct": round(overall_pct, 1),
        "failures": failures,
        "mtbf_hours": mtbf_hours,
        "mttr_hours": mttr_hours,
        "downtime_hours": round(total_downtime_hours, 2),
        "downtime_hours_by_category": {k: round(v, 2) for k, v in hours_by_category.items()},
        "top_failure_reason": top_failure_reason,
    }


def _compute_maintenance_status(intervals_full: list[_DowntimeInterval], *, as_of: datetime) -> dict:
    """last_maintenance_at/days_since/next_due/status, from the machine's
    FULL (not window-clipped) interval history — a maintenance event before
    the analysis window still counts, e.g. for an overdue flag on a short
    window that starts after the last real maintenance.
    """
    maintenance_intervals = [
        i for i in intervals_full if i.category == "planned_maintenance" and i.end <= as_of
    ]
    if not maintenance_intervals:
        return {
            "last_maintenance_at": None,
            "days_since_last_maintenance": None,
            "next_maintenance_due": None,
            "maintenance_status": "unknown",
        }

    last_maintenance_at = max(i.end for i in maintenance_intervals)
    days_since = (as_of - last_maintenance_at).days
    next_due_date = last_maintenance_at.date() + timedelta(days=MAINTENANCE_INTERVAL_DAYS)

    as_of_date = as_of.date()
    if next_due_date < as_of_date:
        status = "overdue"
    elif next_due_date <= as_of_date + timedelta(days=DUE_SOON_DAYS):
        status = "due_soon"
    else:
        status = "ok"

    return {
        "last_maintenance_at": last_maintenance_at,
        "days_since_last_maintenance": days_since,
        "next_maintenance_due": next_due_date,
        "maintenance_status": status,
    }


def _iso_week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _weekly_series(
    intervals_window: list[_DowntimeInterval], window_start: datetime, window_end: datetime
) -> list[dict]:
    """One entry per ISO week (Monday-start) overlapping [window_start,
    window_end). The first/last bucket may be partial when the window
    doesn't start/end on a Monday — week_start always labels that week's
    Monday regardless.
    """
    if window_start >= window_end:
        return []

    weeks: list[dict] = []
    cursor = _iso_week_monday(window_start.date())
    while datetime.combine(cursor, time.min, tzinfo=timezone.utc) < window_end:
        bucket_start = max(window_start, datetime.combine(cursor, time.min, tzinfo=timezone.utc))
        bucket_end = min(
            window_end, datetime.combine(cursor + timedelta(days=7), time.min, tzinfo=timezone.utc)
        )
        bucket_hours = (bucket_end - bucket_start).total_seconds() / 3600
        bucket_intervals = _clip_intervals(intervals_window, bucket_start, bucket_end)
        metrics = _compute_window_metrics(bucket_intervals, bucket_hours)

        weeks.append(
            {
                "week_start": cursor.isoformat(),
                "downtime_hours": metrics["downtime_hours"],
                "failures": metrics["failures"],
                "physical_availability_pct": metrics["physical_availability_pct"],
            }
        )
        cursor += timedelta(days=7)

    return weeks


def _events_list(intervals_window: list[_DowntimeInterval]) -> list[dict]:
    return [
        {
            "start": i.start,
            "end": None if i.open else i.end,
            "hours": round(_interval_hours(i), 2),
            "reason": i.reason,
            "category": i.category,
            "source": i.source,
        }
        for i in sorted(intervals_window, key=lambda i: i.start)
    ]


# --------------------------------------------------------------------------
# Database-facing layer
# --------------------------------------------------------------------------


def _assumptions_payload() -> dict:
    categories = {**REASON_CATEGORIES, "other": []}
    return {
        "maintenance_interval_days": MAINTENANCE_INTERVAL_DAYS,
        "due_soon_days": DUE_SOON_DAYS,
        "categories": categories,
    }


def _get_status_events(db: Session, equipment_id: int) -> list[_StatusEvent]:
    rows = db.scalars(
        select(EquipmentStatusLog)
        .where(EquipmentStatusLog.equipment_id == equipment_id)
        .order_by(EquipmentStatusLog.changed_at)
    ).all()
    return [
        _StatusEvent(changed_at=r.changed_at, new_status=r.new_status, reason=r.reason, source=r.source)
        for r in rows
    ]


def _data_through(db: Session, *, site_id: int | None, equipment_id: int | None) -> datetime | None:
    stmt = select(func.max(EquipmentStatusLog.changed_at))
    if equipment_id is not None:
        stmt = stmt.where(EquipmentStatusLog.equipment_id == equipment_id)
    elif site_id is not None:
        stmt = stmt.where(EquipmentStatusLog.site_id == site_id)
    return db.scalar(stmt)


def _resolve_window(
    db: Session,
    *,
    site_id: int | None,
    equipment_id: int | None,
    start: date | None,
    end: date | None,
) -> tuple[datetime, datetime, date, date, datetime | None]:
    """Returns (window_start_dt, window_end_dt_exclusive, start_date,
    end_date, data_through).

    Default window: end = the date of data_through (or today, if this scope
    has no status-log history yet); start = end - DEFAULT_WINDOW_DAYS.
    window_end_dt is the exclusive day-after boundary (so a window covers
    full calendar days), clipped to real wall-clock `now` if that boundary
    would otherwise fall in the future.
    """
    data_through = _data_through(db, site_id=site_id, equipment_id=equipment_id)
    now = datetime.now(timezone.utc)

    end_date = end if end is not None else (data_through.date() if data_through else now.date())
    start_date = start if start is not None else end_date - timedelta(days=DEFAULT_WINDOW_DAYS)

    if start_date > end_date:
        raise InvalidWindowError("start must not be after end")
    if (end_date - start_date).days > MAX_WINDOW_DAYS:
        raise WindowTooLongError(f"window must not exceed {MAX_WINDOW_DAYS} days")

    window_start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    window_end = datetime.combine(end_date, time.min, tzinfo=timezone.utc) + timedelta(days=1)
    window_end = min(window_end, now)
    if window_end < window_start:
        window_end = window_start

    return window_start, window_end, start_date, end_date, data_through


def _machine_result(
    equipment: Equipment,
    intervals_full: list[_DowntimeInterval],
    intervals_window: list[_DowntimeInterval],
    window_hours: float,
    window_end: datetime,
) -> dict:
    window_metrics = _compute_window_metrics(intervals_window, window_hours)
    maintenance = _compute_maintenance_status(intervals_full, as_of=window_end)

    return {
        "equipment_id": equipment.id,
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "site_id": equipment.site_id,
        "status": equipment.status.value,
        "physical_availability_pct": window_metrics["physical_availability_pct"],
        "overall_availability_pct": window_metrics["overall_availability_pct"],
        "failures": window_metrics["failures"],
        "mtbf_hours": window_metrics["mtbf_hours"],
        "mttr_hours": window_metrics["mttr_hours"],
        "downtime_hours": window_metrics["downtime_hours"],
        "downtime_hours_by_category": window_metrics["downtime_hours_by_category"],
        "top_failure_reason": window_metrics["top_failure_reason"],
        "last_maintenance_at": maintenance["last_maintenance_at"],
        "days_since_last_maintenance": maintenance["days_since_last_maintenance"],
        "next_maintenance_due": maintenance["next_maintenance_due"],
        "maintenance_status": maintenance["maintenance_status"],
        "utilisation_pct": None,
        "utilisation_note": UTILISATION_NOTE,
    }


def _aggregate_fleet(machine_results: list[dict], *, site_id: int | None, window_hours: float) -> dict:
    """Fleet totals = sum of hours across machines, never an average of
    percentages (see DEFINITIONS)."""
    equipment_count = len(machine_results)
    fleet_window_hours = window_hours * equipment_count

    hours_by_category = _empty_category_hours()
    total_failures = 0
    overdue = 0
    due_soon = 0

    for m in machine_results:
        for key, hours in m["downtime_hours_by_category"].items():
            hours_by_category[key] += hours
        total_failures += m["failures"]
        if m["maintenance_status"] == "overdue":
            overdue += 1
        elif m["maintenance_status"] == "due_soon":
            due_soon += 1

    total_downtime_hours = sum(hours_by_category.values())
    physical_deduction = (
        hours_by_category["planned_maintenance"]
        + hours_by_category["failure"]
        + hours_by_category["spare_parts_wait"]
    )

    if fleet_window_hours <= 0:
        physical_pct = 100.0
        overall_pct = 100.0
    else:
        physical_pct = (fleet_window_hours - physical_deduction) / fleet_window_hours * 100
        overall_pct = (fleet_window_hours - total_downtime_hours) / fleet_window_hours * 100

    if total_failures == 0:
        mtbf_hours: float | None = None
        mttr_hours: float | None = None
    else:
        uptime_hours = max(0.0, fleet_window_hours - total_downtime_hours)
        mtbf_hours = round(uptime_hours / total_failures, 2)
        mttr_hours = round(hours_by_category["failure"] / total_failures, 2)

    return {
        "site_id": site_id,
        "equipment_count": equipment_count,
        "physical_availability_pct": round(physical_pct, 1),
        "overall_availability_pct": round(overall_pct, 1),
        "failures": total_failures,
        "mtbf_hours": mtbf_hours,
        "mttr_hours": mttr_hours,
        "downtime_hours_by_category": {k: round(v, 2) for k, v in hours_by_category.items()},
        "maintenance_overdue_count": overdue,
        "maintenance_due_soon_count": due_soon,
    }


def get_fleet_metrics(
    db: Session, *, site_id: int | None, start: date | None, end: date | None
) -> dict:
    """GET /equipment/metrics response body. `site_id` must already be
    validated (404'd) by the caller if not None.
    """
    window_start, window_end, start_date, end_date, data_through = _resolve_window(
        db, site_id=site_id, equipment_id=None, start=start, end=end
    )
    window_hours = (window_end - window_start).total_seconds() / 3600
    now = datetime.now(timezone.utc)

    stmt = select(Equipment).order_by(Equipment.name)
    if site_id is not None:
        stmt = stmt.where(Equipment.site_id == site_id)
    equipment_rows = db.scalars(stmt).all()

    machine_results = []
    for equipment in equipment_rows:
        events = _get_status_events(db, equipment.id)
        intervals_full, _warnings = _build_downtime_intervals(events, window_end=window_end, now=now)
        intervals_window = _clip_intervals(intervals_full, window_start, window_end)
        machine_results.append(
            _machine_result(equipment, intervals_full, intervals_window, window_hours, window_end)
        )

    fleet = _aggregate_fleet(machine_results, site_id=site_id, window_hours=window_hours)

    return {
        "generated_at": now,
        "window": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "hours": round(window_hours, 2),
            "data_through": data_through,
        },
        "assumptions": _assumptions_payload(),
        "fleet": fleet,
        "equipment": machine_results,
        "data_note": DATA_NOTE,
    }


def get_equipment_metrics(db: Session, equipment: Equipment, *, start: date | None, end: date | None) -> dict:
    """GET /equipment/{equipment_id}/metrics response body: the same fields
    as one entry in get_fleet_metrics's "equipment" array, plus weekly and
    events. No window/assumptions/data_note wrapper — see CONTRACT.
    """
    window_start, window_end, _start_date, _end_date, _data_through = _resolve_window(
        db, site_id=None, equipment_id=equipment.id, start=start, end=end
    )
    window_hours = (window_end - window_start).total_seconds() / 3600
    now = datetime.now(timezone.utc)

    events = _get_status_events(db, equipment.id)
    intervals_full, _warnings = _build_downtime_intervals(events, window_end=window_end, now=now)
    intervals_window = _clip_intervals(intervals_full, window_start, window_end)

    result = _machine_result(equipment, intervals_full, intervals_window, window_hours, window_end)
    result["weekly"] = _weekly_series(intervals_window, window_start, window_end)
    result["events"] = _events_list(intervals_window)
    return result
