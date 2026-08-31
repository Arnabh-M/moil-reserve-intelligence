"""Pydantic schemas for mine sites."""

from pydantic import BaseModel, ConfigDict


class SiteOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Balaghat",
                "belt_name": "Balaghat Manganese Belt",
                "district": "Balaghat",
                "state": "Madhya Pradesh",
                "centroid_lat": 21.80,
                "centroid_lon": 80.19,
                "active_risk_count": 2,
                "avg_reserve_confidence": 0.67,
            }
        },
    )

    id: int
    name: str
    belt_name: str | None
    district: str | None
    state: str | None
    centroid_lat: float
    centroid_lon: float
    active_risk_count: int
    avg_reserve_confidence: float | None
