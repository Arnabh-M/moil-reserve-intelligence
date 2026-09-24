"""Inference-side read of blast delays from Postgres, for the shortfall model's
`blast_delay_days_lag` feature.

The window definition and the counting live in ONE place,
app.services.shortfall_features.blast_delay_days_lag, which the training pipeline
also calls. This module only turns `blast_events` rows into the
(planned_date, delay_days) pairs that function consumes.

What counts as a delay event: a row with a recorded delay_reason that was not
cancelled (a cancelled blast is not a delay; a blast that was merely planned has
not slipped). Its delay days are planned_date .. actual_date - 1. A delayed blast
with no actual_date yet is open-ended and is counted for at most
BLAST_DELAY_MAX_DAYS from its planned date (see shortfall_features).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import BlastEvent, BlastStatus
from app.services.shortfall_features import (
    BLAST_DELAY_MAX_DAYS,
    BLAST_LAG_WINDOW_DAYS,
    blast_delay_days_lag,
)


def _delay_days(planned: date, actual: date | None, as_of: date) -> int:
    if actual is not None:
        return max(0, (actual - planned).days)
    return min(max(0, (as_of - planned).days), BLAST_DELAY_MAX_DAYS)


def blast_delay_days_lag_for_site(db: Session, site_id: int, as_of: date) -> float:
    """Blast-delay days at `site_id` in the trailing 7 days ending as_of - 1."""
    window_start = as_of - timedelta(days=BLAST_LAG_WINDOW_DAYS)
    rows = db.execute(
        select(BlastEvent.planned_date, BlastEvent.actual_date).where(
            BlastEvent.site_id == site_id,
            BlastEvent.delay_reason.is_not(None),
            BlastEvent.status != BlastStatus.CANCELLED,
            BlastEvent.planned_date < as_of,
            or_(BlastEvent.actual_date.is_(None), BlastEvent.actual_date > window_start),
        )
    ).all()
    events = [(planned, _delay_days(planned, actual, as_of)) for planned, actual in rows]
    return blast_delay_days_lag(events, as_of)
