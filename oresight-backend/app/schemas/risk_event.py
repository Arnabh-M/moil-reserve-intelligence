"""Pydantic schemas for detected risk events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RiskEventOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 5,
                "site_id": 2,
                "site_name": "Nagpur",
                "risk_type": "equipment_failure",
                "severity": "critical",
                "score": 0.93,
                "description": "Haul Truck HT-302 engine overheating has taken the unit fully offline.",
                "resolved": False,
                "detected_at": "2026-08-31T05:11:27.578760+00:00",
            }
        },
    )

    id: int
    site_id: int
    site_name: str
    risk_type: str
    severity: Literal["low", "medium", "high", "critical"]
    score: float | None
    description: str | None
    resolved: bool
    detected_at: datetime
