"""Tests for the bounded-value validation added on top of Field Intake and
the Scenario Simulator (app/constants/validation_limits.py), plus a
regression test for the shared RequestValidationError handler in app/main.py
that every one of these bounds now flows through.

Hits the real stack and SKIPs when Postgres/Neo4j are unreachable, matching
tests/test_production.py and tests/test_blasting.py's convention. Every
record a test creates is deleted on teardown.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.constants.validation_limits import MAX_FREE_TEXT_LENGTH, MAX_TONNES
from app.db import SessionLocal
from app.main import app
from app.models import BlastEvent, Equipment, EquipmentStatus, ProductionRecord

SITE_ID = 1


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


@pytest.fixture
def created_record_ids():
    ids: list[int] = []
    yield ids
    if ids:
        db = SessionLocal()
        db.execute(delete(ProductionRecord).where(ProductionRecord.id.in_(ids)))
        db.commit()
        db.close()


@pytest.fixture
def created_blast_ids():
    ids: list[int] = []
    yield ids
    if ids:
        db = SessionLocal()
        db.execute(delete(BlastEvent).where(BlastEvent.id.in_(ids)))
        db.commit()
        db.close()


def _production_payload(**overrides) -> dict:
    return {
        "site_id": SITE_ID,
        "date": "2027-03-01",
        "shift": "general",
        "actual_output": 900.0,
        "target_output": 1000.0,
        **overrides,
    }


def _blast_payload(**overrides) -> dict:
    return {
        "site_id": SITE_ID,
        "planned_date": "2026-09-15",
        "expected_yield_tonnes": 1800.0,
        **overrides,
    }


# --------------------------------------------------------------------------
# Production tonnage bounds
# --------------------------------------------------------------------------


def test_actual_output_over_max_is_422(client):
    r = client.post("/production", json=_production_payload(date="2027-03-02", actual_output=MAX_TONNES + 1))
    assert r.status_code == 422


def test_actual_output_at_max_is_accepted(client, created_record_ids):
    r = client.post("/production", json=_production_payload(date="2027-03-03", actual_output=MAX_TONNES, target_output=MAX_TONNES))
    assert r.status_code == 201, r.text
    created_record_ids.append(r.json()["id"])
    assert r.json()["actual_output"] == MAX_TONNES


def test_actual_output_still_rejects_negative(client):
    r = client.post("/production", json=_production_payload(date="2027-03-04", actual_output=-1))
    assert r.status_code == 422


def test_target_output_over_max_is_422(client):
    r = client.post("/production", json=_production_payload(date="2027-03-05", target_output=MAX_TONNES + 1))
    assert r.status_code == 422


def test_target_output_at_max_is_accepted(client, created_record_ids):
    r = client.post("/production", json=_production_payload(date="2027-03-06", actual_output=MAX_TONNES, target_output=MAX_TONNES))
    assert r.status_code == 201, r.text
    created_record_ids.append(r.json()["id"])


def test_material_processed_over_max_is_422(client):
    r = client.post("/production", json=_production_payload(date="2027-03-07", material_processed=MAX_TONNES + 1))
    assert r.status_code == 422


def test_material_processed_at_max_is_accepted(client, created_record_ids):
    r = client.post("/production", json=_production_payload(date="2027-03-08", material_processed=MAX_TONNES))
    assert r.status_code == 201, r.text
    created_record_ids.append(r.json()["id"])
    assert r.json()["material_processed"] == MAX_TONNES


def test_production_normal_submission_still_succeeds(client, created_record_ids):
    """Field Intake -> Production: a representative valid submission."""
    r = client.post(
        "/production",
        json=_production_payload(
            date="2027-03-09", actual_output=750.0, target_output=800.0,
            operating_hours=22.0, downtime_hours=2.0, material_processed=760.0, quality_grade=32.5,
        ),
    )
    assert r.status_code == 201, r.text
    created_record_ids.append(r.json()["id"])


# --------------------------------------------------------------------------
# Blast yield bounds
# --------------------------------------------------------------------------


def test_expected_yield_over_max_is_422(client):
    r = client.post("/blast-events", json=_blast_payload(expected_yield_tonnes=MAX_TONNES + 1))
    assert r.status_code == 422


def test_expected_yield_at_max_is_accepted(client, created_blast_ids):
    r = client.post("/blast-events", json=_blast_payload(expected_yield_tonnes=MAX_TONNES))
    assert r.status_code == 201, r.text
    created_blast_ids.append(r.json()["id"])
    assert r.json()["expected_yield_tonnes"] == MAX_TONNES


def test_actual_yield_over_max_is_422(client, created_blast_ids):
    plan = client.post("/blast-events", json=_blast_payload(planned_date="2026-09-16"))
    assert plan.status_code == 201
    created_blast_ids.append(plan.json()["id"])
    r = client.patch(
        f"/blast-events/{plan.json()['id']}",
        json={"status": "completed", "actual_date": "2026-09-16", "actual_yield_tonnes": MAX_TONNES + 1},
    )
    assert r.status_code == 422


def test_actual_yield_at_max_is_accepted(client, created_blast_ids):
    plan = client.post("/blast-events", json=_blast_payload(planned_date="2026-09-17"))
    assert plan.status_code == 201
    created_blast_ids.append(plan.json()["id"])
    r = client.patch(
        f"/blast-events/{plan.json()['id']}",
        json={"status": "completed", "actual_date": "2026-09-17", "actual_yield_tonnes": MAX_TONNES},
    )
    assert r.status_code == 200, r.text
    assert r.json()["actual_yield_tonnes"] == MAX_TONNES


def test_actual_yield_still_rejects_negative(client, created_blast_ids):
    plan = client.post("/blast-events", json=_blast_payload(planned_date="2026-09-18"))
    assert plan.status_code == 201
    created_blast_ids.append(plan.json()["id"])
    r = client.patch(
        f"/blast-events/{plan.json()['id']}",
        json={"status": "completed", "actual_date": "2026-09-18", "actual_yield_tonnes": -1},
    )
    assert r.status_code == 422


def test_blasting_normal_submission_still_succeeds(client, created_blast_ids):
    """Field Intake -> Blasting: a representative valid submission."""
    r = client.post("/blast-events", json=_blast_payload(planned_date="2026-09-19", expected_yield_tonnes=1500.0, notes="Bench 3, twin-row pattern."))
    assert r.status_code == 201, r.text
    created_blast_ids.append(r.json()["id"])


# --------------------------------------------------------------------------
# Equipment status reason length bound
# --------------------------------------------------------------------------


@pytest.fixture
def up_equipment_id():
    db = SessionLocal()
    try:
        equipment = db.query(Equipment).filter(Equipment.status == EquipmentStatus.UP).first()
        return equipment.id
    finally:
        db.close()


def test_equipment_reason_over_max_length_is_422(client, up_equipment_id):
    r = client.post(
        f"/equipment/{up_equipment_id}/status",
        json={"status": "up", "reason": "x" * (MAX_FREE_TEXT_LENGTH + 1)},
    )
    assert r.status_code == 422


def test_equipment_reason_at_max_length_is_accepted(client, up_equipment_id):
    r = client.post(
        f"/equipment/{up_equipment_id}/status",
        json={"status": "up", "reason": "x" * MAX_FREE_TEXT_LENGTH},
    )
    assert r.status_code == 200, r.text


def test_equipment_normal_submission_still_succeeds(client, up_equipment_id):
    """Field Intake -> Equipment: a representative valid submission."""
    r = client.post(f"/equipment/{up_equipment_id}/status", json={"status": "up", "reason": "Routine check, no issues."})
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------------
# Site notes (Field Intake -> Notes) — unchanged, regression only
# --------------------------------------------------------------------------


def test_notes_normal_submission_still_succeeds(client):
    r = client.post("/site-notes", json={"site_id": SITE_ID, "text": "Validation-limits regression check note."})
    assert r.status_code == 201, r.text


# --------------------------------------------------------------------------
# Simulator severity / duration bounds
#
# NOTE ON `lenient_client`: /simulate has a PRE-EXISTING, out-of-scope bug
# (CausalGraphOut validation fails on `edges.3.target` being None) that fires
# on EVERY call that reaches SimulatorAgent.run_scenario() successfully --
# reproduced with a bare {"scenario_type": "equipment_down", "site_id": 1,
# "duration_days": 5} payload carrying no severity/duration field at all, so
# it is provably unrelated to the bounds added in this task. Confirmed
# present on the pre-task baseline too (test_graph_and_agents.py's
# test_simulate_supported_scenarios was already failing there).
#
# The default `client` fixture's TestClient re-raises server-side exceptions
# (raise_server_exceptions=True), which would surface that unrelated bug as
# a raw pydantic ValidationError instead of a normal response. `lenient_client`
# disables that so these tests can assert what they actually own -- that a
# valid boundary value is never rejected at the 422 validation layer --
# without either masking or attempting to fix the unrelated pre-existing bug.
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lenient_client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_simulate_severity_over_max_is_422(client):
    r = client.post("/simulate", json={"scenario_type": "rainfall_event", "site_id": SITE_ID, "duration_days": 5, "severity": 101})
    assert r.status_code == 422


def test_simulate_severity_negative_is_422(client):
    r = client.post("/simulate", json={"scenario_type": "rainfall_event", "site_id": SITE_ID, "duration_days": 5, "severity": -1})
    assert r.status_code == 422


def test_simulate_severity_at_max_is_not_rejected_by_validation(lenient_client):
    r = lenient_client.post("/simulate", json={"scenario_type": "rainfall_event", "site_id": SITE_ID, "duration_days": 5, "severity": 100})
    assert r.status_code != 422, r.text


def test_simulate_condition_duration_over_max_is_422(client):
    r = client.post(
        "/simulate",
        json={
            "scenario_type": "equipment_down", "site_id": SITE_ID, "duration_days": 5,
            "conditions": [{"type": "equipment_down", "severity": 2.0, "duration": 366}],
        },
    )
    assert r.status_code == 422


def test_simulate_condition_duration_at_max_is_not_rejected_by_validation(lenient_client):
    r = lenient_client.post(
        "/simulate",
        json={
            "scenario_type": "equipment_down", "site_id": SITE_ID, "duration_days": 5,
            "conditions": [{"type": "equipment_down", "severity": 2.0, "duration": 365}],
        },
    )
    assert r.status_code != 422, r.text


def test_simulate_duration_days_bound_is_unchanged(client, lenient_client):
    """Regression: SimulateRequest.duration_days must stay at its existing
    1-90 bound — this task deliberately does not widen it (see discovery).
    90 must not be rejected by validation (the pre-existing /simulate bug,
    unrelated to this bound, may still keep it from reaching 200 -- see the
    module note above); 91 must still be a clean 422.
    """
    assert lenient_client.post("/simulate", json={"scenario_type": "equipment_down", "site_id": SITE_ID, "duration_days": 90}).status_code != 422
    assert client.post("/simulate", json={"scenario_type": "equipment_down", "site_id": SITE_ID, "duration_days": 91}).status_code == 422


def test_simulate_normal_run_is_not_rejected_by_validation_and_has_same_shape_if_it_completes(lenient_client):
    """A valid Scenario Simulator run must never be rejected by request
    validation (422). If it completes (200), it must return the pre-existing
    response shape unchanged. It may also hit the pre-existing, out-of-scope
    /simulate bug (see the module note above) and come back as a 500 --
    that outcome is accepted here rather than masked, since fixing it is out
    of scope and reproducibly unrelated to this task's bounds.
    """
    r = lenient_client.post("/simulate", json={"scenario_type": "equipment_down", "site_id": SITE_ID, "duration_days": 5})
    assert r.status_code != 422, r.text
    if r.status_code == 200:
        body = r.json()
        assert set(body) >= {"before", "after", "affected_graph_path", "updated_graph"}
        for snap in (body["before"], body["after"]):
            assert set(snap) == {"reserve_confidence", "production_forecast_tonnes", "risk_score"}


# --------------------------------------------------------------------------
# Regression guard: existing GET endpoints still 200 with seeded data intact
# --------------------------------------------------------------------------


def test_get_endpoints_unaffected_by_new_bounds(client):
    for path in (
        f"/production?site_id={SITE_ID}",
        f"/blast-events?site_id={SITE_ID}",
        f"/equipment?site_id={SITE_ID}",
    ):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text}"
        assert isinstance(r.json(), list)


def test_root_endpoint():
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert r.json() == {"service": "OreSight API", "status": "ok", "docs": "/docs"}


# --------------------------------------------------------------------------
# RequestValidationError handler regression (shared infrastructure — highest
# blast radius of any change in this task)
# --------------------------------------------------------------------------


def test_validation_error_shape_is_unchanged(client):
    r = client.post("/production", json=_production_payload(date="2027-03-10", actual_output=MAX_TONNES + 1))
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"detail", "error_code"}
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"], list)
    assert all(isinstance(item, str) for item in body["detail"])


def test_validation_error_message_is_readable_and_names_field_value_and_bound(client):
    r = client.post("/production", json=_production_payload(date="2027-03-11", actual_output=200_000))
    assert r.status_code == 422
    detail = r.json()["detail"]
    joined = " ".join(detail)
    assert "actual_output" in joined
    assert "200000" in joined or "200000.0" in joined
    assert str(MAX_TONNES) in joined


def test_pre_existing_bound_still_produces_same_shape_only_message_improved(client):
    """quality_grade (0-100) already existed before this task and already hit
    this same handler — its shape must be unaffected by the handler change.
    """
    r = client.post("/production", json=_production_payload(date="2027-03-12", quality_grade=150))
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"detail", "error_code"}
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"], list)
    assert any("quality_grade" in item for item in body["detail"])
