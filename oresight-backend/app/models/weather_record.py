"""WeatherRecord ORM model — stored weather observations and forecasts per site.

PROVENANCE & LICENSING NOTE:
External weather data is sourced from Open-Meteo (https://open-meteo.com/).
The free public API tier is strictly for non-commercial evaluation and demo purposes.
Commercial or production deployment for MOIL requires review of Open-Meteo licensing
and potentially a commercial plan or self-hosted meteorological model instance.
These values represent regional numerical meteorological estimates sampled at site centroid
coordinates, NOT in-pit microclimate or 300m bench-level sensor data.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.site import Site


class WeatherRecord(Base):
    __tablename__ = "weather_records"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "timestamp", "is_forecast",
            name="uq_weather_records_site_timestamp_forecast"
        ),
        Index("ix_weather_records_site_timestamp", "site_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    rainfall_mm: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float)
    weather_type: Mapped[str | None] = mapped_column(Text)
    is_forecast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="open-meteo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    site: Mapped["Site"] = relationship(back_populates="weather_records")
