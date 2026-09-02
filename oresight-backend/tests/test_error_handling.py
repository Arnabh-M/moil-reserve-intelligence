"""Task C: every endpoint fails cleanly — meaningful status codes, JSON
error bodies with an `error_code`, never a naked 500 / stack trace, and a
bounded response when Postgres or Neo4j is unreachable.

Infra-down cases are simulated with dependency overrides / monkeypatch
rather than actually stopping containers, so the suite stays hermetic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.config import get_settings
from app.db import get_db
from app.graph_db import get_graph_driver
from app.main import app


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


@pytest.fixture
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_graph_driver, None)


# --------------------------------------------------------------------------
# unknown ids -> 404 (never 500), with a machine-readable error_code
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, url",
    [
        ("GET", "/sites/999999"),
        ("GET", "/sites/999999/geojson"),
        ("GET", "/risk-events/999999/causal-graph"),
        ("GET", "/recommendations?risk_event_id=999999"),
        ("GET", "/reserve-zones?site_id=999999"),
        ("GET", "/production?site_id=999999"),
        ("GET", "/site-notes/search?q=x&site_id=999999"),
    ],
)
def test_unknown_id_is_404_with_error_code(client, method, url):
    r = client.request(method, url)
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "method, url",
    [
        ("POST", "/simulate"),
        ("POST", "/site-notes"),
        ("POST", "/production"),
        ("GET", "/sites/not-an-int"),
        ("GET", "/recommendations"),
        ("GET", "/site-notes/search"),
        ("POST", "/reports/upload"),
    ],
)
def test_malformed_request_is_422_not_500(client, method, url):
    r = client.request(method, url, json={"garbage": True})
    assert r.status_code == 422
    assert r.json()["error_code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# Postgres unreachable -> 503 (app-level OperationalError handler)
# --------------------------------------------------------------------------


def _raise_db_down():
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))
    yield  # pragma: no cover - generator dependency shape


@pytest.mark.parametrize("url", ["/sites", "/kpi/summary", "/equipment", "/site-notes/search?q=rain"])
def test_postgres_down_is_503(client, _clear_overrides, url):
    app.dependency_overrides[get_db] = _raise_db_down
    r = client.get(url)
    assert r.status_code == 503
    body = r.json()
    assert body["error_code"] == "SERVICE_UNAVAILABLE"
    assert "detail" in body and "unavailable" in body["detail"].lower()


# --------------------------------------------------------------------------
# Neo4j unreachable
# --------------------------------------------------------------------------


class _DeadDriver:
    """A driver whose every session raises ServiceUnavailable, like a real
    driver pointed at a down Neo4j.
    """

    def session(self, *_a, **_k):
        raise ServiceUnavailable("Unable to connect to Neo4j")


def test_neo4j_down_causal_graph_degrades_to_fallback(client, _clear_overrides):
    app.dependency_overrides[get_graph_driver] = lambda: _DeadDriver()
    rid = client.get("/risk-events").json()[0]["id"]
    r = client.get(f"/risk-events/{rid}/causal-graph")
    assert r.status_code == 200
    body = r.json()
    assert body["graph_source"] == "postgres_fallback"
    assert len(body["nodes"]) == 1 and body["edges"] == []
    assert body["note"]


def test_neo4j_down_recommendations_is_503(client, _clear_overrides):
    app.dependency_overrides[get_graph_driver] = lambda: _DeadDriver()
    rid = client.get("/risk-events").json()[0]["id"]
    r = client.get(f"/recommendations?risk_event_id={rid}")
    assert r.status_code == 503
    assert r.json()["error_code"] == "SERVICE_UNAVAILABLE"


def test_neo4j_down_reports_upload_still_returns_extracted_deposits(client, _clear_overrides):
    app.dependency_overrides[get_graph_driver] = lambda: _DeadDriver()
    from pathlib import Path

    pdf = (Path(__file__).parent / "fixtures" / "sample_survey.pdf").read_bytes()
    r = client.post("/reports/upload", files={"file": ("s.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["deposit_count"] == 3
    assert body["nodes_created"] == []
    assert any("neo4j" in w.lower() for w in body["warnings"])


# --------------------------------------------------------------------------
# trained model file missing -> 503 (not 500)
# --------------------------------------------------------------------------


def test_simulate_missing_model_file_is_503(client, monkeypatch):
    import app.routers.simulate as simulate_router

    def _boom(*_a, **_k):
        raise FileNotFoundError("models/shortfall_forecaster.pkl")

    monkeypatch.setattr(simulate_router, "SimulatorAgent", _boom)
    r = client.post(
        "/simulate",
        json={"scenario_type": "rainfall_event", "site_id": 1, "duration_days": 5},
    )
    assert r.status_code == 503
    assert r.json()["error_code"] == "SERVICE_UNAVAILABLE"
    assert "model" in r.json()["detail"].lower()


def test_recommendations_missing_model_file_is_503(client, monkeypatch):
    import app.routers.recommendations as rec_router

    def _boom(*_a, **_k):
        raise FileNotFoundError("models/shortfall_forecaster.pkl")

    monkeypatch.setattr(rec_router, "PlannerAgent", _boom)
    rid = client.get("/risk-events").json()[0]["id"]
    r = client.get(f"/recommendations?risk_event_id={rid}")
    assert r.status_code == 503
    assert r.json()["error_code"] == "SERVICE_UNAVAILABLE"
