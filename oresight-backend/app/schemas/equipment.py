"""Pydantic schemas for mining equipment."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.constants.validation_limits import MAX_FREE_TEXT_LENGTH


class EquipmentOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 16,
                "site_id": 1,
                "site_name": "Balaghat",
                "name": "Excavator BAL-1",
                "equipment_type": "Excavator",
                "status": "down",
                "last_status_change": "2026-08-30T05:11:27.578760+00:00",
                "status_reason": "Hydraulic pump failure - spare part on order, ETA 3 days",
                "flapping": False,
            }
        },
    )

    id: int
    site_id: int
    site_name: str
    name: str
    equipment_type: str
    status: Literal["up", "down"]
    last_status_change: datetime | None
    status_reason: str | None
    # Field Intake Hardening Phase 4 (§2.2) — additive. Only ever true on the
    # response to the status-change call that tripped flap detection; the
    # list endpoint always returns False (see routers/equipment.py).
    flapping: bool = False


class EquipmentStatusUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "down",
                "reason": "Engine overheating - pulled for inspection",
                "source": "manual",
            }
        }
    )

    status: Literal["up", "down"]
    reason: str | None = Field(None, max_length=MAX_FREE_TEXT_LENGTH)
    # 'manual' (single-row edit, the default), 'bulk' (bulk-down flow), or
    # 'sync' (reserved for a future automated ingestion path).
    source: Literal["manual", "bulk", "sync"] = "manual"


class EquipmentStatusLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    site_id: int
    old_status: str | None
    new_status: str
    reason: str | None
    changed_by: str | None
    changed_at: datetime
    source: str


class EquipmentHistoryPage(BaseModel):
    """Cursor-paginated page of status-log rows, newest first."""

    items: list[EquipmentStatusLogOut]
    next_cursor: datetime | None


# -- Equipment performance metrics (Task 6) ---------------------------------
# See docs/EQUIPMENT_METRICS.md for every definition and formula.

MaintenanceStatus = Literal["ok", "due_soon", "overdue", "unknown"]


class DowntimeHoursByCategory(BaseModel):
    """Downtime hours split by reason category — see
    app/constants/equipment_assumptions.py for the reason -> category map.
    """

    planned_maintenance: float
    failure: float
    spare_parts_wait: float
    operational: float
    weather: float
    other: float


class EquipmentMetricsWindow(BaseModel):
    start: date
    end: date
    hours: float
    data_through: datetime | None


class EquipmentMetricsAssumptions(BaseModel):
    maintenance_interval_days: int
    due_soon_days: int
    categories: dict[str, list[str]]


class FleetMetricsOut(BaseModel):
    site_id: int | None
    equipment_count: int
    physical_availability_pct: float
    overall_availability_pct: float
    failures: int
    mtbf_hours: float | None
    mttr_hours: float | None
    downtime_hours_by_category: DowntimeHoursByCategory
    maintenance_overdue_count: int
    maintenance_due_soon_count: int


class EquipmentMetricsEntryOut(BaseModel):
    """One machine's metrics, as returned inside GET /equipment/metrics's
    "equipment" array, and as the base of GET /equipment/{id}/metrics
    (which adds `weekly` and `events` — see EquipmentDetailMetricsOut).
    """

    equipment_id: int
    name: str
    equipment_type: str
    site_id: int
    status: Literal["up", "down"]
    physical_availability_pct: float
    overall_availability_pct: float
    failures: int
    mtbf_hours: float | None
    mttr_hours: float | None
    downtime_hours: float
    downtime_hours_by_category: DowntimeHoursByCategory
    top_failure_reason: str | None
    last_maintenance_at: datetime | None
    days_since_last_maintenance: int | None
    next_maintenance_due: date | None
    maintenance_status: MaintenanceStatus
    # ASSUMPTION: always null — no operating-hours (hour-meter) data exists
    # anywhere in this dataset to compute utilisation from.
    utilisation_pct: None = None
    utilisation_note: str


class EquipmentMetricsOut(BaseModel):
    """GET /equipment/metrics response body."""

    generated_at: datetime
    window: EquipmentMetricsWindow
    assumptions: EquipmentMetricsAssumptions
    fleet: FleetMetricsOut
    equipment: list[EquipmentMetricsEntryOut]
    data_note: str


class WeeklyMetricsPoint(BaseModel):
    week_start: date
    downtime_hours: float
    failures: int
    physical_availability_pct: float


class DowntimeEventOut(BaseModel):
    start: datetime
    end: datetime | None
    hours: float
    reason: str | None
    category: str
    source: str


class EquipmentDetailMetricsOut(EquipmentMetricsEntryOut):
    """GET /equipment/{equipment_id}/metrics response body — the same
    fields as one "equipment" array entry above, plus weekly and events. No
    window/assumptions/data_note wrapper (unlike the fleet endpoint).
    """

    weekly: list[WeeklyMetricsPoint]
    events: list[DowntimeEventOut]
