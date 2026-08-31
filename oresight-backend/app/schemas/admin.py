"""Pydantic schema for scheduler job status (ops/demo visibility)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobStatusOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "ingest_satellite_data",
                "next_run_time": "2026-08-31T14:00:00+00:00",
                "last_run_at": None,
                "last_status": "never_run",
                "last_error": None,
            }
        },
    )

    id: str
    next_run_time: datetime | None
    last_run_at: datetime | None
    last_status: str
    last_error: str | None
