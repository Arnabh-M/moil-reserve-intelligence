"""ProductionRecord ORM model — daily actual vs target tonnage per site."""

from datetime import date as date_, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.site import Site


class ProductionRecord(Base):
    __tablename__ = "production_records"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "date", "shift", name="uq_production_records_site_date_shift"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)
    actual_output: Mapped[float | None] = mapped_column(Float)
    target_output: Mapped[float | None] = mapped_column(Float)

    # -- added for Field Intake Hardening Phase 1 (production persistence) --
    shift: Mapped[str] = mapped_column(
        String, nullable=False, server_default="general"
    )
    operating_hours: Mapped[float | None] = mapped_column(Numeric(4, 2))
    downtime_hours: Mapped[float | None] = mapped_column(Numeric(4, 2))
    material_processed: Mapped[float | None] = mapped_column(Numeric)
    quality_grade: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # Postgres text[]; empty list rather than NULL is written on create so
    # `col @> ARRAY[...]`-style queries later don't need NULL-handling.
    shortfall_reasons: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    shortfall_other_note: Mapped[str | None] = mapped_column(Text)
    # Computed and persisted server-side on write (see routers/production.py);
    # the frontend still computes it live for instant feedback, but this
    # column is the canonical value shown after save.
    variance_class: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String, server_default="system")
    updated_by: Mapped[str | None] = mapped_column(String)

    site: Mapped["Site"] = relationship(back_populates="production_records")
