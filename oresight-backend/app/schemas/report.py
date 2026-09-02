"""Pydantic schemas for the survey-report upload / extraction endpoint.

`ExtractedDeposit` is the *entire* contract between the text extractor
(app.services.extraction) and everything downstream — the route and the
Neo4j write path only ever see this shape, never the raw PDF text or any
extractor internals. Swapping the deterministic parser for an LLM-backed
one later must keep returning exactly this.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.causal_graph import GraphNode


class ExtractedDeposit(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "deposit_id": "BAL-D1",
                "depth": 145.2,
                "grade": 38.5,
                "structure_type": "fold_axis",
                "belt_zone": "Balaghat-Manganese Belt",
            }
        },
    )

    deposit_id: str
    depth: float | None = Field(None, description="Borehole / deposit depth in metres")
    grade: float | None = Field(None, description="Average Mn grade, percent")
    structure_type: str | None = Field(
        None, description="Dominant structural feature, canonicalised (fold_axis, fault_line, shear_zone, …)"
    )
    belt_zone: str | None = Field(
        None, description="Manganese belt / zone the deposit sits in, as written in the source"
    )


class ReportUploadOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "filename": "balaghat_survey_2026.pdf",
                "text_extracted": True,
                "deposit_count": 2,
                "deposits": [
                    {
                        "deposit_id": "BAL-D1",
                        "depth": 145.2,
                        "grade": 38.5,
                        "structure_type": "fold_axis",
                        "belt_zone": "Balaghat-Manganese Belt",
                    },
                    {
                        "deposit_id": "BAL-D2",
                        "depth": 98.0,
                        "grade": 24.1,
                        "structure_type": "fault_line",
                        "belt_zone": "Balaghat-Manganese Belt",
                    },
                ],
                "nodes_created": [
                    {"id": "oz_upload_bal_d1", "label": "BAL-D1", "type": "OreZone"},
                    {"id": "sf_upload_bal_d1", "label": "fold_axis (BAL-D1)", "type": "StructuralFeature"},
                ],
                "warnings": [],
            }
        },
    )

    filename: str
    text_extracted: bool
    deposit_count: int
    deposits: list[ExtractedDeposit]
    # Neo4j nodes MERGE-d as a result of this upload, in the same
    # {id,label,type} shape the causal-graph endpoints use.
    nodes_created: list[GraphNode]
    warnings: list[str] = []
