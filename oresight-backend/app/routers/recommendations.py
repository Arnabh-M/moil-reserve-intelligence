"""Route for AI-generated mitigation recommendations.

Thin orchestration layer: this endpoint does auth-free request handling and
error mapping only. All candidate search, simulation-backed scoring, and
ranking lives in `app.agents.planner.PlannerAgent` (P2's module) and is not
duplicated or second-guessed here.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from neo4j.exceptions import ServiceUnavailable
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.agents.planner import PlannerAgent
from app.db import get_db
from app.graph_db import get_graph_driver
from app.schemas import RecommendationOut
from app.services.lookups import get_risk_event_or_404

logger = logging.getLogger("oresight.recommendations")

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
    driver: Driver = Depends(get_graph_driver),
) -> list[RecommendationOut]:
    """Return ranked mitigation options for a risk event.

    Pass-through to `PlannerAgent.get_recommendations()`, which returns one
    `RecommendationOut`-shaped dict (trigger + options sorted by projected
    impact). It is wrapped in a list to match the response model; extend the
    agent if multiple recommendation angles are ever needed.

    - Risk event not found -> 404 (raised by the agent via the shared
      `get_risk_event_or_404` lookup).
    - Anything else that goes wrong inside the engine -> 502, so the caller
      gets a clear "upstream failed" rather than an opaque 500.
    """
    # Fail fast with a clean 404 before constructing the agent.
    get_risk_event_or_404(db, risk_event_id)

    try:
        agent = PlannerAgent(db, driver)
    except (FileNotFoundError, OSError) as exc:
        # PlannerAgent builds a SimulatorAgent, which loads the trained model.
        logger.error("PlannerAgent could not load its model: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Forecasting model is unavailable on the server. Run train_shortfall_model.py.",
        ) from exc

    try:
        result = agent.get_recommendations(risk_event_id)
    except HTTPException:
        raise
    except (ServiceUnavailable, OperationalError, InterfaceError):
        # Neo4j or Postgres is down — let the app-level handlers turn these
        # into a clean 503 rather than masking them as a 502 engine failure.
        raise
    except Exception as exc:  # noqa: BLE001 - map any other engine failure to 502
        logger.exception(
            "PlannerAgent failed for risk_event_id=%s", risk_event_id
        )
        raise HTTPException(
            status_code=502,
            detail="Recommendation engine failed to produce a result.",
        ) from exc

    return [RecommendationOut(**result)]
