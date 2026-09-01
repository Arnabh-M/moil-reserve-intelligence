"""Route for what-if scenario simulation.

Thin orchestration layer over `app.agents.simulator.SimulatorAgent` (P2's
module): request validation, error mapping, and response shaping only. The
forecasting model, feature perturbation, and graph traversal all live in the
agent and are not reimplemented here.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from sqlalchemy.orm import Session

from app.agents.simulator import SCENARIO_TYPES, SimulatorAgent
from app.db import get_db
from app.graph_db import get_graph_driver
from app.schemas import CausalGraphOut, SimStateSnapshot, SimulateRequest, SimulateResponse

logger = logging.getLogger("oresight.simulate")

router = APIRouter(prefix="/simulate", tags=["simulation"])


@router.post(
    "", response_model=SimulateResponse, summary="Run a what-if scenario simulation"
)
def simulate(
    payload: SimulateRequest,
    db: Session = Depends(get_db),
    driver: Driver = Depends(get_graph_driver),
) -> SimulateResponse:
    """Project a disruption scenario's before/after impact on one site.

    Pass-through to `SimulatorAgent.run_scenario()`. `scenario_type` is
    constrained to `equipment_down | delay_blasting | rainfall_event` by the
    request schema (FastAPI returns 422 for anything else); it is
    re-checked here against the agent's own supported set so a drift between
    the two is a clean 422, never a 500.

    - Unknown `site_id` -> 404 (from the agent's `get_site_or_404`).
    - `duration_days` outside 1..90 -> 422 (request schema).
    - Engine failure -> 502.
    """
    if payload.scenario_type not in SCENARIO_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported scenario_type {payload.scenario_type!r}; "
                f"must be one of {sorted(SCENARIO_TYPES)}."
            ),
        )

    agent = SimulatorAgent(db, driver)
    try:
        result = agent.run_scenario(
            payload.scenario_type,
            site_id=payload.site_id,
            duration_days=payload.duration_days,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        # Defensive: agent rejects an unknown scenario_type this way.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - map any engine failure to 502
        logger.exception(
            "SimulatorAgent failed for scenario=%s site=%s",
            payload.scenario_type,
            payload.site_id,
        )
        raise HTTPException(
            status_code=502, detail="Simulation engine failed to produce a result."
        ) from exc

    updated_graph = CausalGraphOut(
        nodes=result["updated_graph"]["nodes"],
        edges=result["updated_graph"]["edges"],
        graph_source="simulated",
    )

    return SimulateResponse(
        before=SimStateSnapshot(**result["before"]),
        after=SimStateSnapshot(**result["after"]),
        affected_graph_path=result["affected_graph_path"],
        updated_graph=updated_graph,
    )
