"""The Watcher's rain-forecast risks: weather_heavy_rain (>= 64.5 mm/24 h, score 0.6 -> 1.0 at 115.5 mm)
and weather_advisory_rain (>= 35 mm/24 h, score 0.4). Forecasts are injected, so no test touches the
network. The pure functions run anywhere; the agent tests need Postgres + Neo4j (they skip otherwise)
and delete every weather risk event they create."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.agents.watcher import (
    ADVISORY_RAIN_MM,
    ADVISORY_RAIN_SCORE,
    FORECAST_LEAD_HOURS,
    HEAVY_RAIN_MM,
    RISK_TYPE_ADVISORY_RAIN,
    RISK_TYPE_HEAVY_RAIN,
    WatcherAgent,
    heavy_rain_score,
    peak_rolling_rain,
)
from app.config import get_settings
from app.db import SessionLocal
from app.graph_db import init_graph_driver
from app.models import RiskEvent, Site
from app.services.weather_service import WeatherServiceError

T0 = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)


def hourly(mm_at_hour: dict[int, float], start: datetime = T0, hours: int = FORECAST_LEAD_HOURS) -> list[dict]:
    return [{"timestamp": start + timedelta(hours=h), "precipitation_mm": mm_at_hour.get(h, 0.0)} for h in range(hours)]


def storm(peak_mm: float, start: datetime = T0) -> list[dict]:
    """72 dry hours except one wet hour delivering `peak_mm`."""
    return hourly({30: peak_mm}, start)


# ---------------------------------------------------------------------
# pure functions
# ---------------------------------------------------------------------
def test_score_is_0_6_at_the_imd_threshold_and_1_0_at_115_5_mm():
    assert heavy_rain_score(64.5) == 0.6
    assert heavy_rain_score(115.5) == 1.0
    assert heavy_rain_score(90.0) == pytest.approx(0.8)  # linear in between
    assert heavy_rain_score(400.0) == 1.0  # never above 1


def test_the_rolling_24h_window_does_not_split_a_storm_at_midnight():
    # 30 mm at 23:00 and 30 mm at 01:00: two calendar days of 30 mm, but ONE 24-hour spell of 60 mm
    points = hourly({23: 30.0, 25: 30.0})
    peak, start, end = peak_rolling_rain(points)
    assert peak == 60.0
    assert end - start == timedelta(hours=23)


def test_a_forecast_shorter_than_the_window_sums_what_it_has():
    assert peak_rolling_rain(hourly({1: 5.0, 2: 6.0}, hours=6))[0] == 11.0


def test_thresholds_are_the_specified_ones():
    assert (HEAVY_RAIN_MM, ADVISORY_RAIN_MM, ADVISORY_RAIN_SCORE, FORECAST_LEAD_HOURS) == (64.5, 35.0, 0.4, 72)


# ---------------------------------------------------------------------
# the agent (Postgres + Neo4j)
# ---------------------------------------------------------------------
def _postgres_reachable() -> bool:
    try:
        engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


def _neo4j_reachable() -> bool:
    try:
        init_graph_driver().verify_connectivity()
        return True
    except Exception:  # noqa: BLE001
        return False


def _purge(db, driver):
    """Remove every weather risk event (PG rows + Neo4j nodes). Real ones are re-created by the
    scheduler's next pass, so nothing of value is lost."""
    for row in db.scalars(select(RiskEvent).where(RiskEvent.risk_type.like("weather\\_%"))).all():
        db.delete(row)
    db.commit()
    with driver.session() as session:
        session.run("MATCH (r:RiskEvent) WHERE r.risk_type STARTS WITH 'weather_' DETACH DELETE r")


@pytest.fixture
def env():
    if not (_postgres_reachable() and _neo4j_reachable()):
        pytest.skip("needs both Postgres and Neo4j")
    db = SessionLocal()
    driver = init_graph_driver()
    _purge(db, driver)
    try:
        yield db, driver
    finally:
        db.rollback()
        _purge(db, driver)
        db.close()


def _events(db, risk_type=None, resolved=None):
    stmt = select(RiskEvent).where(RiskEvent.risk_type.like("weather\\_%"))
    if risk_type:
        stmt = stmt.where(RiskEvent.risk_type == risk_type)
    if resolved is not None:
        stmt = stmt.where(RiskEvent.resolved.is_(resolved))
    db.expire_all()
    return db.scalars(stmt).all()


def _run(env, forecast):
    db, driver = env
    return WatcherAgent(db, driver, forecast_fn=lambda *_a: forecast).check_for_changes()


def _n_sites(db) -> int:
    return len(db.scalars(select(Site)).all())


def test_a_heavy_forecast_creates_one_heavy_and_one_advisory_event_per_site(env):
    db, _ = env
    _run(env, storm(70.0))
    sites = _n_sites(db)
    heavy, advisory = _events(db, RISK_TYPE_HEAVY_RAIN), _events(db, RISK_TYPE_ADVISORY_RAIN)
    assert len(heavy) == len(advisory) == sites
    assert {e.score for e in heavy} == {heavy_rain_score(70.0)}
    assert {e.score for e in advisory} == {ADVISORY_RAIN_SCORE}
    assert all(e.resolved is False and e.severity.value for e in heavy + advisory)
    assert "64.5" in heavy[0].description and "Open-Meteo" in heavy[0].description


def test_between_the_thresholds_only_the_advisory_exists(env):
    db, _ = env
    _run(env, storm(40.0))
    assert _events(db, RISK_TYPE_HEAVY_RAIN) == []
    assert len(_events(db, RISK_TYPE_ADVISORY_RAIN)) == _n_sites(db)


def test_below_35_mm_nothing_is_created(env):
    db, _ = env
    _run(env, storm(34.9))
    assert _events(db) == []


def test_one_unresolved_event_per_site_per_type_however_often_it_polls(env):
    db, _ = env
    for _ in range(3):
        _run(env, storm(70.0))
    assert len(_events(db, RISK_TYPE_HEAVY_RAIN)) == _n_sites(db)
    assert len(_events(db, RISK_TYPE_ADVISORY_RAIN)) == _n_sites(db)


def test_an_existing_advisory_does_not_block_the_heavy_event(env):
    db, _ = env
    _run(env, storm(40.0))
    assert _events(db, RISK_TYPE_HEAVY_RAIN) == []
    _run(env, storm(70.0))  # the forecast worsens: separate dedup key, so the heavy event is still created
    assert len(_events(db, RISK_TYPE_HEAVY_RAIN)) == _n_sites(db)
    assert len(_events(db, RISK_TYPE_ADVISORY_RAIN)) == _n_sites(db)  # and the advisory was not duplicated


def test_events_auto_resolve_when_the_forecast_no_longer_clears_their_threshold(env):
    db, _ = env
    _run(env, storm(70.0))
    _run(env, storm(40.0))  # heavy cleared, advisory still true
    assert _events(db, RISK_TYPE_HEAVY_RAIN, resolved=False) == []
    assert len(_events(db, RISK_TYPE_HEAVY_RAIN, resolved=True)) == _n_sites(db)
    assert all(e.resolved_at is not None for e in _events(db, RISK_TYPE_HEAVY_RAIN, resolved=True))
    assert len(_events(db, RISK_TYPE_ADVISORY_RAIN, resolved=False)) == _n_sites(db)

    _run(env, storm(5.0))  # nothing clears now
    assert _events(db, resolved=False) == []

    _run(env, storm(70.0))  # a new spell of weather is a new event, not a reopened old one
    assert len(_events(db, RISK_TYPE_HEAVY_RAIN, resolved=False)) == _n_sites(db)
    assert len(_events(db, RISK_TYPE_HEAVY_RAIN)) == 2 * _n_sites(db)


@pytest.mark.parametrize("failure", ["error", "empty"])
def test_an_unavailable_forecast_creates_nothing_and_resolves_nothing(env, caplog, monkeypatch, failure):
    db, driver = env
    # test_migrations runs Alembic, whose fileConfig() DISABLES every logger that already exists (this one
    # included), which would make caplog blind to the warning in a full-suite run
    monkeypatch.setattr(logging.getLogger("oresight.agents"), "disabled", False)
    _run(env, storm(70.0))
    open_before = {e.id for e in _events(db, resolved=False)}
    assert open_before

    def unavailable(*_a):
        if failure == "error":
            raise WeatherServiceError("Weather service request timed out", status_code=504)
        return []

    with caplog.at_level(logging.WARNING, logger="oresight.agents"):
        created = WatcherAgent(db, driver, forecast_fn=unavailable).check_for_changes()
    assert created == []
    assert {e.id for e in _events(db, resolved=False)} == open_before, "no data is not the same as 'no rain'"
    assert any("rain forecast unavailable" in r.message and "no weather risk events" in r.message for r in caplog.records)


def test_an_unavailable_forecast_on_an_empty_db_creates_no_event_and_no_fallback_numbers(env):
    db, driver = env

    def boom(*_a):
        raise WeatherServiceError("Failed to connect to weather service", status_code=502)

    assert WatcherAgent(db, driver, forecast_fn=boom).check_for_changes() == []
    assert _events(db) == []


def test_a_forecast_overlapping_a_neo4j_weather_event_is_linked_to_it(env):
    db, driver = env
    # we_bal_01 is Balaghat's demo heavy-rain WeatherEvent; seed_scenario_a re-dates it around "now",
    # so read its dates instead of assuming them
    with driver.session() as session:
        event = session.run("MATCH (w:WeatherEvent {id: 'we_bal_01'}) RETURN w.start_date AS s").single()
    start = event["s"].to_native()
    _run(env, storm(70.0, start=datetime(start.year, start.month, start.day, tzinfo=timezone.utc)))
    balaghat = db.scalars(select(Site).where(Site.name == "Balaghat")).one()
    heavy = next(e for e in _events(db, RISK_TYPE_HEAVY_RAIN) if e.site_id == balaghat.id)
    with driver.session() as session:
        linked = session.run(
            "MATCH (w:WeatherEvent {id: 'we_bal_01'})-[:CORRELATES_WITH]->(r:RiskEvent {external_ref: $ref}) RETURN count(r) AS n",
            ref=str(heavy.id),
        ).single()["n"]
    assert linked == 1


def test_a_forecast_overlapping_no_weather_event_still_creates_the_risk_without_a_link(env):
    db, driver = env
    _run(env, storm(70.0, start=datetime(2030, 1, 1, tzinfo=timezone.utc)))
    heavy = _events(db, RISK_TYPE_HEAVY_RAIN)
    assert len(heavy) == _n_sites(db)
    with driver.session() as session:
        edges = session.run(
            "MATCH (:WeatherEvent)-[:CORRELATES_WITH]->(r:RiskEvent) WHERE r.risk_type STARTS WITH 'weather_' RETURN count(r) AS n"
        ).single()["n"]
    assert edges == 0
