"""Weather Service — fetches real meteorological data from the Open-Meteo API.

PROVENANCE & LICENSING NOTICE:
==============================
Data Source: Open-Meteo (https://open-meteo.com/)
Data Type: REAL EXTERNAL WEATHER DATA (numerical weather prediction models: ECMWF, GFS, ICON)
Licensing: The standard public Open-Meteo API is provided strictly for non-commercial,
educational, and demonstration evaluation.
IMPORTANT: Production or commercial deployment for MOIL requires review of Open-Meteo
commercial licensing terms (paid commercial plan) or deployment of an in-house
self-hosted Open-Meteo / IMD numerical weather instance.

SPATIAL RESOLUTION NOTICE:
==========================
These meteorological observations and forecasts are sampled for the mine site's centroid
coordinates (approx 9-13 km model grid resolution). They represent regional atmospheric conditions,
NOT high-resolution in-pit sensors or 300m bench-level microclimate data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

# On Windows Python 3.14, inject system certificate store to ensure reliable TLS handshakes
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

logger = logging.getLogger("oresight.weather")

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT_SECONDS = 10.0
USER_AGENT = "OreSight-Reserve-Intelligence/1.0 (internal-demo; +https://github.com/Arnabh-M/moil-reserve-intelligence)"

# WMO Weather interpretation codes (WW)
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherServiceError(Exception):
    """Raised when external weather retrieval fails. Never fall back to synthetic data."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_weather_description(code: int | None) -> str:
    """Map WMO code to human-readable description."""
    if code is None:
        return "Unknown"
    return WMO_WEATHER_CODES.get(code, f"Weather code {code}")


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string into UTC timezone-aware datetime."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current meteorological conditions from Open-Meteo for given coordinates.

    Raises:
        WeatherServiceError: If the remote API request fails, times out, or returns an error.
    """
    params = {
        "latitude": round(latitude, 5),
        "longitude": round(longitude, 5),
        "current": (
            "temperature_2m,relative_humidity_2m,precipitation,rain,"
            "wind_speed_10m,wind_direction_10m,weather_code"
        ),
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius",
        "timezone": "UTC",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, headers=headers) as client:
            response = client.get(OPEN_METEO_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        logger.error("Open-Meteo timeout for lat=%s, lon=%s: %s", latitude, longitude, exc)
        raise WeatherServiceError("Weather service request timed out", status_code=504) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Open-Meteo HTTP %s error: %s", exc.response.status_code, exc.response.text)
        raise WeatherServiceError(
            f"External weather service returned HTTP {exc.response.status_code}",
            status_code=502,
        ) from exc
    except Exception as exc:
        logger.error("Open-Meteo connection error for lat=%s, lon=%s: %s", latitude, longitude, exc)
        raise WeatherServiceError(f"Failed to connect to weather service: {exc}", status_code=502) from exc

    current = data.get("current")
    if not current:
        raise WeatherServiceError("Weather service response missing 'current' payload", status_code=502)

    weather_code = current.get("weather_code")
    return {
        "timestamp": parse_iso_datetime(current["time"]),
        "temperature_c": current.get("temperature_2m"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": float(current.get("precipitation", 0.0) or 0.0),
        "rain_mm": current.get("rain"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "weather_code": weather_code,
        "weather_description": get_weather_description(weather_code),
        "source": "open-meteo",
    }


def fetch_forecast_weather(
    latitude: float,
    longitude: float,
    forecast_hours: int = 48,
) -> list[dict[str, Any]]:
    """Fetch hourly weather forecast from Open-Meteo for given coordinates.

    Args:
        latitude: Latitude in WGS84.
        longitude: Longitude in WGS84.
        forecast_hours: Number of hourly forecast steps (capped at 168 hours = 7 days).

    Raises:
        WeatherServiceError: If the remote API request fails, times out, or returns an error.
    """
    forecast_hours = max(1, min(forecast_hours, 168))
    forecast_days = max(1, (forecast_hours + 23) // 24)

    params = {
        "latitude": round(latitude, 5),
        "longitude": round(longitude, 5),
        "hourly": (
            "temperature_2m,relative_humidity_2m,precipitation,rain,"
            "wind_speed_10m,wind_direction_10m,weather_code"
        ),
        "forecast_days": forecast_days,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius",
        "timezone": "UTC",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, headers=headers) as client:
            response = client.get(OPEN_METEO_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        logger.error("Open-Meteo timeout for forecast lat=%s, lon=%s: %s", latitude, longitude, exc)
        raise WeatherServiceError("Weather service forecast request timed out", status_code=504) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Open-Meteo HTTP %s error: %s", exc.response.status_code, exc.response.text)
        raise WeatherServiceError(
            f"External weather service returned HTTP {exc.response.status_code}",
            status_code=502,
        ) from exc
    except Exception as exc:
        logger.error("Open-Meteo connection error for forecast: %s", exc)
        raise WeatherServiceError(f"Failed to connect to weather service: {exc}", status_code=502) from exc

    hourly = data.get("hourly")
    if not hourly or "time" not in hourly:
        raise WeatherServiceError("Weather service response missing 'hourly' payload", status_code=502)

    times = hourly["time"][:forecast_hours]
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    precips = hourly.get("precipitation", [])
    rains = hourly.get("rain", [])
    winds = hourly.get("wind_speed_10m", [])
    wind_dirs = hourly.get("wind_direction_10m", [])
    codes = hourly.get("weather_code", [])

    points: list[dict[str, Any]] = []
    for i, t in enumerate(times):
        code = codes[i] if i < len(codes) else None
        points.append({
            "timestamp": parse_iso_datetime(t),
            "temperature_c": temps[i] if i < len(temps) else None,
            "relative_humidity_pct": humidities[i] if i < len(humidities) else None,
            "precipitation_mm": float(precips[i] or 0.0) if i < len(precips) else 0.0,
            "rain_mm": rains[i] if i < len(rains) else None,
            "wind_speed_kmh": winds[i] if i < len(winds) else None,
            "wind_direction_deg": wind_dirs[i] if i < len(wind_dirs) else None,
            "weather_code": code,
            "weather_description": get_weather_description(code),
        })

    return points
