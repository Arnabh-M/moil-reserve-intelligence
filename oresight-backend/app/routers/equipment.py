"""Routes for mining equipment: list, status updates, and status history."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.models import (
    Equipment,
    EquipmentStatus,
    EquipmentStatusLog,
    RiskEvent,
    RiskSeverity,
)
from app.schemas import (
    EquipmentHistoryPage,
    EquipmentOut,
    EquipmentStatusLogOut,
    EquipmentStatusUpdate,
)
from app.services.lookups import get_equipment_or_404, get_site_or_404

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _equipment_to_out(equipment: Equipment, flapping: bool = False) -> EquipmentOut:
    return EquipmentOut(
        id=equipment.id,
        site_id=equipment.site_id,
        site_name=equipment.site.name,
        name=equipment.name,
        equipment_type=equipment.equipment_type,
        status=equipment.status.value,
        last_status_change=equipment.last_status_change,
        status_reason=equipment.status_reason,
        flapping=flapping,
    )


@router.get("", response_model=list[EquipmentOut], summary="List equipment")
def list_equipment(
    site_id: int | None = Query(None, description="Filter to one site's equipment"),
    db: Session = Depends(get_db),
) -> list[EquipmentOut]:
    """Return equipment, optionally filtered to a single site."""
    if site_id is not None:
        get_site_or_404(db, site_id)

    stmt = (
        select(Equipment).options(joinedload(Equipment.site)).order_by(Equipment.name)
    )
    if site_id is not None:
        stmt = stmt.where(Equipment.site_id == site_id)
    equipment_rows = db.scalars(stmt).all()
    return [_equipment_to_out(e) for e in equipment_rows]


@router.get(
    "/history",
    response_model=list[EquipmentStatusLogOut],
    summary="Site-wide equipment status history",
)
def list_equipment_history(
    site_id: int | None = Query(None, description="Filter to one site"),
    since: datetime | None = Query(None, description="Only rows changed at or after this time"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EquipmentStatusLogOut]:
    """Newest-first status-change history across a site (or every site)."""
    if site_id is not None:
        get_site_or_404(db, site_id)

    stmt = select(EquipmentStatusLog).order_by(EquipmentStatusLog.changed_at.desc())
    if site_id is not None:
        stmt = stmt.where(EquipmentStatusLog.site_id == site_id)
    if since is not None:
        stmt = stmt.where(EquipmentStatusLog.changed_at >= since)
    rows = db.scalars(stmt.limit(limit)).all()
    return [EquipmentStatusLogOut.model_validate(row) for row in rows]


@router.get(
    "/{equipment_id}/history",
    response_model=EquipmentHistoryPage,
    summary="One equipment unit's status history",
)
def get_equipment_history(
    equipment_id: int,
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = Query(None, description="Cursor: only rows changed before this time"),
    db: Session = Depends(get_db),
) -> EquipmentHistoryPage:
    """Cursor-paginated (on `changed_at`), newest-first. Pass the previous
    page's `next_cursor` as `before` to fetch the next page.
    """
    get_equipment_or_404(db, equipment_id)

    stmt = (
        select(EquipmentStatusLog)
        .where(EquipmentStatusLog.equipment_id == equipment_id)
        .order_by(EquipmentStatusLog.changed_at.desc())
    )
    if before is not None:
        stmt = stmt.where(EquipmentStatusLog.changed_at < before)
    rows = db.scalars(stmt.limit(limit)).all()
    next_cursor = rows[-1].changed_at if len(rows) == limit else None
    return EquipmentHistoryPage(
        items=[EquipmentStatusLogOut.model_validate(row) for row in rows],
        next_cursor=next_cursor,
    )


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
    """Update an equipment's status and reason. Transitioning it from 'up' to
    'down' also opens a high-severity `equipment_failure` risk event for its
    site — re-posting 'down' while it's already down (e.g. just to update the
    reason text) does not open a second one.

    Also writes one `equipment_status_log` row in the same transaction as the
    status update (Field Intake Hardening §2.1) — if the log insert fails,
    the whole request fails, so history is never silently incomplete. If that
    row pushes the equipment's log count within
    `EQUIPMENT_FLAP_WINDOW_HOURS` above `EQUIPMENT_FLAP_THRESHOLD`, one
    medium-severity `equipment_flapping` risk event is opened (deduped the
    same way as `equipment_failure`), and the response's additive `flapping`
    field reflects the current flap state regardless of whether a new event
    was opened.
    """
    equipment = get_equipment_or_404(db, equipment_id)
    was_down = equipment.status == EquipmentStatus.DOWN
    old_status = equipment.status.value

    equipment.status = EquipmentStatus(payload.status)
    equipment.status_reason = payload.reason
    equipment.last_status_change = datetime.now(timezone.utc)

    if equipment.status == EquipmentStatus.DOWN and not was_down:
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

    db.add(
        EquipmentStatusLog(
            equipment_id=equipment.id,
            site_id=equipment.site_id,
            old_status=old_status,
            new_status=equipment.status.value,
            reason=payload.reason,
            source=payload.source,
        )
    )
    db.flush()  # so the row just added counts toward the flap-window query below

    settings = get_settings()
    window_start = datetime.now(timezone.utc) - timedelta(
        hours=settings.EQUIPMENT_FLAP_WINDOW_HOURS
    )
    recent_change_count = db.scalar(
        select(func.count())
        .select_from(EquipmentStatusLog)
        .where(
            EquipmentStatusLog.equipment_id == equipment.id,
            EquipmentStatusLog.changed_at >= window_start,
        )
    )
    is_flapping = recent_change_count > settings.EQUIPMENT_FLAP_THRESHOLD

    if is_flapping:
        existing_flap_event = db.scalar(
            select(RiskEvent).where(
                RiskEvent.risk_type == "equipment_flapping",
                RiskEvent.source_entity_type == "equipment",
                RiskEvent.source_entity_id == equipment.id,
                RiskEvent.resolved.is_(False),
            )
        )
        if existing_flap_event is None:
            db.add(
                RiskEvent(
                    site_id=equipment.site_id,
                    risk_type="equipment_flapping",
                    severity=RiskSeverity.MEDIUM,
                    score=0.45,
                    description=(
                        f"{equipment.name} at {equipment.site.name} has changed status "
                        f"{recent_change_count} times in the last "
                        f"{settings.EQUIPMENT_FLAP_WINDOW_HOURS}h."
                    ),
                    source_entity_type="equipment",
                    source_entity_id=equipment.id,
                    resolved=False,
                )
            )

    db.commit()
    db.refresh(equipment)
    return _equipment_to_out(equipment, flapping=is_flapping)
