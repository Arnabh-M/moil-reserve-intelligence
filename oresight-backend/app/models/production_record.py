"""ProductionRecord ORM model — daily actual vs target tonnage per site."""

from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.site import Site


class ProductionRecord(Base):
    __tablename__ = "production_records"
    __table_args__ = (
        UniqueConstraint("site_id", "date", name="uq_production_records_site_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)
    actual_output: Mapped[float | None] = mapped_column(Float)
    target_output: Mapped[float | None] = mapped_column(Float)

    site: Mapped["Site"] = relationship(back_populates="production_records")
