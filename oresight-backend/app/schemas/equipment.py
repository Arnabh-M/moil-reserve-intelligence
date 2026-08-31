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


class EquipmentStatusUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "down",
                "reason": "Engine overheating - pulled for inspection",
            }
        }
    )

    status: Literal["up", "down"]
    reason: str | None = None
