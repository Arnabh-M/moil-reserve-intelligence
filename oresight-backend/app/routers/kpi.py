"""Route for the Command Center KPI summary."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Equipment, ReserveZone, RiskEvent
from app.schemas import KPISummaryOut

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get(
    "/summary",
    response_model=KPISummaryOut,
    summary="Get Command Center KPI summary",
)
def get_kpi_summary(db: Session = Depends(get_db)) -> KPISummaryOut:
    """Return the 4 headline KPIs for the Command Center dashboard: active
    risk events, average reserve confidence, sites currently under watch
    (i.e. with at least one active risk), and when the twin state was last
    updated.
    """
    active_risk_events = (
        db.scalar(
            select(func.count())
            .select_from(RiskEvent)
            .where(RiskEvent.resolved.is_(False))
        )
        or 0
    )

    avg_reserve_confidence = db.scalar(select(func.avg(ReserveZone.confidence_score)))

    sites_under_watch = (
        db.scalar(
            select(func.count(func.distinct(RiskEvent.site_id))).where(
                RiskEvent.resolved.is_(False)
            )
        )
        or 0
    )

    latest_risk = db.scalar(select(func.max(RiskEvent.detected_at)))
    latest_zone_update = db.scalar(select(func.max(ReserveZone.last_updated)))
    latest_equipment_change = db.scalar(select(func.max(Equipment.last_status_change)))

    candidates = [
        t for t in (latest_risk, latest_zone_update, latest_equipment_change) if t is not None
    ]
    twin_last_updated = max(candidates) if candidates else None

    return KPISummaryOut(
        active_risk_events=active_risk_events,
        avg_reserve_confidence=(
            round(avg_reserve_confidence, 3) if avg_reserve_confidence is not None else None
        ),
        sites_under_watch=sites_under_watch,
        twin_last_updated=twin_last_updated,
    )
