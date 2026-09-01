"""Pydantic schemas for the causal graph visualisation (React Flow shaped)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class GraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    target: str
    relationship: str


class CausalGraphOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "nodes": [
                    {
                        "id": "weather_2026_03_14",
                        "label": "Heavy Rainfall 14 Mar",
                        "type": "WeatherEvent",
                    },
                    {
                        "id": "blast_plan_b204",
                        "label": "Blast Plan B-204",
                        "type": "BlastPlan",
                    },
                    {"id": "zone_b2", "label": "Zone B2", "type": "OreZone"},
                    {
                        "id": "equipment_ex201",
                        "label": "Excavator EX-201",
                        "type": "Equipment",
                    },
                    {
                        "id": "risk_event_shortfall",
                        "label": "Production shortfall risk",
                        "type": "RiskEvent",
                    },
                ],
                "edges": [
                    {
                        "source": "weather_2026_03_14",
                        "target": "blast_plan_b204",
                        "relationship": "DELAYS",
                    },
                    {
                        "source": "blast_plan_b204",
                        "target": "zone_b2",
                        "relationship": "AFFECTS",
                    },
                    {
                        "source": "equipment_ex201",
                        "target": "zone_b2",
                        "relationship": "OPERATES_IN",
                    },
                    {
                        "source": "zone_b2",
                        "target": "risk_event_shortfall",
                        "relationship": "CAUSES",
                    },
                ],
            }
        },
    )

    nodes: list[GraphNode]
    edges: list[GraphEdge]

    # Where this graph came from, so the frontend can tell a real traversal
    # apart from a degraded fallback and render an explicit banner instead of
    # what looks like an empty-graph rendering bug:
    #   "neo4j"            - live traversal of the causal graph
    #   "postgres_fallback"- the risk event exists in Postgres but has no
    #                        node in Neo4j yet (predates the graph sync);
    #                        `nodes` holds just the risk event itself
    #   "simulated"        - a what-if graph from POST /simulate, anchored on
    #                        real Neo4j nodes plus a synthetic trigger node
    graph_source: Literal["neo4j", "postgres_fallback", "simulated"] = "neo4j"
    note: str | None = None
