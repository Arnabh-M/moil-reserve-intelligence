"""Pydantic schemas for daily production records."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ProductionRecordOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 42,
                "site_id": 1,
                "date": "2026-08-29",
                "actual_output": 712.4,
                "target_output": 1062.5,
                "variance_pct": -32.96,
            }
        },
    )

    id: int
    site_id: int
    date: date
    actual_output: float | None
    target_output: float | None
    variance_pct: float | None


class ProductionRecordCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": 1,
                "date": "2026-08-31",
                "actual_output": 1180.0,
                "target_output": 1250.0,
            }
        }
    )

    site_id: int
    date: date
    actual_output: float
    target_output: float
