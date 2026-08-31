"""Route for what-if scenario simulation (stubbed with deterministic math)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Equipment, ProductionRecord, ReserveZone, RiskEvent
from app.schemas import (
    CausalGraphOut,
    GraphEdge,
    GraphNode,
    SimStateSnapshot,
    SimulateRequest,
    SimulateResponse,
)
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/simulate", tags=["simulation"])

# STUB: replaced on Day 4-5 with the real simulation engine. Rates are
# fraction-per-day, capped so long durations don't run away to nonsense.
_SCENARIO_RATES = {
    "equipment_down": {"production": 0.045, "risk": 0.05, "confidence": 0.002},
    "delay_blasting": {"production": 0.03, "risk": 0.035, "confidence": 0.015},
    "rainfall_event": {"production": 0.05, "risk": 0.04, "confidence": 0.003},
}

_SCENARIO_LABELS = {
    "equipment_down": "Equipment Down",
    "delay_blasting": "Blast Plan Delay",
    "rainfall_event": "Rainfall Event",
}


@router.post(
    "", response_model=SimulateResponse, summary="Run a what-if scenario simulation"
)
def simulate(payload: SimulateRequest, db: Session = Depends(get_db)) -> SimulateResponse:
    """Simulate the impact of a disruption scenario on one site's twin state.

    STUB: replaced on Day 4-5 with the real simulation engine. For now applies
    a small deterministic model: the 'before' snapshot is grounded in today's
    real data for the site, then perturbed by `scenario_type` and
    `duration_days` for 'after' - so the numbers are plausible, move in the
    correct direction, and scale with duration rather than being random or
    constant.
    """
    site = get_site_or_404(db, payload.site_id)

    avg_confidence = (
        db.scalar(
            select(func.avg(ReserveZone.confidence_score)).where(
                ReserveZone.site_id == site.id
            )
        )
        or 0.6
    )

    recent_output_subq = (
        select(ProductionRecord.actual_output)
        .where(ProductionRecord.site_id == site.id)
        .order_by(ProductionRecord.date.desc())
        .limit(14)
        .subquery()
    )
    avg_recent_output = db.scalar(
        select(func.avg(recent_output_subq.c.actual_output))
    )

    baseline_risk = db.scalar(
        select(func.avg(RiskEvent.score)).where(
            RiskEvent.site_id == site.id, RiskEvent.resolved.is_(False)
        )
    )

    before = SimStateSnapshot(
        reserve_confidence=round(avg_confidence, 3),
        production_forecast_tonnes=round(avg_recent_output or 900.0, 1),
        risk_score=round(baseline_risk if baseline_risk is not None else 0.3, 3),
    )

    rates = _SCENARIO_RATES[payload.scenario_type]
    duration = payload.duration_days

    production_drop = min(rates["production"] * duration, 0.6)
    risk_increase = min(rates["risk"] * duration, 0.65)
    confidence_drop = min(rates["confidence"] * duration, 0.25)

    after = SimStateSnapshot(
        reserve_confidence=round(
            max(before.reserve_confidence * (1 - confidence_drop), 0.05), 3
        ),
        production_forecast_tonnes=round(
            before.production_forecast_tonnes * (1 - production_drop), 1
        ),
        risk_score=round(min(before.risk_score + risk_increase, 0.97), 3),
    )

    scenario_label = _SCENARIO_LABELS[payload.scenario_type]

    equipment_row = None
    if payload.scenario_type == "equipment_down":
        equipment_row = db.scalar(
            select(Equipment).where(Equipment.site_id == site.id).order_by(Equipment.name)
        )

    trigger_node_id = f"sim_{payload.scenario_type}"
    production_node_id = "production_forecast"
    risk_node_id = "risk_event_sim"

    nodes = [
        GraphNode(
            id=trigger_node_id,
            label=f"Simulated: {scenario_label} at {site.name}",
            type="SimulatedEvent",
        )
    ]
    edges = []
    affected_path = [trigger_node_id]

    if equipment_row is not None:
        equipment_node_id = f"equipment_{equipment_row.id}"
        nodes.append(
            GraphNode(id=equipment_node_id, label=equipment_row.name, type="Equipment")
        )
        edges.append(
            GraphEdge(
                source=trigger_node_id, target=equipment_node_id, relationship="TRIGGERS"
            )
        )
        edges.append(
            GraphEdge(
                source=equipment_node_id,
                target=production_node_id,
                relationship="REDUCES",
            )
        )
        affected_path.append(equipment_node_id)
    else:
        edges.append(
            GraphEdge(
                source=trigger_node_id,
                target=production_node_id,
                relationship="REDUCES",
            )
        )

    nodes.append(
        GraphNode(
            id=production_node_id, label="Production Forecast", type="ProductionForecast"
        )
    )
    nodes.append(
        GraphNode(
            id=risk_node_id,
            label=f"Simulated {scenario_label} Risk",
            type="RiskEvent",
        )
    )
    edges.append(
        GraphEdge(
            source=production_node_id, target=risk_node_id, relationship="TRIGGERS"
        )
    )
    affected_path.append(production_node_id)
    affected_path.append(risk_node_id)

    updated_graph = CausalGraphOut(nodes=nodes, edges=edges)

    return SimulateResponse(
        before=before,
        after=after,
        affected_graph_path=affected_path,
        updated_graph=updated_graph,
    )
