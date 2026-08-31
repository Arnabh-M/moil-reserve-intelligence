"""Pydantic schema for the Command Center KPI summary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KPISummaryOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "active_risk_events": 5,
                "avg_reserve_confidence": 0.64,
                "sites_under_watch": 3,
                "twin_last_updated": "2026-08-31T05:11:27.578760+00:00",
            }
        },
    )

    active_risk_events: int
    avg_reserve_confidence: float | None
    sites_under_watch: int
    twin_last_updated: datetime | None
