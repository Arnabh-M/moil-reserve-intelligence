"""Pydantic schemas for AI-generated mitigation recommendations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImpactedEntity(BaseModel):
    """One entity reached while tracing a recommendation's ripple/cascade
    effect through the causal graph. See app/services/cascade_service.py.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    entity_type: str
    name: str
    hops: int
    classification: Literal["blocking", "shifted", "downstream", "informational"]
    path: list[str]
    detail: str | None = None


class CascadeResult(BaseModel):
    """Downstream ripple impact of acting on a recommendation option — a
    deterministic graph-traversal + rule-evaluation result, never
    model-generated. Optional/additive: absent or null whenever cascade
    computation isn't available or fails (see cascade_service.compute_cascade).
    """

    model_config = ConfigDict(from_attributes=True)

    shift_days: int | None
    entities_affected: int
    blocking_count: int
    cascade_severity: Literal["none", "low", "moderate", "high"]
    cascade_adjusted_impact: float | None
    explanation: str
    impacted: list[ImpactedEntity] = Field(default_factory=list)


class RecommendationOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: Literal["reschedule", "redeploy", "adjust_plan"]
    description: str
    projected_impact: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    cascade: CascadeResult | None = None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "trigger": "Excavator EX-201 hydraulic failure at Balaghat",
                "risk_event_id": 1,
                "options": [
                    {
                        "type": "reschedule",
                        "description": (
                            "Delay the next blast at Balaghat by 2 days to let "
                            "Excavator EX-201 return to service."
                        ),
                        "projected_impact": 62.5,
                        "confidence": 0.78,
                    },
                    {
                        "type": "redeploy",
                        "description": (
                            "Redeploy Rock Drill DR-101 to cover Excavator "
                            "EX-201's workload at Balaghat for the outage."
                        ),
                        "projected_impact": 71.0,
                        "confidence": 0.82,
                    },
                    {
                        "type": "adjust_plan",
                        "description": (
                            "Lower Balaghat's daily target output by 15% until "
                            "Excavator EX-201 is repaired."
                        ),
                        "projected_impact": 45.0,
                        "confidence": 0.9,
                    },
                ],
            }
        },
    )

    trigger: str
    risk_event_id: int
    options: list[RecommendationOption]
