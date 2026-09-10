"""Pydantic schemas for blast events + delay-reason aggregation."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.constants.validation_limits import MAX_TONNES

BlastStatusLiteral = Literal["planned", "completed", "delayed", "cancelled"]
DelayReasonLiteral = Literal[
    "permit_pending",
    "weather_hold",
    "safety_hold",
    "equipment_unavailable",
    "explosive_supply",
]


class BlastEventOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 7,
                "site_id": 1,
                "reserve_zone_id": 3,
                "planned_date": "2026-09-10",
                "actual_date": None,
                "status": "delayed",
                "delay_reason": "permit_pending",
                "expected_yield_tonnes": 1800.0,
                "actual_yield_tonnes": None,
                "notes": "District explosives permit renewal still with the controller.",
                "created_at": "2026-09-07T09:15:00Z",
                "updated_at": "2026-09-07T11:40:00Z",
            }
        },
    )

    id: int
    site_id: int
    reserve_zone_id: int | None
    planned_date: date
    actual_date: date | None
    status: BlastStatusLiteral
    delay_reason: DelayReasonLiteral | None
    expected_yield_tonnes: float
    actual_yield_tonnes: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BlastEventCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": 1,
                "reserve_zone_id": 3,
                "planned_date": "2026-09-10",
                "expected_yield_tonnes": 1800.0,
                "notes": "Bench 4 north face, twin-row pattern.",
            }
        }
    )

    site_id: int
    reserve_zone_id: int | None = None
    planned_date: date
    expected_yield_tonnes: float = Field(
        gt=0, le=MAX_TONNES, description="Planned tonnes from this blast; must be positive"
    )
    notes: str | None = None


class BlastEventUpdate(BaseModel):
    """Partial update. Cross-field rules (a delayed/cancelled blast needs a
    `delay_reason`; a completed one needs `actual_date` + `actual_yield_tonnes`)
    depend on the stored row, so the router enforces them, not this schema.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "actual_date": "2026-09-11",
                "actual_yield_tonnes": 1725.5,
                "notes": "Fired a day late; fragmentation within spec.",
            }
        }
    )

    status: BlastStatusLiteral | None = None
    actual_date: date | None = None
    delay_reason: DelayReasonLiteral | None = None
    actual_yield_tonnes: float | None = Field(
        default=None, ge=0, le=MAX_TONNES, description="Tonnes actually recovered; non-negative"
    )
    notes: str | None = None


class BlastDelaySummaryRow(BaseModel):
    """One delay reason's contribution to lost tonnes. Only `delayed` and
    `cancelled` blasts are counted — a completed blast lost nothing.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "delay_reason": "permit_pending",
                "event_count": 3,
                "expected_yield_tonnes": 5400.0,
                "actual_yield_tonnes": 0.0,
                "tonnes_lost": 5400.0,
            }
        }
    )

    delay_reason: DelayReasonLiteral | None
    event_count: int
    expected_yield_tonnes: float
    actual_yield_tonnes: float
    tonnes_lost: float
