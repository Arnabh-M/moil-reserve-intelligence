"""Suite-wide fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _watcher_never_calls_live_weather(monkeypatch):
    """The Watcher's DEFAULT rain-forecast source is the live Open-Meteo API. Tests that run the real
    watcher (scheduler.run_watcher, the risk-event fixtures) must neither depend on the network nor
    write whatever the real forecast happens to say into the demo database. An empty forecast is
    treated as "unavailable": no weather risk event is created or resolved. The weather-watcher tests
    inject their own `forecast_fn`, which this does not affect."""
    from app.agents import watcher

    monkeypatch.setattr(watcher, "fetch_site_rain_forecast", lambda *_a, **_k: [])
