"""Tests for GET /demo/scenarios — stable-key -> current risk_event_id lookup.

Runs against the real seeded stack; SKIPs if Postgres is unreachable.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.main import app

EXPECTED_KEYS = {"weather-delay", "equipment-down"}
_FIELDS = {
    "key",
    "scenario_name",
    "available",
    "risk_event_id",
    "site_id",
    "site_name",
    "risk_type",
    "description",
    "expected_recommendation",
}


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(
            get_settings().DATABASE_URL, connect_args={"connect_timeout": 3}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture(scope="module")
def client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable")
    with TestClient(app) as c:
        yield c


def test_lists_every_configured_scenario_with_the_full_shape(client):
    body = client.get("/demo/scenarios").json()
    assert {s["key"] for s in body} == EXPECTED_KEYS
    for s in body:
        assert set(s) == _FIELDS


def test_scenarios_resolve_to_live_risk_events(client):
    body = client.get("/demo/scenarios").json()
    known_ids = {r["id"] for r in client.get("/risk-events").json()}

    for s in body:
        assert s["available"] is True, f"{s['key']} did not resolve — is its seed script run?"
        assert s["risk_event_id"] in known_ids
        # the resolved row really is the shape the scenario claims
        assert s["risk_type"] == ("production_shortfall" if s["key"] == "weather-delay" else "equipment_failure")


def test_equipment_down_scenario_leads_with_a_redeploy(client):
    scenario = next(s for s in client.get("/demo/scenarios").json() if s["key"] == "equipment-down")
    recs = client.get(f"/recommendations?risk_event_id={scenario['risk_event_id']}").json()
    assert recs[0]["options"][0]["type"] == scenario["expected_recommendation"] == "redeploy"


def test_weather_delay_scenario_has_a_real_neo4j_causal_graph(client):
    scenario = next(s for s in client.get("/demo/scenarios").json() if s["key"] == "weather-delay")
    graph = client.get(f"/risk-events/{scenario['risk_event_id']}/causal-graph").json()
    assert graph["graph_source"] == "neo4j"
    assert len(graph["nodes"]) > 1


def test_does_not_touch_the_risk_events_contract(client):
    """GET /risk-events must be unchanged — no demo fields leaked in."""
    body = client.get("/risk-events").json()[0]
    assert set(body) == {
        "id", "site_id", "site_name", "risk_type", "severity",
        "score", "description", "resolved", "detected_at",
    }
