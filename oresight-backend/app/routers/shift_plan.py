"""Routes for the shift plan — recommendation options a planner has chosen
to act on.

Purely additive Day-4 feature. `POST /shift-plan` snapshots one option from
`GET /recommendations`; `GET /shift-plan?site_id=` lists a site's entries,
newest first. Nothing here mutates or reads any other resource.

Error handling mirrors `app/routers/recommendations.py`: unknown ids -> a
clean 404 via the shared `get_*_or_404` lookups, Postgres-unreachable
errors propagate to the app-level handlers (-> 503), and anything else that
goes wrong persisting the row -> 502 rather than an opaque 500.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ShiftPlanEntry
from app.schemas import ShiftPlanEntryCreate, ShiftPlanEntryOut
from app.services.lookups import get_risk_event_or_404, get_site_or_404

logger = logging.getLogger("oresight.shift_plan")

router = APIRouter(prefix="/shift-plan", tags=["shift-plan"])


@router.post(
    "",
    response_model=ShiftPlanEntryOut,
    status_code=201,
    summary="Add a recommendation option to the shift plan",
)
def add_to_shift_plan(
    payload: ShiftPlanEntryCreate, db: Session = Depends(get_db)
) -> ShiftPlanEntryOut:
    """Persist one chosen recommendation option.

    `site_id` is taken from the referenced risk event, not the request body.

    - Unknown `risk_event_id` -> 404 (shared `get_risk_event_or_404`).
    - Bad option shape (unknown `option_type`, impact/confidence out of
      range, blank description) -> 422 via the global validation handler.
    - Postgres unreachable -> 503 (app-level handler).
    - Any other write failure -> 502, so the caller gets a clear "upstream
      failed" instead of an opaque 500.
    """
    risk_event = get_risk_event_or_404(db, payload.risk_event_id)

    entry = ShiftPlanEntry(
        risk_event_id=risk_event.id,
        site_id=risk_event.site_id,
        option_type=payload.option_type,
        description=payload.description,
        target_id=payload.target_id,
        projected_impact=payload.projected_impact,
        confidence=payload.confidence,
    )
    db.add(entry)
    try:
        db.commit()
    except (OperationalError, InterfaceError):
        # Transient infra — let app.main's handler turn it into a clean 503.
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Failed to persist shift plan entry for risk_event_id=%s", payload.risk_event_id
        )
        raise HTTPException(
            status_code=502, detail="Could not save the shift plan entry."
        ) from exc

    db.refresh(entry)
    return entry


@router.get(
    "",
    response_model=list[ShiftPlanEntryOut],
    summary="List a site's shift plan entries (newest first)",
)
def list_shift_plan(
    site_id: int = Query(..., description="The site whose shift plan to return"),
    db: Session = Depends(get_db),
) -> list[ShiftPlanEntryOut]:
    """Return every shift plan entry for a site, most recently added first.

    - Unknown `site_id` -> 404.
    - A site with no entries yet -> a normal 200 `[]`, not an error.
    """
    get_site_or_404(db, site_id)

    stmt = (
        select(ShiftPlanEntry)
        .where(ShiftPlanEntry.site_id == site_id)
        .order_by(ShiftPlanEntry.created_at.desc(), ShiftPlanEntry.id.desc())
    )
    return db.scalars(stmt).all()
