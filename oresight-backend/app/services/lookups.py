"""Shared 'fetch or 404' helpers used across routers."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Equipment, RiskEvent, Site


def get_site_or_404(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site


def get_equipment_or_404(db: Session, equipment_id: int) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    return equipment


def get_risk_event_or_404(db: Session, risk_event_id: int) -> RiskEvent:
    risk_event = db.get(RiskEvent, risk_event_id)
    if risk_event is None:
        raise HTTPException(status_code=404, detail=f"Risk event {risk_event_id} not found")
    return risk_event
