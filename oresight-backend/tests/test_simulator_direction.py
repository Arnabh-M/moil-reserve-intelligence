"""A disruption must move the forecast the right way: the property the old model failed.

For a sample of days across 2026, every site and every scenario is replayed through the SimulatorAgent
(`as_of` rebuilds the whole feature row from data before that day) and the "after" production forecast is
compared with "before". The full 265-day sweep (scripts/simulator_sweep.py) found >= 92% of days going
the right way in every cell and at most ~5% the wrong way; this pins a comfortable margin around that on a
~10-day stride, so a retrain or a feature change that makes a scenario incoherent again fails here. The
old model would fail it badly (e.g. delay_blasting raised the forecast on 261 of 265 days at Balaghat).

Needs the rebuilt demo DB and the shipped model. No Neo4j: the graph traversal does not touch the forecast.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.agents.simulator import SCENARIO_TYPES, SimulatorAgent
from app.config import get_settings
from app.db import SessionLocal
from app.models import Site

SAMPLE_DAYS = [date(2026, 1, 15) + timedelta(days=10 * k) for k in range(26)]  # 2026-01-15 .. 2026-09-22
MIN_LOWER = 0.85  # measured on the full sweep: >= 0.92
MAX_HIGHER = 0.10  # measured on the full sweep: <= 0.054


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture(scope="module")
def replay():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    db = SessionLocal()
    agent = SimulatorAgent(db, None)
    agent._traverse_graph = lambda *a, **k: ([], {"nodes": [], "edges": []})
    results = {}
    for site in db.scalars(select(Site).order_by(Site.id)).all():
        for scenario in SCENARIO_TYPES:
            results[(site.name, scenario)] = [agent.run_scenario(scenario, site.id, 5, as_of=d) for d in SAMPLE_DAYS]
    yield results
    db.close()


def test_the_sample_spans_the_year(replay):
    assert SAMPLE_DAYS[-1] == date(2026, 9, 22) and len(replay) == 3 * len(SCENARIO_TYPES)


@pytest.mark.parametrize("scenario", SCENARIO_TYPES)
@pytest.mark.parametrize("site", ["Balaghat", "Nagpur", "Bhandara"])
def test_a_disruption_lowers_the_forecast_on_almost_every_day(replay, site, scenario):
    runs = replay[(site, scenario)]
    lower = sum(r["after"]["production_forecast_tonnes"] < r["before"]["production_forecast_tonnes"] for r in runs)
    higher = sum(r["after"]["production_forecast_tonnes"] > r["before"]["production_forecast_tonnes"] for r in runs)
    n = len(runs)
    assert lower / n >= MIN_LOWER, f"{site}/{scenario}: forecast fell on only {lower}/{n} sampled days"
    assert higher / n <= MAX_HIGHER, f"{site}/{scenario}: a disruption RAISED the forecast on {higher}/{n} sampled days"
    # the risk score follows the model's own predicted worsening, so it can never fall
    assert all(r["after"]["risk_score"] >= r["before"]["risk_score"] for r in runs)


@pytest.mark.parametrize("site", ["Balaghat", "Nagpur", "Bhandara"])
def test_a_bigger_storm_never_helps(site):
    """Within one day's state, more rain must not raise the forecast (same before, monotone after)."""
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    db = SessionLocal()
    try:
        agent = SimulatorAgent(db, None)
        agent._traverse_graph = lambda *a, **k: ([], {"nodes": [], "edges": []})
        site_id = db.scalars(select(Site).where(Site.name == site)).one().id
        violations = 0
        for d in SAMPLE_DAYS:
            after = [
                agent.run_scenario("rainfall_event", site_id, 5, severity=mm, as_of=d)["after"]["production_forecast_tonnes"]
                for mm in (0.0, 23.5, 87.8)
            ]
            violations += not (after[0] >= after[1] >= after[2])
        assert violations <= 0.10 * len(SAMPLE_DAYS), f"{site}: rain was non-monotone on {violations}/{len(SAMPLE_DAYS)} days"
    finally:
        db.close()
