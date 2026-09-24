"""The Simulator's scenario -> feature mapping and its router behaviour.

The mapping is a deliberate, documented contract (app/agents/simulator.py module docstring):
  equipment_down -> equipment_down_today_pct   (NOT rolling_7d_downtime_pct: non-monotone in the model)
  delay_blasting -> blast_delay_days_lag
  rainfall_event -> rain_3d_mm, rain_7d_mm, heavy_rain_lag1   (NOT rain_today_mm: no same-day effect
                                                               exists in the world the model learned)
These tests pin it, and the rainfall arithmetic, without a database: the agent is built with no
session/driver (its constructor never touches them) and fed a hand-built live feature row.
"""

import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.agents.simulator import SimulatorAgent
from app.config import get_settings
from app.main import app
from app.services.forecast_model import ModelVersionMismatchError
from app.services.live_features import FeatureConstants, LiveDataUnavailableError, LiveFeatures

AS_OF = date(2026, 6, 15)
CONSTANTS = FeatureConstants(
    machines_per_site={"balaghat": 5}, heavy_rain_mm=35.0, backlog_decay=0.85,
    rolling_downtime_window_days=7, maintenance_reason="scheduled maintenance",
)
BASE_VALUES = {
    "rain_today_mm": 4.0, "rain_3d_mm": 12.0, "rain_7d_mm": 30.0, "heavy_rain_lag1": 0.0,
    "soil_moisture_m3m3": 0.31, "rolling_7d_downtime_pct": 0.08, "equipment_down_today_pct": 0.04,
    "days_since_last_maintenance": 40.0, "backlog_t": 0.4, "blast_delay_days_lag": 1.0,
    "dow_sin": 0.5, "dow_cos": 0.8, "month_sin": 0.1, "month_cos": -0.9,
}


def _live(rain_lag1: float = 2.0, blast_events=((AS_OF - timedelta(days=2), 1),), **overrides) -> LiveFeatures:
    return LiveFeatures(
        site_key="balaghat", as_of=AS_OF, values={**BASE_VALUES, **overrides}, rain_lag1_mm=rain_lag1,
        blast_events=list(blast_events), n_machines=5, constants=CONSTANTS,
    )


@pytest.fixture(scope="module")
def agent():
    return SimulatorAgent(None, None)  # loads the shipped artifact; touches neither store


def _changed(before: dict, after: dict) -> set[str]:
    return {k for k in before if not (before[k] == after[k] or (math.isnan(before[k]) and math.isnan(after[k])))}


# ---------------------------------------------------------------------
# the mapping: only the approved features move
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "scenario, duration, severity, allowed",
    [
        ("equipment_down", 5, None, {"equipment_down_today_pct"}),
        ("delay_blasting", 5, None, {"blast_delay_days_lag"}),
        ("rainfall_event", 5, 60.0, {"rain_3d_mm", "rain_7d_mm", "heavy_rain_lag1"}),
        ("rainfall_event", 1, 60.0, {"rain_3d_mm", "rain_7d_mm", "heavy_rain_lag1"}),
    ],
)
def test_only_the_mapped_features_change(agent, scenario, duration, severity, allowed):
    live = _live()
    after = agent._perturb_features(live, scenario, duration, severity)
    changed = _changed(live.values, after)
    assert changed, f"{scenario} changed nothing"
    assert changed <= allowed, f"{scenario} moved unmapped features: {changed - allowed}"
    # the two features the mapping explicitly refuses to touch
    assert after["rolling_7d_downtime_pct"] == live.values["rolling_7d_downtime_pct"]
    assert after["rain_today_mm"] == live.values["rain_today_mm"]


def test_equipment_down_takes_one_more_machine_out_and_never_exceeds_the_whole_fleet(agent):
    assert agent._perturb_features(_live(), "equipment_down", 5)["equipment_down_today_pct"] == pytest.approx(0.04 + 1 / 5)
    assert agent._perturb_features(_live(equipment_down_today_pct=0.95), "equipment_down", 5)["equipment_down_today_pct"] == 1.0


def test_blast_delay_days_are_unioned_with_the_real_ones_not_double_counted(agent):
    # the site already has a delay on AS_OF-3 and AS_OF-2; a 3-day scenario delay covers AS_OF-3..AS_OF-1
    live = _live(blast_events=[(AS_OF - timedelta(days=3), 2)], blast_delay_days_lag=2.0)
    assert agent._perturb_features(live, "delay_blasting", 3)["blast_delay_days_lag"] == 3.0


def test_a_long_blast_delay_saturates_at_the_seven_day_window(agent):
    assert agent._perturb_features(_live(), "delay_blasting", 30)["blast_delay_days_lag"] == 7.0


# ---------------------------------------------------------------------
# rainfall arithmetic (severity = mm of rain over 3 days)
# ---------------------------------------------------------------------
def test_sixty_mm_in_one_day_is_a_heavy_rain_day_but_over_three_days_it_is_not(agent):
    one_day = agent._perturb_features(_live(), "rainfall_event", 1, 60.0)
    three_day = agent._perturb_features(_live(), "rainfall_event", 3, 60.0)
    assert one_day["heavy_rain_lag1"] == 1.0  # 60 mm/day >= 35
    assert three_day["heavy_rain_lag1"] == 0.0  # 20 mm/day + 2 mm yesterday < 35
    for after in (one_day, three_day):
        assert after["rain_3d_mm"] == pytest.approx(12.0 + 60.0)  # the severity is, by definition, the 3-day total
        assert after["rain_7d_mm"] == pytest.approx(30.0 + 60.0)  # a storm of <= 3 days lies wholly inside the 7-day window


def test_a_longer_storm_keeps_falling_at_the_same_rate_up_to_the_seven_day_window(agent):
    five_day = agent._perturb_features(_live(), "rainfall_event", 5, 60.0)
    assert five_day["rain_3d_mm"] == pytest.approx(12.0 + 60.0)
    assert five_day["rain_7d_mm"] == pytest.approx(30.0 + 20.0 * 5)  # 20 mm/day for 5 days
    thirty_day = agent._perturb_features(_live(), "rainfall_event", 30, 60.0)
    assert thirty_day["rain_7d_mm"] == pytest.approx(30.0 + 20.0 * 7)  # only 7 days fit in the window


def test_the_storms_rain_adds_to_yesterdays_real_rain_and_the_threshold_is_inclusive(agent):
    # 60 mm over 3 days = 20 mm/day, on top of yesterday's real rain, against the model's >= 35 mm flag
    assert agent._perturb_features(_live(rain_lag1=15.0), "rainfall_event", 3, 60.0)["heavy_rain_lag1"] == 1.0
    assert agent._perturb_features(_live(rain_lag1=14.9), "rainfall_event", 3, 60.0)["heavy_rain_lag1"] == 0.0


def test_zero_mm_is_no_event(agent):
    live = _live()
    assert _changed(live.values, agent._perturb_features(live, "rainfall_event", 5, 0.0)) == set()


def test_unobserved_yesterday_leaves_the_heavy_flag_missing_not_guessed(agent):
    after = agent._perturb_features(_live(rain_lag1=float("nan")), "rainfall_event", 3, 60.0)
    assert math.isnan(after["heavy_rain_lag1"])


def test_without_a_severity_the_medium_training_level_is_used_and_it_is_not_zero(agent):
    default = agent.default_rain_severity_mm()
    assert default > 5.0, "a default rainfall 'event' must be an event (medium of the RAINY windows), not ~0 mm"
    assert agent._perturb_features(_live(), "rainfall_event", 5, None)["rain_3d_mm"] == pytest.approx(12.0 + default)


def test_the_frame_refuses_a_row_that_lacks_a_model_column(agent):
    values = dict(BASE_VALUES)
    del values["backlog_t"]
    with pytest.raises(RuntimeError, match="backlog_t"):
        agent._as_frame(values)


# ---------------------------------------------------------------------
# router: severity units, response provenance, refusal paths
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


@pytest.fixture(scope="module")
def client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app) as c:
        yield c


def _post(client, **body):
    return client.post("/simulate", json={"site_id": 1, "duration_days": 5, **body})


def test_rainfall_severity_is_mm_so_values_above_100_are_valid(client):
    assert _post(client, scenario_type="rainfall_event", severity=120).status_code == 200
    assert _post(client, scenario_type="rainfall_event", severity=4000).status_code == 200


def test_rainfall_severity_beyond_any_physical_rainfall_is_422(client):
    assert _post(client, scenario_type="rainfall_event", severity=4001).status_code == 422
    assert _post(client, scenario_type="rainfall_event", severity=-1).status_code == 422


def test_percentage_scenarios_keep_their_100_bound(client):
    assert _post(client, scenario_type="equipment_down", severity=101).status_code == 422
    assert _post(client, scenario_type="delay_blasting", severity=101).status_code == 422
    body = {"scenario_type": "rainfall_event", "conditions": [{"type": "equipment_down", "severity": 101, "duration": 2}]}
    assert _post(client, **body).status_code == 422  # the bound follows the CONDITION's type


def test_ood_warning_for_rainfall_is_in_mm_not_percent(client):
    r = _post(
        client, scenario_type="rainfall_event", severity=200,
        conditions=[{"type": "rainfall_event", "severity": 200, "duration": 5}],
    )
    assert r.status_code == 200
    condition = r.json()["conditions_ood"][0]
    assert condition["severity_out_of_distribution"] is True
    assert condition["severity_valid_range"] == [0.0, 147.0]
    assert " mm" in condition["warnings"][0] and "%" not in condition["warnings"][0]


def test_the_response_says_which_day_the_model_state_describes(client):
    body = _post(client, scenario_type="equipment_down").json()
    as_of = date.fromisoformat(body["model_state_as_of"])
    assert as_of < date.today(), "today is still in progress, so it can never be the model state"
    assert isinstance(body["model_inputs_missing"], list)


def test_rainfall_severity_actually_drives_the_projection(client):
    light = _post(client, scenario_type="rainfall_event", severity=7.5).json()
    severe = _post(client, scenario_type="rainfall_event", severity=87.8).json()
    assert light["before"] == severe["before"]
    assert severe["after"]["production_forecast_tonnes"] < light["after"]["production_forecast_tonnes"]


def test_a_model_the_running_xgboost_cannot_trust_is_a_503_not_a_wrong_answer(client, monkeypatch):
    import app.routers.simulate as simulate_router

    def _refuse(*_a, **_k):
        raise ModelVersionMismatchError("Shortfall model was trained with xgboost 3.4.1 but this process runs xgboost 2.1.4")

    monkeypatch.setattr(simulate_router, "SimulatorAgent", _refuse)
    r = _post(client, scenario_type="equipment_down")
    assert r.status_code == 503 and "xgboost" in r.json()["detail"]


def test_missing_live_inputs_are_a_503_not_a_guess(client, monkeypatch):
    import app.routers.simulate as simulate_router

    def _no_rain(self, *_a, **_k):
        raise LiveDataUnavailableError("the satellite rainfall record has stopped updating")

    monkeypatch.setattr(simulate_router.SimulatorAgent, "run_scenario", _no_rain)
    r = _post(client, scenario_type="rainfall_event")
    assert r.status_code == 503 and "unavailable" in r.json()["detail"].lower()
