"""Pydantic schemas for site notes + similarity search."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SiteNoteCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": 1,
                "text": "Haul road on the north ramp waterlogged after two days of monsoon rain; graders deployed.",
            }
        }
    )

    site_id: int
    text: str = Field(min_length=1, max_length=4000)


class SiteNoteOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "site_id": 1,
                "text": "Haul road on the north ramp waterlogged after two days of monsoon rain.",
                "created_at": "2026-09-02T16:20:00Z",
            }
        },
    )

    id: int
    site_id: int
    text: str
    created_at: datetime


class SiteNoteSearchHit(SiteNoteOut):
    """A `SiteNoteOut` plus its cosine relevance to the query (1.0 = identical
    direction, 0.0 = orthogonal). Higher is better.
    """

    relevance: float
