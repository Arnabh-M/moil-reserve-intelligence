"""Routes for blast events: planning, outcome updates, and delay analysis.

SIH26009 names blasting delays as a production-shortfall driver. This router
captures the plan/outcome pair per blast and aggregates the tonnes lost by
delay reason, so the shortfall story can be attributed rather than guessed.
"""

from datetime import date as date_

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BlastDelayReason, BlastEvent, BlastStatus
from app.schemas import (
    BlastDelaySummaryRow,
    BlastEventCreate,
    BlastEventOut,
    BlastEventUpdate,
)
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/blast-events", tags=["blasting"])

# Statuses whose expected tonnes never came out of the ground.
LOST_TONNAGE_STATUSES = (BlastStatus.DELAYED, BlastStatus.CANCELLED)


def _get_blast_event_or_404(db: Session, blast_event_id: int) -> BlastEvent:
    blast_event = db.get(BlastEvent, blast_event_id)
    if blast_event is None:
        raise HTTPException(
            status_code=404, detail=f"Blast event {blast_event_id} not found"
        )
    return blast_event


def _blast_event_to_out(blast_event: BlastEvent) -> BlastEventOut:
    return BlastEventOut(
        id=blast_event.id,
        site_id=blast_event.site_id,
        reserve_zone_id=blast_event.reserve_zone_id,
        planned_date=blast_event.planned_date,
        actual_date=blast_event.actual_date,
        status=blast_event.status.value,
        delay_reason=(
            blast_event.delay_reason.value if blast_event.delay_reason else None
        ),
        expected_yield_tonnes=float(blast_event.expected_yield_tonnes),
        actual_yield_tonnes=(
            float(blast_event.actual_yield_tonnes)
            if blast_event.actual_yield_tonnes is not None
            else None
        ),
        notes=blast_event.notes,
        created_at=blast_event.created_at,
        updated_at=blast_event.updated_at,
    )


@router.get("", response_model=list[BlastEventOut], summary="List blast events")
def list_blast_events(
    site_id: int | None = Query(None, description="Filter to one site's blasts"),
    status: str | None = Query(
        None, description="Filter by status: planned/completed/delayed/cancelled"
    ),
    db: Session = Depends(get_db),
) -> list[BlastEventOut]:
    """Return blast events, newest planned date first."""
    if site_id is not None:
        get_site_or_404(db, site_id)

    stmt = select(BlastEvent).order_by(
        BlastEvent.planned_date.desc(), BlastEvent.id.desc()
    )
    if site_id is not None:
        stmt = stmt.where(BlastEvent.site_id == site_id)
    if status is not None:
        try:
            stmt = stmt.where(BlastEvent.status == BlastStatus(status))
        except ValueError:
            raise HTTPException(
                status_code=422, detail=f"Unknown blast status '{status}'"
            ) from None

    return [_blast_event_to_out(b) for b in db.scalars(stmt).all()]


@router.get(
    "/summary",
    response_model=list[BlastDelaySummaryRow],
    summary="Tonnes lost grouped by delay reason",
)
def get_blast_delay_summary(
    site_id: int | None = Query(None, description="Filter to one site's blasts"),
    from_: date_ | None = Query(
        None, alias="from", description="Only blasts planned on/after this date"
    ),
    to: date_ | None = Query(
        None, description="Only blasts planned on/before this date"
    ),
    db: Session = Depends(get_db),
) -> list[BlastDelaySummaryRow]:
    """Aggregate lost tonnage by delay reason across `delayed` and `cancelled`
    blasts. Completed and still-planned blasts are excluded: nothing is lost
    yet on a blast that either fired or has not come due.

    `tonnes_lost` is expected minus whatever was actually recovered, treating a
    missing actual yield as zero.
    """
    if site_id is not None:
        get_site_or_404(db, site_id)

    recovered = func.coalesce(func.sum(BlastEvent.actual_yield_tonnes), 0)
    expected = func.coalesce(func.sum(BlastEvent.expected_yield_tonnes), 0)

    stmt = (
        select(
            BlastEvent.delay_reason,
            func.count(BlastEvent.id).label("event_count"),
            expected.label("expected_yield_tonnes"),
            recovered.label("actual_yield_tonnes"),
            (expected - recovered).label("tonnes_lost"),
        )
        .where(BlastEvent.status.in_(LOST_TONNAGE_STATUSES))
        .group_by(BlastEvent.delay_reason)
        .order_by((expected - recovered).desc())
    )
    if site_id is not None:
        stmt = stmt.where(BlastEvent.site_id == site_id)
    if from_ is not None:
        stmt = stmt.where(BlastEvent.planned_date >= from_)
    if to is not None:
        stmt = stmt.where(BlastEvent.planned_date <= to)

    return [
        BlastDelaySummaryRow(
            delay_reason=reason.value if reason else None,
            event_count=count,
            expected_yield_tonnes=float(expected_sum),
            actual_yield_tonnes=float(actual_sum),
            tonnes_lost=float(lost),
        )
        for reason, count, expected_sum, actual_sum, lost in db.execute(stmt).all()
    ]


@router.get(
    "/{blast_event_id}", response_model=BlastEventOut, summary="Get one blast event"
)
def get_blast_event(
    blast_event_id: int, db: Session = Depends(get_db)
) -> BlastEventOut:
    """Return a single blast event, or 404 if it does not exist."""
    return _blast_event_to_out(_get_blast_event_or_404(db, blast_event_id))


@router.post(
    "",
    response_model=BlastEventOut,
    status_code=201,
    summary="Plan a blast",
)
def create_blast_event(
    payload: BlastEventCreate, db: Session = Depends(get_db)
) -> BlastEventOut:
    """Log a planned blast. Always starts at status `planned`; the outcome is
    recorded later via PATCH.
    """
    get_site_or_404(db, payload.site_id)

    blast_event = BlastEvent(
        site_id=payload.site_id,
        reserve_zone_id=payload.reserve_zone_id,
        planned_date=payload.planned_date,
        expected_yield_tonnes=payload.expected_yield_tonnes,
        notes=payload.notes,
        status=BlastStatus.PLANNED,
    )
    db.add(blast_event)
    db.commit()
    db.refresh(blast_event)
    return _blast_event_to_out(blast_event)


@router.patch(
    "/{blast_event_id}",
    response_model=BlastEventOut,
    summary="Record a blast's outcome",
)
def update_blast_event(
    blast_event_id: int, payload: BlastEventUpdate, db: Session = Depends(get_db)
) -> BlastEventOut:
    """Update a blast's outcome.

    - Moving to `delayed`/`cancelled` requires a `delay_reason`, either in this
      request or already stored on the row -> otherwise 422.
    - Moving to `completed` requires `actual_date` and `actual_yield_tonnes`
      -> otherwise 422.
    """
    blast_event = _get_blast_event_or_404(db, blast_event_id)

    new_status = BlastStatus(payload.status) if payload.status else blast_event.status
    delay_reason = (
        BlastDelayReason(payload.delay_reason)
        if payload.delay_reason
        else blast_event.delay_reason
    )
    actual_date = (
        payload.actual_date if payload.actual_date is not None else blast_event.actual_date
    )
    actual_yield = (
        payload.actual_yield_tonnes
        if payload.actual_yield_tonnes is not None
        else blast_event.actual_yield_tonnes
    )

    if new_status in LOST_TONNAGE_STATUSES and delay_reason is None:
        raise HTTPException(
            status_code=422,
            detail=f"A delay_reason is required when status is '{new_status.value}'",
        )
    if new_status == BlastStatus.COMPLETED:
        missing = [
            name
            for name, value in (
                ("actual_date", actual_date),
                ("actual_yield_tonnes", actual_yield),
            )
            if value is None
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{' and '.join(missing)} "
                    f"{'are' if len(missing) > 1 else 'is'} required when status is "
                    "'completed'"
                ),
            )

    blast_event.status = new_status
    blast_event.delay_reason = delay_reason
    blast_event.actual_date = actual_date
    blast_event.actual_yield_tonnes = actual_yield
    if payload.notes is not None:
        blast_event.notes = payload.notes

    db.commit()
    db.refresh(blast_event)
    return _blast_event_to_out(blast_event)
