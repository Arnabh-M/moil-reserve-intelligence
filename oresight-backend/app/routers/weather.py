"""Routes for live meteorological observations and short-term forecasts.

PROVENANCE & LICENSING:
Data is sourced dynamically from Open-Meteo (https://open-meteo.com/).
The standard public tier is non-commercial. Commercial deployment for MOIL
requires reviewing Open-Meteo licensing or self-hosting a weather model.
Data is sampled at the site's centroid coordinates (WGS84 EPSG:4326).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.shape import to_shape
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Site, WeatherRecord
from app.schemas import CurrentWeatherResponse, ForecastWeatherPoint, ForecastWeatherResponse
from app.services.lookups import get_site_or_404
from app.services.weather_service import (
    WeatherServiceError,
    fetch_current_weather,
    fetch_forecast_weather,
)

logger = logging.getLogger("oresight.weather")

router = APIRouter(prefix="/weather", tags=["weather"])


def _persist_weather_record(
    db: Session,
    site_id: int,
    data: dict[str, Any],
    *,
    is_forecast: bool = False,
) -> None:
    """Store or update a weather record in PostgreSQL using an idempotent upsert.

    Uses the unique constraint on (site_id, timestamp, is_forecast) to prevent
    duplicate records across frequent API calls or frontend refreshes.
    """
    try:
        stmt = pg_insert(WeatherRecord).values(
            site_id=site_id,
            timestamp=data["timestamp"],
            rainfall_mm=float(data.get("precipitation_mm", 0.0) or 0.0),
            temperature_c=data.get("temperature_c"),
            humidity_pct=data.get("relative_humidity_pct"),
            wind_speed_kmh=data.get("wind_speed_kmh"),
            wind_direction_deg=data.get("wind_direction_deg"),
            weather_type=data.get("weather_description"),
            is_forecast=is_forecast,
            source=data.get("source", "open-meteo"),
        )
        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_weather_records_site_timestamp_forecast",
            set_={
                "rainfall_mm": stmt.excluded.rainfall_mm,
                "temperature_c": stmt.excluded.temperature_c,
                "humidity_pct": stmt.excluded.humidity_pct,
                "wind_speed_kmh": stmt.excluded.wind_speed_kmh,
                "wind_direction_deg": stmt.excluded.wind_direction_deg,
                "weather_type": stmt.excluded.weather_type,
            },
        )
        db.execute(upsert_stmt)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - DB persistence failure must not fail the live weather read
        db.rollback()
        logger.warning("Could not persist weather record for site %s: %s", site_id, exc)


@router.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Get current meteorological conditions for a site",
)
def get_current_weather(
    site_id: int = Query(..., description="ID of the mine site"),
    db: Session = Depends(get_db),
) -> CurrentWeatherResponse:
    """Return live current weather sampled at the site's centroid from Open-Meteo.

    Validates that the site exists, extracts its WGS84 centroid coordinates,
    fetches live observation values, optionally persists the record, and returns
    a normalized response.
    """
    site = get_site_or_404(db, site_id)
    point = to_shape(site.centroid)
    lat = float(point.y)
    lon = float(point.x)

    try:
        data = fetch_current_weather(lat, lon)
    except WeatherServiceError as exc:
        logger.error("Weather retrieval failed for site %s (%s, %s): %s", site.id, lat, lon, exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    _persist_weather_record(db, site.id, data, is_forecast=False)

    return CurrentWeatherResponse(
        site_id=site.id,
        site_name=site.name,
        latitude=round(lat, 5),
        longitude=round(lon, 5),
        timestamp=data["timestamp"],
        temperature_c=data["temperature_c"],
        relative_humidity_pct=data["relative_humidity_pct"],
        precipitation_mm=data["precipitation_mm"],
        rain_mm=data["rain_mm"],
        wind_speed_kmh=data["wind_speed_kmh"],
        wind_direction_deg=data["wind_direction_deg"],
        weather_code=data["weather_code"],
        weather_description=data["weather_description"],
        is_forecast=False,
        source=data["source"],
    )


@router.get(
    "/forecast",
    response_model=ForecastWeatherResponse,
    summary="Get hourly meteorological forecast for a site",
)
def get_forecast_weather(
    site_id: int = Query(..., description="ID of the mine site"),
    hours: int = Query(48, ge=1, le=168, description="Forecast horizon in hours (1-168)"),
    db: Session = Depends(get_db),
) -> ForecastWeatherResponse:
    """Return hourly meteorological forecast sampled at the site's centroid from Open-Meteo.

    Validates that the site exists, extracts its WGS84 centroid coordinates,
    fetches short-term hourly forecast data, and returns normalized forecast steps.
    """
    site = get_site_or_404(db, site_id)
    point = to_shape(site.centroid)
    lat = float(point.y)
    lon = float(point.x)

    try:
        points = fetch_forecast_weather(lat, lon, forecast_hours=hours)
    except WeatherServiceError as exc:
        logger.error("Weather forecast retrieval failed for site %s (%s, %s): %s", site.id, lat, lon, exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    # Persist the nearest forecast points opportunistically
    for pt in points[:24]:
        _persist_weather_record(db, site.id, pt, is_forecast=True)

    return ForecastWeatherResponse(
        site_id=site.id,
        site_name=site.name,
        latitude=round(lat, 5),
        longitude=round(lon, 5),
        forecast_horizon_hours=hours,
        source="open-meteo",
        forecast=[ForecastWeatherPoint(**pt) for pt in points],
    )
