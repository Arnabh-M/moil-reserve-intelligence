"""Pydantic schemas package — import every schema so `from app.schemas import X` works."""

from app.schemas.admin import JobStatusOut
from app.schemas.causal_graph import CausalGraphOut, GraphEdge, GraphNode
from app.schemas.demo import DemoScenarioOut
from app.schemas.equipment import EquipmentOut, EquipmentStatusUpdate
from app.schemas.kpi import KPISummaryOut
from app.schemas.production import ProductionRecordCreate, ProductionRecordOut
from app.schemas.recommendation import RecommendationOption, RecommendationOut
from app.schemas.report import ExtractedDeposit, ReportUploadOut
from app.schemas.risk_event import RiskEventOut
from app.schemas.simulation import SimStateSnapshot, SimulateRequest, SimulateResponse
from app.schemas.site import SiteOut
from app.schemas.site_note import SiteNoteCreate, SiteNoteOut, SiteNoteSearchHit

__all__ = [
    "JobStatusOut",
    "CausalGraphOut",
    "GraphEdge",
    "GraphNode",
    "DemoScenarioOut",
    "EquipmentOut",
    "EquipmentStatusUpdate",
    "KPISummaryOut",
    "ProductionRecordCreate",
    "ProductionRecordOut",
    "RecommendationOption",
    "RecommendationOut",
    "ExtractedDeposit",
    "ReportUploadOut",
    "RiskEventOut",
    "SimStateSnapshot",
    "SimulateRequest",
    "SimulateResponse",
    "SiteOut",
    "SiteNoteCreate",
    "SiteNoteOut",
    "SiteNoteSearchHit",
]
