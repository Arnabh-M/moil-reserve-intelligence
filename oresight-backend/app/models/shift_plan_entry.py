"""ShiftPlanEntry ORM model — a recommendation option a planner has
committed to the shift plan.

Purely additive Day-4 feature: `POST /shift-plan` snapshots one option from
`GET /recommendations` (its type / description / projected impact /
confidence, plus the risk event and site it came from) so the "Add to shift
plan" button on the dashboard actually persists. `site_id` is derived from
the referenced risk event, not supplied by the caller. Nothing else in the
API reads or writes this table.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ShiftPlanEntry(Base):
    __tablename__ = "shift_plan_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_event_id: Mapped[int] = mapped_column(
        ForeignKey("risk_events.id"), index=True, nullable=False
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    option_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str | None] = mapped_column(Text)
    projected_impact: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
