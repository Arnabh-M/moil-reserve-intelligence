"""Route for what-if scenario simulation.

Thin orchestration layer over `app.agents.simulator.SimulatorAgent` (P2's
module): request validation, error mapping, and response shaping only. The
forecasting model, feature perturbation, and graph traversal all live in the
agent and are not reimplemented here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from neo4j.exceptions import ServiceUnavailable
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.agents.simulator import SCENARIO_TYPES, SimulatorAgent
from app.db import get_db
from app.graph_db import get_graph_driver
from app.schemas import (
    CausalGraphOut,
    ConditionInput,
    ConditionOODStatus,
    SimStateSnapshot,
    SimulateRequest,
    SimulateResponse,
)

logger = logging.getLogger("oresight.simulate")

router = APIRouter(prefix="/simulate", tags=["simulation"])

_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def _load_training_ranges() -> dict | None:
    path = _MODELS_DIR / "training_data_ranges.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_conditions_distribution(
    conditions: list[ConditionInput] | None,
    default_scenario_type: str,
    default_duration_days: int,
    default_severity: float | None = None,
) -> tuple[bool, list[ConditionOODStatus], str | None]:
    """Check whether scenario conditions exceed the model's validated training bounds.

    Returns:
        (out_of_distribution: bool, conditions_ood: list[ConditionOODStatus], warning_message: str | None)
    """
    ranges = _load_training_ranges() or {
        "equipment_down": {
            "severity_min_pct": 0.0,
            "severity_max_pct": 5.3,
            "duration_min_days": 0.1,
            "duration_max_days": 1.9,
        },
        "delay_blasting": {
            "severity_min_pct": 0.4,
            "severity_max_pct": 34.9,
            "duration_min_days": 5.0,
            "duration_max_days": 10.0,
        },
        "rainfall_event": {
            "severity_min_pct": 14.6,
            "severity_max_pct": 100.0,
            "duration_min_days": 1.0,
            "duration_max_days": 30.0,
        },
    }

    cond_items: list[tuple[int, str, float | None, float | None]] = []
    if conditions and len(conditions) > 0:
        for idx, c in enumerate(conditions):
            c_type = c.type if hasattr(c, "type") else default_scenario_type
            c_sev = c.severity if hasattr(c, "severity") else None
            c_dur = c.duration if hasattr(c, "duration") else None
            cond_items.append((idx, c_type, c_sev, c_dur))
    else:
        cond_items.append(
            (0, default_scenario_type, default_severity, float(default_duration_days))
        )

    statuses: list[ConditionOODStatus] = []
    any_ood = False

    for idx, sc_type, sev, dur in cond_items:
        type_range = ranges.get(sc_type)
        sev_ood = False
        dur_ood = False
        warnings: list[str] = []
        sev_range: list[float] | None = None
        dur_range: list[float] | None = None

        if type_range:
            s_min = float(type_range.get("severity_min_pct", 0.0))
            s_max = float(type_range.get("severity_max_pct", 100.0))
            d_min = float(type_range.get("duration_min_days", 1.0))
            d_max = float(type_range.get("duration_max_days", 30.0))
            sev_range = [s_min, s_max]
            dur_range = [d_min, d_max]

            if sev is not None:
                if sev < s_min or sev > s_max:
                    sev_ood = True
                    warnings.append(
                        f"Severity {sev}% is outside validated training range ({s_min}–{s_max}%)."
                    )

            if dur is not None:
                if dur < d_min or dur > d_max:
                    dur_ood = True
                    warnings.append(
                        f"Duration {dur}d is outside validated training range ({d_min}–{d_max} days)."
                    )

        cond_is_ood = sev_ood or dur_ood
        if cond_is_ood:
            any_ood = True

        statuses.append(
            ConditionOODStatus(
                index=idx,
                scenario_type=sc_type,
                out_of_distribution=cond_is_ood,
                severity_out_of_distribution=sev_ood,
                duration_out_of_distribution=dur_ood,
                severity_value=float(sev) if sev is not None else None,
                duration_value=float(dur) if dur is not None else None,
                severity_valid_range=sev_range,
                duration_valid_range=dur_range,
                warnings=warnings,
            )
        )

    warning_msg: str | None = None
    if any_ood:
        ood_indices = [str(s.index + 1) for s in statuses if s.out_of_distribution]
        warning_msg = (
            f"Condition {', '.join(ood_indices)} has parameters outside the range the model was "
            "validated on. Treat projections with extra caution as results represent extrapolations."
        )

    return any_ood, statuses, warning_msg


@router.get(
    "/training-ranges",
    summary="Training data ranges for condition-type hints",
    response_model=None,
)
def training_ranges() -> dict:
    """Return per-condition-type severity/duration statistics derived from the
    training data CSVs.  Used by the Simulator UI to show honest range hints
    on each ConditionCard (e.g. "Typical range in training data: 0–5% severity,
    0.1–1.9 days").  Returns 503 if the ranges file hasn't been produced yet.
    """
    data = _load_training_ranges()
    if data is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Training data ranges are unavailable. "
                "Run train_shortfall_model.py to generate them."
            ),
        )
    return data


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

    try:
        agent = SimulatorAgent(db, driver)
    except (FileNotFoundError, OSError) as exc:
        # The trained shortfall model / feature-columns file isn't on disk.
        logger.error("SimulatorAgent could not load its model: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Forecasting model is unavailable on the server. Run train_shortfall_model.py.",
        ) from exc

    try:
        result = agent.run_scenario(
            payload.scenario_type,
            site_id=payload.site_id,
            duration_days=payload.duration_days,
        )
    except HTTPException:
        raise
    except (ServiceUnavailable, OperationalError, InterfaceError):
        # Neo4j or Postgres is down — let the app-level handlers turn these
        # into a clean 503 rather than masking them as a 502 engine failure.
        raise
    except ValueError as exc:
        # Defensive: agent rejects an unknown scenario_type this way.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - map any other engine failure to 502
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

    if payload.site_context or payload.current_reserve_confidence is not None:
        logger.debug(
            "Received unused site KPI context for future model retraining: site_id=%s, context=%s, conf=%s, var=%s",
            payload.site_id,
            payload.site_context,
            payload.current_reserve_confidence,
            payload.recent_production_variance,
        )

    any_ood, conditions_ood, ood_warning = evaluate_conditions_distribution(
        payload.conditions,
        default_scenario_type=payload.scenario_type,
        default_duration_days=payload.duration_days,
        default_severity=payload.severity,
    )

    return SimulateResponse(
        before=SimStateSnapshot(**result["before"]),
        after=SimStateSnapshot(**result["after"]),
        affected_graph_path=result["affected_graph_path"],
        updated_graph=updated_graph,
        uncertainty=result.get("uncertainty"),
        out_of_distribution=any_ood,
        conditions_ood=conditions_ood,
        out_of_distribution_warning=ood_warning,
    )

