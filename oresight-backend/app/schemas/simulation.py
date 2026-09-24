"""Pydantic schemas for the what-if simulation endpoint."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants.validation_limits import (
    RAINFALL_3D_MM_MAX,
    RAINFALL_3D_MM_MIN,
    SEVERITY_PCT_MAX,
    SEVERITY_PCT_MIN,
    SIMULATOR_CONDITION_DURATION_MAX_DAYS,
    SIMULATOR_CONDITION_DURATION_MIN_DAYS,
)
from app.schemas.causal_graph import CausalGraphOut


def _check_severity_bound(scenario_type: str, severity: float | None) -> None:
    """Severity is mm of 3-day rain for rainfall_event and a percentage for the other scenarios,
    so its upper bound depends on the scenario (the lower bound is 0 for both)."""
    if severity is None:
        return
    if scenario_type == "rainfall_event":
        if not RAINFALL_3D_MM_MIN <= severity <= RAINFALL_3D_MM_MAX:
            raise ValueError(f"rainfall_event severity is mm of 3-day rain and must be within {RAINFALL_3D_MM_MIN}-{RAINFALL_3D_MM_MAX}")
    elif not SEVERITY_PCT_MIN <= severity <= SEVERITY_PCT_MAX:
        raise ValueError(f"{scenario_type} severity is a percentage and must be within {SEVERITY_PCT_MIN}-{SEVERITY_PCT_MAX}")


class ConditionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["equipment_down", "delay_blasting", "rainfall_event"]
    equipment: str | None = None
    severity: float | None = Field(None, ge=0)  # unit and upper bound depend on the scenario type; see _check_severity_bound
    duration: float | None = Field(
        None, ge=SIMULATOR_CONDITION_DURATION_MIN_DAYS, le=SIMULATOR_CONDITION_DURATION_MAX_DAYS
    )

    @model_validator(mode="after")
    def _severity_within_scenario_bound(self) -> "ConditionInput":
        _check_severity_bound(self.type, self.severity)
        return self


class SiteContextInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reserve_confidence: float | None = None
    production_variance: float | None = None
    active_conditions_count: int | None = None


class SimulateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "scenario_type": "equipment_down",
                "site_id": 1,
                "duration_days": 5,
            }
        },
    )

    scenario_type: Literal["equipment_down", "delay_blasting", "rainfall_event"]
    site_id: int
    # 1-90 is the simulator's own validated range, tighter than the generic
    # simulator-lever bound elsewhere — left as-is, not touched by this task.
    duration_days: int = Field(..., ge=1, le=90)
    severity: float | None = Field(None, ge=0)  # unit and upper bound depend on the scenario type; see _check_severity_bound
    conditions: list[ConditionInput] | None = None
    site_context: SiteContextInput | None = None
    current_reserve_confidence: float | None = None
    recent_production_variance: float | None = None

    @model_validator(mode="after")
    def _severity_within_scenario_bound(self) -> "SimulateRequest":
        _check_severity_bound(self.scenario_type, self.severity)
        return self


class SimStateSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reserve_confidence: float
    production_forecast_tonnes: float
    risk_score: float


class UncertaintyMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_rmse: float
    model_mae: float
    residual_std: float
    production_impact_uncertainty_tonnes: float
    risk_uncertainty: float
    reserve_confidence_uncertainty: float
    downtime_uncertainty_days: float


class ConditionOODStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int = 0
    scenario_type: str
    out_of_distribution: bool = False
    severity_out_of_distribution: bool = False
    duration_out_of_distribution: bool = False
    severity_value: float | None = None
    duration_value: float | None = None
    severity_valid_range: list[float] | None = None
    duration_valid_range: list[float] | None = None
    warnings: list[str] = Field(default_factory=list)


class SimulateResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "before": {
                    "reserve_confidence": 0.67,
                    "production_forecast_tonnes": 1187.3,
                    "risk_score": 0.42,
                },
                "after": {
                    "reserve_confidence": 0.663,
                    "production_forecast_tonnes": 950.8,
                    "risk_score": 0.67,
                },
                "affected_graph_path": [
                    "sim_equipment_down",
                    "equipment_1",
                    "production_forecast",
                    "risk_event_sim",
                ],
                "updated_graph": {
                    "nodes": [
                        {
                            "id": "sim_equipment_down",
                            "label": "Simulated: Equipment Down at Balaghat",
                            "type": "SimulatedEvent",
                        },
                        {
                            "id": "equipment_1",
                            "label": "Excavator EX-201",
                            "type": "Equipment",
                        },
                        {
                            "id": "production_forecast",
                            "label": "Production Forecast",
                            "type": "ProductionForecast",
                        },
                        {
                            "id": "risk_event_sim",
                            "label": "Simulated Equipment Down Risk",
                            "type": "RiskEvent",
                        },
                    ],
                    "edges": [
                        {
                            "source": "sim_equipment_down",
                            "target": "equipment_1",
                            "relationship": "TRIGGERS",
                        },
                        {
                            "source": "equipment_1",
                            "target": "production_forecast",
                            "relationship": "REDUCES",
                        },
                        {
                            "source": "production_forecast",
                            "target": "risk_event_sim",
                            "relationship": "TRIGGERS",
                        },
                    ],
                },
                "uncertainty": {
                    "model_rmse": 0.158,
                    "model_mae": 0.1177,
                    "residual_std": 0.153,
                    "production_impact_uncertainty_tonnes": 137.7,
                    "risk_uncertainty": 0.306,
                    "reserve_confidence_uncertainty": 0.007,
                    "downtime_uncertainty_days": 0.5,
                },
                "out_of_distribution": False,
                "conditions_ood": [],
                "out_of_distribution_warning": None,
            }
        },
    )

    before: SimStateSnapshot
    after: SimStateSnapshot
    affected_graph_path: list[str]
    updated_graph: CausalGraphOut
    uncertainty: UncertaintyMetrics | None = None
    out_of_distribution: bool = False
    conditions_ood: list[ConditionOODStatus] = Field(default_factory=list)
    out_of_distribution_warning: str | None = None
    # The calendar day the model's "before" state describes: the latest finished day with a complete
    # observed rain record, not necessarily today (satellite rain lags 1-3 days). Never hidden.
    model_state_as_of: date | None = None
    # Model inputs no source could supply for that day (passed to the model as NaN, never filled in).
    model_inputs_missing: list[str] = Field(default_factory=list)
