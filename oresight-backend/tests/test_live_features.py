"""Unit tests for the live feature builder's pure logic (app/services/live_features.py):
as-of resolution, the satellite-then-Open-Meteo rain lookup, and the downtime feature math.
No database, no network: rain sources are stubbed. The DB-backed check that the live row equals
the TRAINING frame lives in test_live_feature_parity.py.
"""

import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from app.services import live_features as lf
from app.services.live_features import (
    FeatureConstants,
    LiveDataUnavailableError,
    downtime_features,
    reconstruct_outages,
    resolve_as_of,
    satellite_rain_lookup,
)

CONSTANTS = FeatureConstants(
    machines_per_site={"balaghat": 5},
    heavy_rain_mm=35.0,
    backlog_decay=0.85,
    rolling_downtime_window_days=7,
    maintenance_reason="scheduled maintenance",
)
D = date(2026, 9, 22)


def _observed_through(last: date, missing: tuple[date, ...] = ()) -> dict[date, float]:
    return {last - timedelta(days=k): 1.0 for k in range(60) if (last - timedelta(days=k)) not in missing}


# ---------------------------------------------------------------------
# as-of resolution
# ---------------------------------------------------------------------
def test_as_of_is_the_requested_day_when_its_window_is_complete():
    as_of, _ = resolve_as_of("balaghat", D, lambda *_: _observed_through(D))
    assert as_of == D


def test_as_of_walks_back_to_the_latest_day_with_observed_rain():
    as_of, _ = resolve_as_of("balaghat", D, lambda *_: _observed_through(D - timedelta(days=2)))
    assert as_of == D - timedelta(days=2)


def test_as_of_skips_days_whose_seven_day_window_has_a_hole():
    hole = D - timedelta(days=3)
    as_of, _ = resolve_as_of("balaghat", D, lambda *_: _observed_through(D, missing=(hole,)))
    # D-3 itself and every day whose previous week includes it (D-2, D-1, D) are rejected
    assert as_of == D - timedelta(days=4)


def test_as_of_refuses_rather_than_invent_when_the_rain_record_has_stopped():
    with pytest.raises(LiveDataUnavailableError, match="stopped updating"):
        resolve_as_of("balaghat", D, lambda *_: {})


# ---------------------------------------------------------------------
# rain lookup: satellite CSV first, Open-Meteo fallback second, never invented
# ---------------------------------------------------------------------
def _frame(rows):
    return pd.DataFrame(rows, columns=["site_id", "date", "rainfall_mm", "rain_source"])


@pytest.fixture
def stub_weather(monkeypatch):
    """A weather_history stand-in: the CSV knows 09-20..09-22 and has NaN for 09-23; the
    fallback is scripted per test. Records every fallback call."""
    from app.services import weather_history

    lf._fallback_failed_at.clear()
    calls = []
    state = {"fallback_value": float("nan")}

    def fake_load(site_ids, start, end, use_fallback=True, http_timeout=None):
        days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end))
        rows = []
        for d in days:
            if d <= pd.Timestamp("2026-09-22"):
                rows.append((site_ids[0], d, 2.0, "IMERG"))
            elif use_fallback:
                calls.append((d.date(), http_timeout))
                rows.append((site_ids[0], d, state["fallback_value"], "open-meteo-archive"))
            else:
                rows.append((site_ids[0], d, float("nan"), "missing"))
        return _frame(rows)

    monkeypatch.setattr(weather_history, "load_rainfall_history", fake_load)
    yield calls, state
    lf._fallback_failed_at.clear()


def test_a_date_no_source_has_is_absent_not_filled(stub_weather):
    calls, _ = stub_weather
    observed = satellite_rain_lookup("balaghat", date(2026, 9, 21), date(2026, 9, 23))
    assert set(observed) == {date(2026, 9, 21), date(2026, 9, 22)}  # 09-23 missing everywhere -> absent
    assert calls, "the fallback must have been tried for the gap"


def test_fallback_is_used_for_dates_the_csv_lacks_and_is_time_bounded(stub_weather):
    calls, state = stub_weather
    state["fallback_value"] = 7.5
    observed = satellite_rain_lookup("balaghat", date(2026, 9, 21), date(2026, 9, 23))
    assert observed[date(2026, 9, 23)] == 7.5
    assert observed[date(2026, 9, 22)] == 2.0  # the CSV value is never overridden
    assert calls == [(date(2026, 9, 23), lf.FALLBACK_HTTP_TIMEOUT_SECONDS)]


def test_a_failed_fallback_is_not_retried_on_every_request(stub_weather):
    calls, _ = stub_weather
    satellite_rain_lookup("balaghat", date(2026, 9, 21), date(2026, 9, 23))
    n_after_first = len(calls)
    satellite_rain_lookup("balaghat", date(2026, 9, 21), date(2026, 9, 23))
    satellite_rain_lookup("balaghat", date(2026, 9, 21), date(2026, 9, 23))
    assert len(calls) == n_after_first, "an offline demo must not stall every Simulator click"


# ---------------------------------------------------------------------
# downtime features
# ---------------------------------------------------------------------
def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 3, day, hour)


def test_downtime_features_match_the_hand_computed_values():
    outages = [
        (_dt(8, 22), _dt(10, 6), "mechanical failure", 1),  # started before t, 26h in the window, 6h into day t
        (_dt(10, 5), _dt(10, 9), "mechanical failure", 2),  # starts ON day t: history excludes it
        (_dt(9, 12), None, "spare parts unavailable", 3),  # still running: 12h in the window, assumed all of day t
        (_dt(1, 8), _dt(1, 12), "scheduled maintenance", 4),  # before the window; sets days-since = 9
        (_dt(5, 8), _dt(5, 12), "scheduled maintenance", 5),  # 4h in the window; 5 days ago
    ]
    rolling, today, since = downtime_features(outages, date(2026, 3, 10), 5, CONSTANTS)
    assert rolling == pytest.approx((26 + 12 + 4) / (5 * 7 * 24))
    assert today == pytest.approx((6 + 24) / (5 * 24))
    assert since == 9.0  # the MOST overdue machine, not the average


def test_no_history_gives_zero_downtime_and_a_missing_maintenance_age():
    rolling, today, since = downtime_features([], date(2026, 3, 10), 5, CONSTANTS)
    assert (rolling, today) == (0.0, 0.0)
    assert math.isnan(since)  # never guessed


def _row(equipment_id, status, when, reason=None, row_id=0):
    return SimpleNamespace(
        equipment_id=equipment_id, new_status=status, changed_at=when.replace(tzinfo=timezone.utc), reason=reason, id=row_id
    )


def test_outages_are_rebuilt_from_down_up_rows_as_naive_utc():
    rows = [
        _row(1, "up", _dt(2, 9), "returned to service", 2),
        _row(1, "down", _dt(1, 8), "hydraulic leak", 1),
        _row(1, "down", _dt(1, 9), "duplicate down must not restart the outage", 3),
        _row(2, "down", _dt(3, 8), "electrical fault", 4),  # never closed -> still running
    ]
    assert sorted(reconstruct_outages(rows), key=lambda o: o[3]) == [
        (_dt(1, 8), _dt(2, 9), "hydraulic leak", 1),
        (_dt(3, 8), None, "electrical fault", 2),
    ]


# ---------------------------------------------------------------------
# feature constants travel with the artifact
# ---------------------------------------------------------------------
def test_constants_are_read_from_the_artifact_metrics():
    metrics = {
        "feature_constants": {
            "machines_per_site": {"balaghat": 5, "bhandara": 9},
            "heavy_rain_mm": 35.0,
            "backlog_decay": 0.85,
            "rolling_downtime_window_days": 7,
            "maintenance_reason": "scheduled maintenance",
        }
    }
    assert FeatureConstants.from_metrics(metrics).machines_per_site["bhandara"] == 9


def test_an_artifact_without_constants_is_refused_not_defaulted():
    with pytest.raises(LiveDataUnavailableError, match="feature_constants"):
        FeatureConstants.from_metrics({"rmse": 0.05})
