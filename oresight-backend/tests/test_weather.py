"""Tests for weather service, schemas, and router endpoints.

All remote Open-Meteo HTTP calls are mocked to ensure deterministic, fast,
offline test execution without external network dependency or rate-limit consumption.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point

from app.db import get_db
from app.main import app
from app.models import Site
from app.schemas.weather import (
    CurrentWeatherResponse,
    ForecastWeatherPoint,
    ForecastWeatherResponse,
)
from app.services.weather_service import (
    WeatherServiceError,
    fetch_current_weather,
    fetch_forecast_weather,
    get_weather_description,
)

SAMPLE_OPEN_METEO_CURRENT_RESPONSE = {
    "latitude": 21.87,
    "longitude": 80.23,
    "utc_offset_seconds": 0,
    "timezone": "UTC",
    "current": {
        "time": "2026-09-08T18:00",
        "interval": 900,
        "temperature_2m": 25.4,
        "relative_humidity_2m": 88,
        "precipitation": 1.5,
        "rain": 1.5,
        "wind_speed_10m": 7.2,
        "wind_direction_10m": 215,
        "weather_code": 61,
    },
}

SAMPLE_OPEN_METEO_HOURLY_RESPONSE = {
    "latitude": 21.87,
    "longitude": 80.23,
    "timezone": "UTC",
    "hourly": {
        "time": [
            "2026-09-08T18:00",
            "2026-09-08T19:00",
            "2026-09-08T20:00",
        ],
        "temperature_2m": [25.4, 24.9, 24.5],
        "relative_humidity_2m": [88, 90, 92],
        "precipitation": [1.5, 0.5, 0.0],
        "rain": [1.5, 0.5, 0.0],
        "wind_speed_10m": [7.2, 6.5, 5.8],
        "wind_direction_10m": [215, 210, 205],
        "weather_code": [61, 80, 2],
    },
}


# ==============================================================================
# Unit Tests: Weather Service
# ==============================================================================

def test_wmo_code_interpretation():
    assert get_weather_description(0) == "Clear sky"
    assert get_weather_description(61) == "Slight rain"
    assert get_weather_description(95) == "Thunderstorm"
    assert get_weather_description(None) == "Unknown"
    assert get_weather_description(999) == "Weather code 999"


@patch("httpx.Client.get")
def test_fetch_current_weather_parsing(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_CURRENT_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = fetch_current_weather(21.87, 80.23)

    assert result["temperature_c"] == 25.4
    assert result["relative_humidity_pct"] == 88
    assert result["precipitation_mm"] == 1.5
    assert result["rain_mm"] == 1.5
    assert result["wind_speed_kmh"] == 7.2
    assert result["wind_direction_deg"] == 215
    assert result["weather_code"] == 61
    assert result["weather_description"] == "Slight rain"
    assert result["source"] == "open-meteo"


@patch("httpx.Client.get")
def test_fetch_forecast_weather_parsing(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_HOURLY_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    points = fetch_forecast_weather(21.87, 80.23, forecast_hours=3)

    assert len(points) == 3
    assert points[0]["temperature_c"] == 25.4
    assert points[0]["precipitation_mm"] == 1.5
    assert points[0]["weather_description"] == "Slight rain"
    assert points[2]["weather_description"] == "Partly cloudy"


@patch("httpx.Client.get")
def test_weather_service_handles_timeout(mock_get):
    import httpx
    mock_get.side_effect = httpx.TimeoutException("Connection timed out")

    with pytest.raises(WeatherServiceError) as exc_info:
        fetch_current_weather(21.87, 80.23)

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.message.lower()


@patch("httpx.Client.get")
def test_weather_service_handles_http_error(mock_get):
    import httpx
    req = httpx.Request("GET", "https://api.open-meteo.com")
    resp = httpx.Response(status_code=500, request=req, text="Internal Server Error")
    mock_get.side_effect = httpx.HTTPStatusError("Server Error", request=req, response=resp)

    with pytest.raises(WeatherServiceError) as exc_info:
        fetch_current_weather(21.87, 80.23)

    assert exc_info.value.status_code == 502
    assert "HTTP 500" in exc_info.value.message


# ==============================================================================
# Unit Tests: Pydantic Schema Validation
# ==============================================================================

def test_current_weather_schema_validation():
    payload = {
        "site_id": 1,
        "site_name": "Balaghat Mine",
        "latitude": 21.87,
        "longitude": 80.23,
        "timestamp": "2026-09-08T18:00:00Z",
        "temperature_c": 25.4,
        "relative_humidity_pct": 88.0,
        "precipitation_mm": 1.5,
        "rain_mm": 1.5,
        "wind_speed_kmh": 7.2,
        "wind_direction_deg": 215.0,
        "weather_code": 61,
        "weather_description": "Slight rain",
        "is_forecast": False,
        "source": "open-meteo",
    }
    obj = CurrentWeatherResponse.model_validate(payload)
    assert obj.site_id == 1
    assert obj.precipitation_mm == 1.5
    assert obj.is_forecast is False


def test_forecast_weather_schema_validation():
    payload = {
        "site_id": 1,
        "site_name": "Balaghat Mine",
        "latitude": 21.87,
        "longitude": 80.23,
        "forecast_horizon_hours": 3,
        "source": "open-meteo",
        "forecast": [
            {
                "timestamp": "2026-09-08T18:00:00Z",
                "temperature_c": 25.4,
                "relative_humidity_pct": 88.0,
                "precipitation_mm": 1.5,
                "rain_mm": 1.5,
                "wind_speed_kmh": 7.2,
                "wind_direction_deg": 215.0,
                "weather_code": 61,
                "weather_description": "Slight rain",
            }
        ],
    }
    obj = ForecastWeatherResponse.model_validate(payload)
    assert len(obj.forecast) == 1
    assert obj.forecast[0].weather_code == 61


# ==============================================================================
# Integration Tests: Router Endpoints (Mocked DB & Service)
# ==============================================================================

class MockCentroid:
    """Mock WKBElement wrapper returning a Shapely Point."""
    def __init__(self, x: float, y: float):
        self.point = Point(x, y)

    def __geo_interface__(self):
        return self.point.__geo_interface__


def test_weather_missing_site_returns_404():
    """Missing site must return standard 404 with error_code."""
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.get("/weather/current?site_id=999999")
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("app.routers.weather.fetch_current_weather")
@patch("app.routers.weather.to_shape")
def test_current_weather_endpoint_success(mock_to_shape, mock_fetch):
    mock_site = MagicMock()
    mock_site.id = 1
    mock_site.name = "Balaghat Mine"
    mock_site.centroid = "mock_centroid_geom"

    mock_point = MagicMock()
    mock_point.x = 80.23
    mock_point.y = 21.87
    mock_to_shape.return_value = mock_point

    from datetime import datetime, timezone
    mock_fetch.return_value = {
        "timestamp": datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc),
        "temperature_c": 26.1,
        "relative_humidity_pct": 84.0,
        "precipitation_mm": 0.0,
        "rain_mm": 0.0,
        "wind_speed_kmh": 4.5,
        "wind_direction_deg": 190.0,
        "weather_code": 1,
        "weather_description": "Mainly clear",
        "source": "open-meteo",
    }

    mock_db = MagicMock()
    mock_db.get.return_value = mock_site

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.get("/weather/current?site_id=1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["site_id"] == 1
            assert data["site_name"] == "Balaghat Mine"
            assert data["temperature_c"] == 26.1
            assert data["weather_description"] == "Mainly clear"
            assert data["source"] == "open-meteo"
            assert data["is_forecast"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("app.routers.weather.fetch_current_weather")
@patch("app.routers.weather.to_shape")
def test_current_weather_upstream_error_returns_502(mock_to_shape, mock_fetch):
    mock_site = MagicMock()
    mock_site.id = 1
    mock_site.name = "Balaghat Mine"
    mock_point = MagicMock()
    mock_point.x = 80.23
    mock_point.y = 21.87
    mock_to_shape.return_value = mock_point

    mock_fetch.side_effect = WeatherServiceError("Open-Meteo unavailable", status_code=502)

    mock_db = MagicMock()
    mock_db.get.return_value = mock_site

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.get("/weather/current?site_id=1")
            assert resp.status_code == 502
            data = resp.json()
            assert "Open-Meteo unavailable" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("app.routers.weather.fetch_forecast_weather")
@patch("app.routers.weather.to_shape")
def test_forecast_weather_endpoint_success(mock_to_shape, mock_fetch):
    mock_site = MagicMock()
    mock_site.id = 1
    mock_site.name = "Balaghat Mine"
    mock_point = MagicMock()
    mock_point.x = 80.23
    mock_point.y = 21.87
    mock_to_shape.return_value = mock_point

    from datetime import datetime, timezone
    mock_fetch.return_value = [
        {
            "timestamp": datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc),
            "temperature_c": 25.0,
            "relative_humidity_pct": 85.0,
            "precipitation_mm": 0.2,
            "rain_mm": 0.2,
            "wind_speed_kmh": 5.0,
            "wind_direction_deg": 200.0,
            "weather_code": 80,
            "weather_description": "Slight rain showers",
        }
    ]

    mock_db = MagicMock()
    mock_db.get.return_value = mock_site

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.get("/weather/forecast?site_id=1&hours=24")
            assert resp.status_code == 200
            data = resp.json()
            assert data["site_id"] == 1
            assert data["forecast_horizon_hours"] == 24
            assert len(data["forecast"]) == 1
            assert data["forecast"][0]["weather_description"] == "Slight rain showers"
    finally:
        app.dependency_overrides.pop(get_db, None)
