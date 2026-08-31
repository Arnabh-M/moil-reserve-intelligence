"""ReserveZone ORM model — confidence-scored ore sub-polygons within a site."""

from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.site import Site


class ReserveZone(Base):
    __tablename__ = "reserve_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=False
    )
    zone_name: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True)
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    estimated_grade_pct: Mapped[float | None] = mapped_column(Float)
    estimated_depth_m: Mapped[float | None] = mapped_column(Float)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    site: Mapped["Site"] = relationship(back_populates="reserve_zones")
