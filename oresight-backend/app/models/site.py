"""Site ORM model — one row per MOIL mine site (Balaghat, Nagpur, Bhandara)."""

from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.production_record import ProductionRecord
    from app.models.reserve_zone import ReserveZone
    from app.models.risk_event import RiskEvent


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    belt_name: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True)
    )
    centroid: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    reserve_zones: Mapped[list["ReserveZone"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="site")
    production_records: Mapped[list["ProductionRecord"]] = relationship(
        back_populates="site"
    )
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="site")
