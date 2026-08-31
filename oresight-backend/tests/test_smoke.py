"""End-to-end smoke tests against the real seeded dev database.

These hit the actual Postgres instance (via `docker compose up -d` +
`python -m app.seed_dev`), not a mock. Skips (does not fail) if Postgres
isn't reachable, so teammates without the DB running locally don't get
confusing failures. The two tests that write data (equipment status,
production create) clean up after themselves so re-running this suite never
pollutes the demo dataset.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import ProductionRecord, RiskEvent


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
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app) as c:
        yield c


GET_ENDPOINTS = [
    "/sites",
    "/equipment",
    "/production",
    "/risk-events",
    "/reserve-zones",
    "/kpi/summary",
    "/admin/jobs",
]


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_endpoint_returns_200_and_nonempty(client, path):
    response = client.get(path)
    assert response.status_code == 200

    body = response.json()
    if isinstance(body, list):
        assert len(body) > 0, f"{path} returned an empty list"
    elif isinstance(body, dict) and body.get("type") == "FeatureCollection":
        assert len(body["features"]) > 0, f"{path} returned an empty FeatureCollection"
    else:
        assert body, f"{path} returned an empty payload"


def test_path_param_endpoints_return_200_and_nonempty(client):
    """Covers the GET endpoints that need a real id first: site detail/geojson,
    the causal graph, and recommendations.
    """
    sites = client.get("/sites").json()
    site_id = sites[0]["id"]

    detail = client.get(f"/sites/{site_id}")
    assert detail.status_code == 200
    assert detail.json()

    geojson = client.get(f"/sites/{site_id}/geojson")
    assert geojson.status_code == 200
    assert geojson.json()["features"]

    risk_events = client.get("/risk-events").json()
    assert risk_events
    risk_event_id = risk_events[0]["id"]

    graph = client.get(f"/risk-events/{risk_event_id}/causal-graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"]

    recommendations = client.get(f"/recommendations?risk_event_id={risk_event_id}")
    assert recommendations.status_code == 200
    assert recommendations.json()


def test_equipment_status_down_creates_risk_event(client):
    equipment = client.get("/equipment").json()
    target = next(e for e in equipment if e["status"] == "up")
    site_id = target["site_id"]

    before_count = len(client.get(f"/risk-events?site_id={site_id}").json())

    response = client.post(
        f"/equipment/{target['id']}/status",
        json={"status": "down", "reason": "Smoke test failure"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "down"

    after = client.get(f"/risk-events?site_id={site_id}").json()
    assert len(after) == before_count + 1

    # Restore equipment and remove the risk event this test created.
    client.post(f"/equipment/{target['id']}/status", json={"status": "up", "reason": None})
    created = max(after, key=lambda r: r["id"])

    db = SessionLocal()
    try:
        db.query(RiskEvent).filter(RiskEvent.id == created["id"]).delete()
        db.commit()
    finally:
        db.close()


def test_production_duplicate_returns_409(client):
    sites = client.get("/sites").json()
    site_id = sites[0]["id"]
    payload = {
        "site_id": site_id,
        "date": "2027-06-15",
        "actual_output": 1000.0,
        "target_output": 1100.0,
    }

    first = client.post("/production", json=payload)
    assert first.status_code == 201
    created_id = first.json()["id"]

    duplicate = client.post("/production", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "CONFLICT"

    db = SessionLocal()
    try:
        db.query(ProductionRecord).filter(ProductionRecord.id == created_id).delete()
        db.commit()
    finally:
        db.close()


def test_simulate_after_differs_from_before(client):
    sites = client.get("/sites").json()
    site_id = sites[0]["id"]

    response = client.post(
        "/simulate",
        json={"scenario_type": "equipment_down", "site_id": site_id, "duration_days": 5},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["before"] != body["after"]
    assert (
        body["after"]["production_forecast_tonnes"]
        < body["before"]["production_forecast_tonnes"]
    )
    assert body["after"]["risk_score"] >= body["before"]["risk_score"]
