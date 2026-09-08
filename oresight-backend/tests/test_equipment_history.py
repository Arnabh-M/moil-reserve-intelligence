"""Tests for equipment status history, added in Field Intake Hardening
Phase 4: the append-only audit log, flap detection, and the two history
endpoints.

Hits the real stack and SKIPs when Postgres is unreachable, matching
tests/test_production.py. Every row a test creates is deleted on teardown.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Equipment, EquipmentStatusLog, RiskEvent

SITE_ID = 1


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


@pytest.fixture
def test_equipment():
    """One throwaway equipment row per test, always starting 'up'."""
    db = SessionLocal()
    equipment = Equipment(
        site_id=SITE_ID,
        name="Test Rig PHASE4-1",
        equipment_type="Drill",
        status="up",
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    equipment_id = equipment.id
    db.close()

    yield equipment_id

    db = SessionLocal()
    db.execute(
        delete(RiskEvent).where(
            RiskEvent.source_entity_type == "equipment",
            RiskEvent.source_entity_id == equipment_id,
        )
    )
    db.execute(
        delete(EquipmentStatusLog).where(EquipmentStatusLog.equipment_id == equipment_id)
    )
    db.execute(delete(Equipment).where(Equipment.id == equipment_id))
    db.commit()
    db.close()


def _set_status(client, equipment_id, status, reason=None, source="manual"):
    payload = {"status": status, "reason": reason}
    if source is not None:
        payload["source"] = source
    return client.post(f"/equipment/{equipment_id}/status", json=payload)


def test_status_change_writes_one_log_row(client, test_equipment):
    response = _set_status(client, test_equipment, "down", reason="Hydraulic leak")
    assert response.status_code == 200
    body = response.json()
    assert body["flapping"] is False

    db = SessionLocal()
    rows = (
        db.query(EquipmentStatusLog)
        .filter_by(equipment_id=test_equipment)
        .all()
    )
    db.close()
    assert len(rows) == 1
    assert rows[0].old_status == "up"
    assert rows[0].new_status == "down"
    assert rows[0].reason == "Hydraulic leak"
    assert rows[0].source == "manual"
    assert rows[0].site_id == SITE_ID


def test_source_defaults_to_manual_when_omitted(client, test_equipment):
    response = client.post(
        f"/equipment/{test_equipment}/status", json={"status": "down", "reason": "x"}
    )
    assert response.status_code == 200

    db = SessionLocal()
    row = (
        db.query(EquipmentStatusLog)
        .filter_by(equipment_id=test_equipment)
        .one()
    )
    db.close()
    assert row.source == "manual"


def test_bulk_source_is_recorded(client, test_equipment):
    _set_status(client, test_equipment, "down", reason="Bulk sweep", source="bulk")

    db = SessionLocal()
    row = (
        db.query(EquipmentStatusLog)
        .filter_by(equipment_id=test_equipment)
        .one()
    )
    db.close()
    assert row.source == "bulk"


def test_repeat_down_does_not_duplicate_failure_event(client, test_equipment):
    _set_status(client, test_equipment, "down", reason="first")
    _set_status(client, test_equipment, "down", reason="still down, updated note")

    db = SessionLocal()
    failure_events = (
        db.query(RiskEvent)
        .filter_by(
            source_entity_type="equipment",
            source_entity_id=test_equipment,
            risk_type="equipment_failure",
        )
        .all()
    )
    log_rows = (
        db.query(EquipmentStatusLog).filter_by(equipment_id=test_equipment).all()
    )
    db.close()
    assert len(failure_events) == 1
    # Both status posts still each write their own log row.
    assert len(log_rows) == 2


def test_flap_detection_opens_one_deduped_risk_event(client, test_equipment):
    settings = get_settings()
    # Threshold default is 4 -> need > 4 changes within the window to trip it.
    for i in range(settings.EQUIPMENT_FLAP_THRESHOLD + 1):
        status = "down" if i % 2 == 0 else "up"
        response = _set_status(client, test_equipment, status, reason=f"flap {i}")
        assert response.status_code == 200

    # The change that crossed the threshold should report flapping=True.
    final_response = _set_status(client, test_equipment, "down", reason="tip over")
    assert final_response.json()["flapping"] is True

    db = SessionLocal()
    flap_events = (
        db.query(RiskEvent)
        .filter_by(
            source_entity_type="equipment",
            source_entity_id=test_equipment,
            risk_type="equipment_flapping",
        )
        .all()
    )
    db.close()
    assert len(flap_events) == 1
    assert flap_events[0].severity.value == "medium"
    assert flap_events[0].score == 0.45

    # One more change while still flapping must not open a second event.
    _set_status(client, test_equipment, "up", reason="still flapping")
    db = SessionLocal()
    flap_events_after = (
        db.query(RiskEvent)
        .filter_by(
            source_entity_type="equipment",
            source_entity_id=test_equipment,
            risk_type="equipment_flapping",
        )
        .all()
    )
    db.close()
    assert len(flap_events_after) == 1


def test_equipment_history_endpoint_is_newest_first_and_paginates(client, test_equipment):
    for i in range(3):
        _set_status(client, test_equipment, "down" if i % 2 == 0 else "up", reason=f"h{i}")

    first_page = client.get(f"/equipment/{test_equipment}/history", params={"limit": 2})
    assert first_page.status_code == 200
    body = first_page.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["changed_at"] >= body["items"][1]["changed_at"]
    assert body["next_cursor"] is not None

    second_page = client.get(
        f"/equipment/{test_equipment}/history",
        params={"limit": 2, "before": body["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
    assert second_body["next_cursor"] is None

    seen_ids = {item["id"] for item in body["items"]} | {
        item["id"] for item in second_body["items"]
    }
    assert len(seen_ids) == 3


def test_equipment_history_unknown_id_is_404(client):
    assert client.get("/equipment/99999/history").status_code == 404


def test_site_wide_history_filters_by_site(client, test_equipment):
    _set_status(client, test_equipment, "down", reason="site-wide check")

    matching = client.get("/equipment/history", params={"site_id": SITE_ID, "limit": 500})
    assert matching.status_code == 200
    ids = {row["equipment_id"] for row in matching.json()}
    assert test_equipment in ids

    other_site = client.get("/equipment/history", params={"site_id": 2, "limit": 500})
    assert other_site.status_code == 200
    other_ids = {row["equipment_id"] for row in other_site.json()}
    assert test_equipment not in other_ids


def test_site_wide_history_unknown_site_is_404(client):
    assert client.get("/equipment/history", params={"site_id": 99999}).status_code == 404
