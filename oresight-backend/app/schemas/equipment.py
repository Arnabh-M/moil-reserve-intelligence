"""Pydantic schemas for mining equipment."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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
    reason: str | None = None
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
