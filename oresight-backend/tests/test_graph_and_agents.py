"""Tests for the Day 3 additions: Neo4j graph layer + agent orchestration
endpoints (causal-graph, recommendations, simulate) and the Watcher job.

Like test_smoke.py these run against the real seeded stack (Postgres +
Neo4j) and SKIP rather than fail when infra isn't reachable, so teammates
without the stack up don't get noise. Anything that writes cleans up after
itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.graph_db import graph_health, init_graph_driver
from app.main import app
from app.models import Equipment, EquipmentStatus, RiskEvent

_OPTION_TYPES = {"reschedule", "redeploy", "adjust_plan"}
_GRAPH_SOURCES = {"neo4j", "postgres_fallback", "simulated"}


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


def _neo4j_reachable() -> bool:
    try:
        init_graph_driver().verify_connectivity()
        return True
    except (ServiceUnavailable, Neo4jError, OSError):
        return False


@pytest.fixture(scope="module")
def client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def linked_risk_event():
    """Yield the id of a risk event that has a real Neo4j causal graph,
    created by running the Watcher against a directly-toggled 'down' unit
    (bypassing POST /equipment/{id}/status so no graph-less Postgres risk is
    auto-created). Cleaned up — Postgres row + Neo4j node — on teardown.
    """
    if not (_postgres_reachable() and _neo4j_reachable()):
        pytest.skip("needs both Postgres and Neo4j")

    from app.agents.watcher import WatcherAgent

    db = SessionLocal()
    driver = init_graph_driver()
    risk_event_id: int | None = None
    equipment_id: int | None = None
    original = None
    try:
        equipment = (
            db.query(Equipment)
            .filter(Equipment.status == EquipmentStatus.UP)
            .order_by(Equipment.id.desc())
            .first()
        )
        equipment_id = equipment.id
        original = (equipment.status_reason, equipment.last_status_change)
        equipment.status = EquipmentStatus.DOWN
        equipment.last_status_change = datetime.now(timezone.utc)
        equipment.status_reason = "graph/agents test — transient"
        db.commit()

        created = WatcherAgent(db, driver).check_for_changes(
            since=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        risk_event_id = next(
            c["id"]
            for c in created
            if c["site_id"] == equipment.site_id
            and c["risk_type"] == "equipment_failure"
        )

        equipment = db.get(Equipment, equipment_id)
        equipment.status = EquipmentStatus.UP
        equipment.status_reason, equipment.last_status_change = original
        db.commit()

        yield risk_event_id
    finally:
        if equipment_id is not None:
            eq = db.get(Equipment, equipment_id)
            if eq is not None and original is not None:
                eq.status = EquipmentStatus.UP
                eq.status_reason, eq.last_status_change = original
        if risk_event_id is not None:
            row = db.get(RiskEvent, risk_event_id)
            if row is not None:
                db.delete(row)
        db.commit()
        if risk_event_id is not None:
            with driver.session() as session:
                session.run(
                    "MATCH (r:RiskEvent {external_ref: $ref}) DETACH DELETE r",
                    ref=str(risk_event_id),
                )
        db.close()


# --------------------------------------------------------------------------
# graph_db
# --------------------------------------------------------------------------


def test_graph_health_reports_connected():
    if not _neo4j_reachable():
        pytest.skip("Neo4j not reachable")
    assert graph_health() == {"status": "connected"}


def test_health_endpoint_includes_neo4j(client):
    body = client.get("/health").json()
    assert body["neo4j"] in {"connected", "unavailable"}


# --------------------------------------------------------------------------
# GET /risk-events/{id}/causal-graph
# --------------------------------------------------------------------------


def test_causal_graph_404_for_unknown_risk_event(client):
    r = client.get("/risk-events/999999/causal-graph")
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"


def test_causal_graph_react_flow_shape(client):
    risk_event_id = client.get("/risk-events").json()[0]["id"]
    r = client.get(f"/risk-events/{risk_event_id}/causal-graph")
    assert r.status_code == 200

    body = r.json()
    assert set(body) >= {"nodes", "edges", "graph_source"}
    assert body["graph_source"] in _GRAPH_SOURCES
    assert body["nodes"], "a causal graph must never come back with zero nodes"
    for node in body["nodes"]:
        assert set(node) == {"id", "label", "type"}
    for edge in body["edges"]:
        assert set(edge) == {"source", "target", "relationship"}
        node_ids = {n["id"] for n in body["nodes"]}
        assert edge["source"] in node_ids and edge["target"] in node_ids


def test_causal_graph_fallback_is_explicit(client):
    """A seed-era risk event (id 1) has no Neo4j node — the endpoint must
    say so explicitly rather than return an empty graph.
    """
    r = client.get("/risk-events/1/causal-graph")
    assert r.status_code == 200
    body = r.json()
    assert body["graph_source"] == "postgres_fallback"
    assert len(body["nodes"]) == 1
    assert body["edges"] == []
    assert body["note"]


def test_causal_graph_live_traversal(client, linked_risk_event):
    r = client.get(f"/risk-events/{linked_risk_event}/causal-graph")
    assert r.status_code == 200
    body = r.json()
    assert body["graph_source"] == "neo4j"
    assert len(body["nodes"]) > 1
    assert any(e["relationship"] == "CAUSES" for e in body["edges"])


# --------------------------------------------------------------------------
# GET /recommendations
# --------------------------------------------------------------------------


def test_recommendations_404_for_unknown_risk_event(client):
    r = client.get("/recommendations?risk_event_id=999999")
    assert r.status_code == 404


def test_recommendations_missing_param_is_422(client):
    assert client.get("/recommendations").status_code == 422


def test_recommendations_passthrough_shape(client, linked_risk_event):
    r = client.get(f"/recommendations?risk_event_id={linked_risk_event}")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body

    for rec in body:
        assert rec["risk_event_id"] == linked_risk_event
        assert rec["trigger"]
        for opt in rec["options"]:
            assert opt["type"] in _OPTION_TYPES
            assert 0 <= opt["projected_impact"] <= 100
            assert 0 <= opt["confidence"] <= 1
        impacts = [o["projected_impact"] for o in rec["options"]]
        assert impacts == sorted(impacts, reverse=True), "options must be ranked"


# --------------------------------------------------------------------------
# POST /simulate
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario", ["equipment_down", "delay_blasting", "rainfall_event"]
)
def test_simulate_supported_scenarios(client, scenario):
    r = client.post(
        "/simulate",
        json={"scenario_type": scenario, "site_id": 1, "duration_days": 5},
    )
    assert r.status_code == 200
    body = r.json()
    for snap in (body["before"], body["after"]):
        assert set(snap) == {
            "reserve_confidence",
            "production_forecast_tonnes",
            "risk_score",
        }
    assert isinstance(body["affected_graph_path"], list)
    assert body["updated_graph"]["graph_source"] == "simulated"
    # updated_graph must be the same shape as the causal-graph endpoint
    for node in body["updated_graph"]["nodes"]:
        assert set(node) == {"id", "label", "type"}


def test_simulate_rejects_unknown_scenario(client):
    r = client.post(
        "/simulate",
        json={"scenario_type": "meteor_strike", "site_id": 1, "duration_days": 5},
    )
    assert r.status_code == 422


def test_simulate_unknown_site_is_404(client):
    r = client.post(
        "/simulate",
        json={"scenario_type": "equipment_down", "site_id": 99999, "duration_days": 5},
    )
    assert r.status_code == 404


def test_simulate_duration_out_of_range_is_422(client):
    r = client.post(
        "/simulate",
        json={"scenario_type": "equipment_down", "site_id": 1, "duration_days": 9999},
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------
# Watcher wired into the scheduler
# --------------------------------------------------------------------------


def test_run_watcher_executes_without_raising():
    if not (_postgres_reachable() and _neo4j_reachable()):
        pytest.skip("needs both Postgres and Neo4j")
    from app.services import scheduler

    scheduler.run_watcher()  # must not raise
    assert scheduler._watcher_last_result["ran_at"] is not None
    assert scheduler._watcher_last_result["error"] is None


def test_run_watcher_swallows_agent_failure(monkeypatch):
    """A failure inside the agent must be logged and recorded, never
    propagated (which could stop the scheduler).
    """
    from app.agents import watcher as watcher_module
    from app.services import scheduler

    class BoomAgent:
        def __init__(self, *_a, **_k):
            pass

        def check_for_changes(self, *_a, **_k):
            raise RuntimeError("simulated agent explosion")

    monkeypatch.setattr(watcher_module, "WatcherAgent", BoomAgent)

    scheduler.run_watcher()  # must not raise

    assert "simulated agent explosion" in (
        scheduler._watcher_last_result["error"] or ""
    )
