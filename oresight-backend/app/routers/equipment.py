"""Routes for mining equipment: list and status updates."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Equipment, EquipmentStatus, RiskEvent, RiskSeverity
from app.schemas import EquipmentOut, EquipmentStatusUpdate
from app.services.lookups import get_equipment_or_404

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _equipment_to_out(equipment: Equipment) -> EquipmentOut:
    return EquipmentOut(
        id=equipment.id,
        site_id=equipment.site_id,
        site_name=equipment.site.name,
        name=equipment.name,
        equipment_type=equipment.equipment_type,
        status=equipment.status.value,
        last_status_change=equipment.last_status_change,
        status_reason=equipment.status_reason,
    )


@router.get("", response_model=list[EquipmentOut], summary="List equipment")
def list_equipment(
    site_id: int | None = Query(None, description="Filter to one site's equipment"),
    db: Session = Depends(get_db),
) -> list[EquipmentOut]:
    """Return equipment, optionally filtered to a single site."""
    stmt = (
        select(Equipment).options(joinedload(Equipment.site)).order_by(Equipment.name)
    )
    if site_id is not None:
        stmt = stmt.where(Equipment.site_id == site_id)
    equipment_rows = db.scalars(stmt).all()
    return [_equipment_to_out(e) for e in equipment_rows]


@router.post(
    "/{equipment_id}/status",
    response_model=EquipmentOut,
    summary="Update an equipment's status",
)
def update_equipment_status(
    equipment_id: int,
    payload: EquipmentStatusUpdate,
    db: Session = Depends(get_db),
) -> EquipmentOut:
    """Update an equipment's status and reason. Marking it 'down' also opens a
    high-severity `equipment_failure` risk event for its site.
    """
    equipment = get_equipment_or_404(db, equipment_id)

    equipment.status = EquipmentStatus(payload.status)
    equipment.status_reason = payload.reason
    equipment.last_status_change = datetime.now(timezone.utc)

    if equipment.status == EquipmentStatus.DOWN:
        db.add(
            RiskEvent(
                site_id=equipment.site_id,
                risk_type="equipment_failure",
                severity=RiskSeverity.HIGH,
                score=0.7,
                description=(
                    f"{equipment.name} at {equipment.site.name} is down"
                    f"{f': {payload.reason}' if payload.reason else '.'}"
                ),
                source_entity_type="equipment",
                source_entity_id=equipment.id,
                resolved=False,
            )
        )

    db.commit()
    db.refresh(equipment)
    return _equipment_to_out(equipment)
