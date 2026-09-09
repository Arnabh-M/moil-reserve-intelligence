"""Pydantic schemas for the what-if simulation endpoint."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.causal_graph import CausalGraphOut


class ConditionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["equipment_down", "delay_blasting", "rainfall_event"]
    equipment: str | None = None
    severity: float | None = None
    duration: float | None = None


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
    duration_days: int = Field(..., ge=1, le=90)
    severity: float | None = None
    conditions: list[ConditionInput] | None = None
    site_context: SiteContextInput | None = None
    current_reserve_confidence: float | None = None
    recent_production_variance: float | None = None



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
