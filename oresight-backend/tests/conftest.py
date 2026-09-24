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


@pytest.fixture(scope="session", autouse=True)
def _remove_equipment_risk_events_left_by_the_suite():
    """Tests that toggle equipment status open `equipment_failure` (reason "Smoke test failure") and
    `equipment_flapping` risk events, and only some of them delete what they create. Whatever of those two
    types exists after the session but not before it is test residue: remove it (Postgres + Neo4j), so
    the demo database is not littered by a routine test run."""
    from sqlalchemy import delete, func, select

    from app.db import SessionLocal
    from app.models import RiskEvent, ShiftPlanEntry

    types = ("equipment_failure", "equipment_flapping")
    try:
        db = SessionLocal()
        before = db.scalar(select(func.coalesce(func.max(RiskEvent.id), 0))) or 0
        db.close()
    except Exception:  # noqa: BLE001 - no database: the DB-backed tests skip themselves
        yield
        return
    yield
    db = SessionLocal()
    try:
        ids = list(db.scalars(select(RiskEvent.id).where(RiskEvent.id > before, RiskEvent.risk_type.in_(types))))
        if ids:
            db.execute(delete(ShiftPlanEntry).where(ShiftPlanEntry.risk_event_id.in_(ids)))
            db.execute(delete(RiskEvent).where(RiskEvent.id.in_(ids)))
            db.commit()
            try:
                from app.graph_db import init_graph_driver

                with init_graph_driver().session() as session:
                    session.run("MATCH (r:RiskEvent) WHERE r.external_ref IN $refs DETACH DELETE r", refs=[str(i) for i in ids])
            except Exception:  # noqa: BLE001
                pass
    finally:
        db.close()
