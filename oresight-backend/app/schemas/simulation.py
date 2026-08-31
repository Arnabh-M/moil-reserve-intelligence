"""Pydantic schemas for the what-if simulation endpoint."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.causal_graph import CausalGraphOut


class SimulateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scenario_type": "equipment_down",
                "site_id": 1,
                "duration_days": 5,
            }
        }
    )

    scenario_type: Literal["equipment_down", "delay_blasting", "rainfall_event"]
    site_id: int
    duration_days: int = Field(..., ge=1, le=90)


class SimStateSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reserve_confidence: float
    production_forecast_tonnes: float
    risk_score: float


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
            }
        },
    )

    before: SimStateSnapshot
    after: SimStateSnapshot
    affected_graph_path: list[str]
    updated_graph: CausalGraphOut
