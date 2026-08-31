"""Routes for risk events and their (stubbed) causal graph."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import RiskEvent
from app.schemas import CausalGraphOut, GraphEdge, GraphNode, RiskEventOut
from app.services.lookups import get_risk_event_or_404

router = APIRouter(prefix="/risk-events", tags=["risk-events"])


def _risk_event_to_out(risk_event: RiskEvent) -> RiskEventOut:
    return RiskEventOut(
        id=risk_event.id,
        site_id=risk_event.site_id,
        site_name=risk_event.site.name,
        risk_type=risk_event.risk_type,
        severity=risk_event.severity.value,
        score=risk_event.score,
        description=risk_event.description,
        resolved=risk_event.resolved,
        detected_at=risk_event.detected_at,
    )


@router.get("", response_model=list[RiskEventOut], summary="List risk events")
def list_risk_events(
    site_id: int | None = Query(None, description="Filter to one site"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    db: Session = Depends(get_db),
) -> list[RiskEventOut]:
    """Return risk events, newest first, optionally filtered by site and/or
    resolved status.
    """
    stmt = (
        select(RiskEvent)
        .options(joinedload(RiskEvent.site))
        .order_by(RiskEvent.detected_at.desc())
    )
    if site_id is not None:
        stmt = stmt.where(RiskEvent.site_id == site_id)
    if resolved is not None:
        stmt = stmt.where(RiskEvent.resolved == resolved)
    rows = db.scalars(stmt).all()
    return [_risk_event_to_out(r) for r in rows]


@router.get(
    "/{risk_event_id}/causal-graph",
    response_model=CausalGraphOut,
    summary="Get the causal graph behind a risk event",
)
def get_causal_graph(
    risk_event_id: int, db: Session = Depends(get_db)
) -> CausalGraphOut:
    """Return the causal chain that led to this risk event.

    STUB: replaced on Day 3 with a live Neo4j traversal. For now returns a
    fixed, realistically-shaped 5-node chain so the frontend can build the
    React Flow graph view today.
    """
    get_risk_event_or_404(db, risk_event_id)

    nodes = [
        GraphNode(
            id="weather_2026_03_14", label="Heavy Rainfall 14 Mar", type="WeatherEvent"
        ),
        GraphNode(id="blast_plan_b204", label="Blast Plan B-204", type="BlastPlan"),
        GraphNode(id="zone_b2", label="Zone B2", type="OreZone"),
        GraphNode(id="equipment_ex201", label="Excavator EX-201", type="Equipment"),
        GraphNode(
            id="risk_event_shortfall",
            label="Production shortfall risk",
            type="RiskEvent",
        ),
    ]
    edges = [
        GraphEdge(
            source="weather_2026_03_14", target="blast_plan_b204", relationship="DELAYS"
        ),
        GraphEdge(source="blast_plan_b204", target="zone_b2", relationship="AFFECTS"),
        GraphEdge(
            source="equipment_ex201", target="zone_b2", relationship="OPERATES_IN"
        ),
        GraphEdge(
            source="zone_b2", target="risk_event_shortfall", relationship="CAUSES"
        ),
    ]
    return CausalGraphOut(nodes=nodes, edges=edges)
