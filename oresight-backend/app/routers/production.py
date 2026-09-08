"""Routes for daily production records."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ProductionRecord, ProductionRecordAudit
from app.schemas import (
    ProductionRecordCreate,
    ProductionRecordOut,
    ProductionRecordUpdate,
    ProductionThresholdsOut,
    ShortfallReasonOut,
)
from app.schemas.production import SHORTFALL_REASONS, classify_variance
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/production", tags=["production"])

# Fields PATCH /production/{id} may change. Order matters only for the
# audit log's readability, not for behavior.
_PATCHABLE_FIELDS = (
    "actual_output",
    "target_output",
    "operating_hours",
    "downtime_hours",
    "material_processed",
    "quality_grade",
    "shortfall_reasons",
    "shortfall_other_note",
)


def _variance_pct(actual: float | None, target: float | None) -> float | None:
    if actual is None or target is None or target == 0:
        return None
    return round((actual - target) / target * 100, 2)


def _record_to_out(record: ProductionRecord) -> ProductionRecordOut:
    variance_pct = _variance_pct(record.actual_output, record.target_output)
    return ProductionRecordOut(
        id=record.id,
        site_id=record.site_id,
        date=record.date,
        shift=record.shift,
        actual_output=record.actual_output,
        target_output=record.target_output,
        variance_pct=variance_pct,
        variance_class=record.variance_class,
        operating_hours=(
            float(record.operating_hours) if record.operating_hours is not None else None
        ),
        downtime_hours=(
            float(record.downtime_hours) if record.downtime_hours is not None else None
        ),
        material_processed=(
            float(record.material_processed)
            if record.material_processed is not None
            else None
        ),
        quality_grade=(
            float(record.quality_grade) if record.quality_grade is not None else None
        ),
        shortfall_reasons=record.shortfall_reasons,
        shortfall_other_note=record.shortfall_other_note,
        created_at=record.created_at,
        updated_at=record.updated_at,
        created_by=record.created_by,
        updated_by=record.updated_by,
    )


def _require_reasons_if_significantly_below(
    variance_class: str | None, shortfall_reasons: list[str] | None
) -> None:
    if variance_class == "significantly_below" and not shortfall_reasons:
        raise HTTPException(
            status_code=422,
            detail=(
                "shortfall_reasons must include at least one reason when the "
                "record is significantly below target (variance <= "
                f"{-12.0}%)."
            ),
        )


# -- static sub-paths first: FastAPI matches routes in declaration order, and
# these must not be shadowed by a future GET /production/{id}. --------------


@router.get(
    "/shortfall-reasons",
    response_model=list[ShortfallReasonOut],
    summary="List the shortfall-reason vocabulary",
)
def list_shortfall_reasons() -> list[ShortfallReasonOut]:
    """The backend-owned source of truth for the Production tab's shortfall
    chips, so the frontend doesn't hardcode a second copy that can drift.
    """
    return [ShortfallReasonOut(value=v, label=label) for v, label in SHORTFALL_REASONS]


@router.get(
    "/thresholds",
    response_model=ProductionThresholdsOut,
    summary="Get the variance-classification thresholds",
)
def get_thresholds() -> ProductionThresholdsOut:
    """The same on_target/slightly_below/significantly_below cut points the
    server uses to compute `variance_class`, so the frontend's live preview
    never drifts from what gets persisted.
    """
    return ProductionThresholdsOut()


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
    this site, date, and shift.

    Cross-field validation (operating_hours + downtime_hours <= 24, an
    'other' shortfall reason requiring shortfall_other_note) is enforced by
    the request schema itself. The significantly-below-requires-a-reason
    rule can't live in the schema — it depends on the computed variance —
    so it's checked here instead.
    """
    get_site_or_404(db, payload.site_id)

    existing = db.scalar(
        select(ProductionRecord).where(
            ProductionRecord.site_id == payload.site_id,
            ProductionRecord.date == payload.date,
            ProductionRecord.shift == payload.shift,
        )
    )
    if existing is not None:
        shift_clause = f" ({payload.shift} shift)" if payload.shift != "general" else ""
        raise HTTPException(
            status_code=409,
            detail=(
                f"A production record for site {payload.site_id} on "
                f"{payload.date}{shift_clause} already exists"
            ),
        )

    variance_pct = _variance_pct(payload.actual_output, payload.target_output)
    variance_class = classify_variance(variance_pct)
    _require_reasons_if_significantly_below(variance_class, payload.shortfall_reasons)

    record = ProductionRecord(
        site_id=payload.site_id,
        date=payload.date,
        shift=payload.shift,
        actual_output=payload.actual_output,
        target_output=payload.target_output,
        operating_hours=payload.operating_hours,
        downtime_hours=payload.downtime_hours,
        material_processed=payload.material_processed,
        quality_grade=payload.quality_grade,
        shortfall_reasons=payload.shortfall_reasons or [],
        shortfall_other_note=payload.shortfall_other_note,
        variance_class=variance_class,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_to_out(record)


@router.patch(
    "/{record_id}",
    response_model=ProductionRecordOut,
    summary="Edit a production record within the edit window",
)
def update_production_record(
    record_id: int, payload: ProductionRecordUpdate, db: Session = Depends(get_db)
) -> ProductionRecordOut:
    """Partially update a production record and log every changed field to
    `production_record_audit`.

    - Unknown id -> 404.
    - Outside `PRODUCTION_EDIT_WINDOW_HOURS` since creation -> 403. (A
      supervisor-role bypass is planned for the auth phase — not implemented
      yet, so today this is a hard cutoff for everyone; see
      IMPLEMENTATION_NOTES.md.)
    - Same operating_hours+downtime_hours<=24 and significantly_below-needs-
      a-reason rules as POST, re-checked against the *resulting* record
      (existing values merged with whatever this PATCH changes).
    """
    record = db.get(ProductionRecord, record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Production record {record_id} not found"
        )

    settings = get_settings()
    window = timedelta(hours=settings.PRODUCTION_EDIT_WINDOW_HOURS)
    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > window:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This record was created more than "
                f"{settings.PRODUCTION_EDIT_WINDOW_HOURS}h ago and is outside "
                "the edit window. A supervisor override is planned but not "
                "yet available."
            ),
        )

    updates = payload.model_dump(exclude_unset=True)

    resulting_operating_hours = updates.get("operating_hours", record.operating_hours)
    resulting_downtime_hours = updates.get("downtime_hours", record.downtime_hours)
    if (
        resulting_operating_hours is not None
        and resulting_downtime_hours is not None
        and float(resulting_operating_hours) + float(resulting_downtime_hours) > 24
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "operating_hours + downtime_hours must not exceed 24 "
                f"(got {resulting_operating_hours} + {resulting_downtime_hours})"
            ),
        )

    resulting_actual = updates.get("actual_output", record.actual_output)
    resulting_target = updates.get("target_output", record.target_output)
    resulting_reasons = updates.get("shortfall_reasons", record.shortfall_reasons)
    resulting_other_note = updates.get(
        "shortfall_other_note", record.shortfall_other_note
    )

    if resulting_reasons and "other" in resulting_reasons and not (
        resulting_other_note and resulting_other_note.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="shortfall_other_note is required when shortfall_reasons includes 'other'",
        )

    resulting_variance_class = classify_variance(
        _variance_pct(resulting_actual, resulting_target)
    )
    _require_reasons_if_significantly_below(resulting_variance_class, resulting_reasons)

    audit_rows: list[ProductionRecordAudit] = []
    for field in _PATCHABLE_FIELDS:
        if field not in updates:
            continue
        old_value = getattr(record, field)
        new_value = updates[field]
        if old_value == new_value:
            continue
        audit_rows.append(
            ProductionRecordAudit(
                record_id=record.id,
                field=field,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
            )
        )
        setattr(record, field, new_value)

    record.variance_class = resulting_variance_class
    record.updated_by = "system"

    for row in audit_rows:
        db.add(row)
    db.commit()
    db.refresh(record)
    return _record_to_out(record)
