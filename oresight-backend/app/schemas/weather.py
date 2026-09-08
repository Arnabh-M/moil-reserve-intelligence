"""Pydantic schemas for current weather observations and forecasts.

PROVENANCE & LICENSING:
Data sourced from Open-Meteo public API (https://open-meteo.com/).
Provided strictly for non-commercial research and internal demonstration.
Commercial MOIL operations require reviewing Open-Meteo commercial plans.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ForecastWeatherPoint(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "timestamp": "2026-09-08T18:00:00Z",
                "temperature_c": 25.4,
                "relative_humidity_pct": 88.0,
                "precipitation_mm": 1.2,
                "rain_mm": 1.2,
                "wind_speed_kmh": 6.8,
                "wind_direction_deg": 210.0,
                "weather_code": 61,
                "weather_description": "Slight rain",
            }
        },
    )

    timestamp: datetime = Field(description="Forecast valid time in UTC")
    temperature_c: float | None = Field(default=None, description="2m air temperature in Celsius")
    relative_humidity_pct: float | None = Field(default=None, description="Relative humidity %")
    precipitation_mm: float = Field(default=0.0, ge=0.0, description="Precipitation in mm")
    rain_mm: float | None = Field(default=None, ge=0.0, description="Liquid rain in mm")
    wind_speed_kmh: float | None = Field(default=None, ge=0.0, description="10m wind speed in km/h")
    wind_direction_deg: float | None = Field(default=None, ge=0.0, le=360.0, description="Wind direction in degrees")
    weather_code: int | None = Field(default=None, description="WMO weather code (0-99)")
    weather_description: str | None = Field(default=None, description="Human-readable WMO weather description")


class CurrentWeatherResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "site_id": 1,
                "site_name": "Balaghat Mine",
                "latitude": 21.87,
                "longitude": 80.23,
                "timestamp": "2026-09-08T17:15:00Z",
                "temperature_c": 25.7,
                "relative_humidity_pct": 86.0,
                "precipitation_mm": 0.0,
                "rain_mm": 0.0,
                "wind_speed_kmh": 0.9,
                "wind_direction_deg": 233.0,
                "weather_code": 1,
                "weather_description": "Mainly clear",
                "is_forecast": False,
                "source": "open-meteo",
            }
        },
    )

    site_id: int
    site_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    precipitation_mm: float = 0.0
    rain_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    weather_code: int | None = None
    weather_description: str | None = None
    is_forecast: bool = False
    source: str = "open-meteo"


class ForecastWeatherResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "site_id": 1,
                "site_name": "Balaghat Mine",
                "latitude": 21.87,
                "longitude": 80.23,
                "forecast_horizon_hours": 48,
                "source": "open-meteo",
                "forecast": [],
            }
        },
    )

    site_id: int
    site_name: str
    latitude: float
    longitude: float
    forecast_horizon_hours: int
    source: str = "open-meteo"
    forecast: list[ForecastWeatherPoint]
