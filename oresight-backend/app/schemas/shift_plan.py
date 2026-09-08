"""Pydantic schemas for the shift plan.

A shift-plan entry is a snapshot of one `GET /recommendations` option, so
the create shape mirrors `RecommendationOption`'s field constraints
(`projected_impact` 0-100, `confidence` 0-1, the three option types). It
deliberately does NOT reference or subclass those schemas — this feature is
additive and stays decoupled from the recommendations contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShiftPlanEntryCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_event_id": 5,
                "option_type": "redeploy",
                "description": "Redeploy Haul Truck HT-303 from Bhandara to Nagpur to cover Haul Truck HT-302.",
                "target_id": "eq_bhandara_06",
                "projected_impact": 77.0,
                "confidence": 0.8,
            }
        }
    )

    risk_event_id: int
    option_type: Literal["reschedule", "redeploy", "adjust_plan"]
    description: str = Field(min_length=1)
    target_id: str | None = None
    projected_impact: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class ShiftPlanEntryOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 3,
                "risk_event_id": 5,
                "site_id": 2,
                "option_type": "redeploy",
                "description": "Redeploy Haul Truck HT-303 from Bhandara to Nagpur to cover Haul Truck HT-302.",
                "target_id": "eq_bhandara_06",
                "projected_impact": 77.0,
                "confidence": 0.8,
                "created_at": "2026-09-08T14:20:00Z",
            }
        },
    )

    id: int
    risk_event_id: int
    site_id: int
    option_type: str
    description: str
    target_id: str | None
    projected_impact: float
    confidence: float
    created_at: datetime
