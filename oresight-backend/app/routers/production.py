"""Routes for daily production records."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProductionRecord
from app.schemas import ProductionRecordCreate, ProductionRecordOut
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/production", tags=["production"])


def _variance_pct(actual: float | None, target: float | None) -> float | None:
    if actual is None or target is None or target == 0:
        return None
    return round((actual - target) / target * 100, 2)


def _record_to_out(record: ProductionRecord) -> ProductionRecordOut:
    return ProductionRecordOut(
        id=record.id,
        site_id=record.site_id,
        date=record.date,
        actual_output=record.actual_output,
        target_output=record.target_output,
        variance_pct=_variance_pct(record.actual_output, record.target_output),
    )


@router.get(
    "", response_model=list[ProductionRecordOut], summary="List production records"
)
def list_production_records(
    site_id: int | None = Query(None, description="Filter to one site"),
    days: int = Query(30, ge=1, le=365, description="How many trailing days to include"),
    db: Session = Depends(get_db),
) -> list[ProductionRecordOut]:
    """Return production records from the last `days` days, ordered oldest to
    newest. If fewer than `days` days of history exist (for the site, or at
    all), returns whatever is available rather than erroring or padding.
    """
    if site_id is not None:
        get_site_or_404(db, site_id)

    since = date.today() - timedelta(days=days)
    stmt = (
        select(ProductionRecord)
        .where(ProductionRecord.date >= since)
        .order_by(ProductionRecord.date.asc())
    )
    if site_id is not None:
        stmt = stmt.where(ProductionRecord.site_id == site_id)
    records = db.scalars(stmt).all()
    return [_record_to_out(r) for r in records]


@router.post(
    "",
    response_model=ProductionRecordOut,
    status_code=201,
    summary="Record a day's production",
)
def create_production_record(
    payload: ProductionRecordCreate, db: Session = Depends(get_db)
) -> ProductionRecordOut:
    """Insert a new production record. Returns 409 if one already exists for
    this site and date.
    """
    get_site_or_404(db, payload.site_id)

    existing = db.scalar(
        select(ProductionRecord).where(
            ProductionRecord.site_id == payload.site_id,
            ProductionRecord.date == payload.date,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A production record for site {payload.site_id} on "
                f"{payload.date} already exists"
            ),
        )

    record = ProductionRecord(
        site_id=payload.site_id,
        date=payload.date,
        actual_output=payload.actual_output,
        target_output=payload.target_output,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_to_out(record)
