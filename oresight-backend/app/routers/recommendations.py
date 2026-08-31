"""Route for AI-generated mitigation recommendations (stubbed)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Equipment
from app.schemas import RecommendationOption, RecommendationOut
from app.services.lookups import get_risk_event_or_404

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "",
    response_model=list[RecommendationOut],
    summary="Get mitigation recommendations for a risk event",
)
def get_recommendations(
    risk_event_id: int = Query(
        ..., description="The risk event to generate recommendations for"
    ),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    """Return mitigation options for a risk event.

    STUB: replaced on Day 4 with real recommendation-engine output. For now
    returns 2 hand-authored recommendations referencing the actual
    site/equipment behind the given risk event, so the frontend can build the
    recommendations UI today.
    """
    risk_event = get_risk_event_or_404(db, risk_event_id)
    site = risk_event.site

    site_equipment = db.scalars(
        select(Equipment).where(Equipment.site_id == site.id).order_by(Equipment.name)
    ).all()
    primary_equipment_name = (
        site_equipment[0].name if site_equipment else "site equipment"
    )
    secondary_equipment_name = (
        site_equipment[1].name if len(site_equipment) > 1 else primary_equipment_name
    )

    return [
        RecommendationOut(
            trigger=risk_event.description or f"{risk_event.risk_type} at {site.name}",
            risk_event_id=risk_event.id,
            options=[
                RecommendationOption(
                    type="reschedule",
                    description=(
                        f"Delay the next blast at {site.name} by 2 days to let "
                        f"{primary_equipment_name} return to service."
                    ),
                    projected_impact=62.5,
                    confidence=0.78,
                ),
                RecommendationOption(
                    type="redeploy",
                    description=(
                        f"Redeploy {secondary_equipment_name} to cover "
                        f"{primary_equipment_name}'s workload at {site.name} "
                        "for the outage."
                    ),
                    projected_impact=71.0,
                    confidence=0.82,
                ),
                RecommendationOption(
                    type="adjust_plan",
                    description=(
                        f"Lower {site.name}'s daily target output by 15% until "
                        f"{primary_equipment_name} is repaired."
                    ),
                    projected_impact=45.0,
                    confidence=0.9,
                ),
            ],
        ),
        RecommendationOut(
            trigger=f"Elevated {risk_event.risk_type} trend at {site.name}",
            risk_event_id=risk_event.id,
            options=[
                RecommendationOption(
                    type="reschedule",
                    description=(
                        f"Shift {site.name}'s next 2 haul cycles to the morning "
                        "shift to reduce exposure."
                    ),
                    projected_impact=54.0,
                    confidence=0.66,
                ),
                RecommendationOption(
                    type="redeploy",
                    description=(
                        f"Temporarily reassign a loader from a neighbouring "
                        f"site to {site.name}."
                    ),
                    projected_impact=68.5,
                    confidence=0.71,
                ),
                RecommendationOption(
                    type="adjust_plan",
                    description=(
                        f"Revise {site.name}'s weekly production target "
                        "downward by 10% for this week."
                    ),
                    projected_impact=40.0,
                    confidence=0.85,
                ),
            ],
        ),
    ]
