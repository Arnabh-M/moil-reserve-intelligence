"""Tests for the production-record endpoints, extended in Field Intake
Hardening Phase 1: shift-scoped uniqueness, the extended field set, server-
side variance classification, and the PATCH edit window + audit log.

Hits the real stack and SKIPs when Postgres is unreachable, matching
tests/test_blasting.py. Every record a test creates is deleted on teardown.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text, update
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import ProductionRecord, ProductionRecordAudit

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
def created_record_ids():
    ids: list[int] = []
    yield ids
    if ids:
        db = SessionLocal()
        db.execute(
            delete(ProductionRecordAudit).where(ProductionRecordAudit.record_id.in_(ids))
        )
        db.execute(delete(ProductionRecord).where(ProductionRecord.id.in_(ids)))
        db.commit()
        db.close()


def _create(client, created_record_ids, **overrides) -> dict:
    payload = {
        "site_id": SITE_ID,
        "date": "2027-01-01",
        "shift": "general",
        "actual_output": 900.0,
        "target_output": 1000.0,
        **overrides,
    }
    response = client.post("/production", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    created_record_ids.append(body["id"])
    return body


def test_shortfall_reasons_and_thresholds_are_served():
    with TestClient(app) as c:
        reasons = c.get("/production/shortfall-reasons").json()
        assert {r["value"] for r in reasons} == {
            "equipment_failure", "maintenance", "weather", "material_availability",
            "labour_shortage", "geological_conditions", "safety_stoppage", "other",
        }
        thresholds = c.get("/production/thresholds").json()
        assert thresholds == {"on_target_min_pct": -3.0, "slightly_below_min_pct": -12.0}


def test_create_persists_all_fields_and_computes_variance_class(client, created_record_ids):
    body = _create(
        client, created_record_ids,
        actual_output=700.0, target_output=1000.0,
        operating_hours=11.5, downtime_hours=1.0,
        material_processed=730.0, quality_grade=31.2,
        shortfall_reasons=["equipment_failure"],
    )
    assert body["variance_class"] == "significantly_below"
    assert body["operating_hours"] == 11.5
    assert body["downtime_hours"] == 1.0
    assert body["material_processed"] == 730.0
    assert body["quality_grade"] == 31.2
    assert body["shortfall_reasons"] == ["equipment_failure"]
    assert body["created_by"] == "system"
    assert body["updated_at"] is None


def test_same_site_date_different_shift_both_save(client, created_record_ids):
    day = _create(client, created_record_ids, date="2027-01-02", shift="day")
    night = _create(client, created_record_ids, date="2027-01-02", shift="night")
    assert day["id"] != night["id"]


def test_same_site_date_shift_is_409(client, created_record_ids):
    _create(client, created_record_ids, date="2027-01-03", shift="day")
    response = client.post(
        "/production",
        json={"site_id": SITE_ID, "date": "2027-01-03", "shift": "day", "actual_output": 1, "target_output": 1},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CONFLICT"


def test_operating_plus_downtime_over_24_is_422(client):
    response = client.post(
        "/production",
        json={
            "site_id": SITE_ID, "date": "2027-01-04", "shift": "general",
            "actual_output": 700, "target_output": 1000,
            "operating_hours": 20, "downtime_hours": 10,
        },
    )
    assert response.status_code == 422


def test_significantly_below_without_reasons_is_422(client):
    response = client.post(
        "/production",
        json={"site_id": SITE_ID, "date": "2027-01-05", "shift": "general", "actual_output": 500, "target_output": 1000},
    )
    assert response.status_code == 422
    assert "shortfall_reasons" in str(response.json()["detail"])


def test_other_reason_without_note_is_422(client):
    response = client.post(
        "/production",
        json={
            "site_id": SITE_ID, "date": "2027-01-06", "shift": "general",
            "actual_output": 500, "target_output": 1000, "shortfall_reasons": ["other"],
        },
    )
    assert response.status_code == 422


def test_patch_updates_field_and_writes_audit_row(client, created_record_ids):
    record = _create(client, created_record_ids, date="2027-01-07", shift="general")
    response = client.patch(f"/production/{record['id']}", json={"actual_output": 950.0, "quality_grade": 33.0})
    assert response.status_code == 200
    body = response.json()
    assert body["actual_output"] == 950.0
    assert body["quality_grade"] == 33.0
    assert body["updated_by"] == "system"
    assert body["updated_at"] is not None

    db = SessionLocal()
    rows = db.query(ProductionRecordAudit).filter_by(record_id=record["id"]).all()
    db.close()
    fields_changed = {r.field for r in rows}
    assert fields_changed == {"actual_output", "quality_grade"}
    actual_row = next(r for r in rows if r.field == "actual_output")
    assert actual_row.old_value == "900.0"
    assert actual_row.new_value == "950.0"


def test_patch_unknown_id_is_404(client):
    assert client.patch("/production/99999", json={"actual_output": 1}).status_code == 404


def test_patch_outside_edit_window_is_403(client, created_record_ids):
    record = _create(client, created_record_ids, date="2027-01-08", shift="general")
    settings = get_settings()

    db = SessionLocal()
    stale = datetime.now(timezone.utc) - timedelta(hours=settings.PRODUCTION_EDIT_WINDOW_HOURS + 1)
    db.execute(
        update(ProductionRecord).where(ProductionRecord.id == record["id"]).values(created_at=stale)
    )
    db.commit()
    db.close()

    response = client.patch(f"/production/{record['id']}", json={"actual_output": 1.0})
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_patch_transitioning_into_significantly_below_requires_reason(client, created_record_ids):
    record = _create(client, created_record_ids, date="2027-01-09", shift="general", actual_output=990.0, target_output=1000.0)
    response = client.patch(f"/production/{record['id']}", json={"actual_output": 500.0})
    assert response.status_code == 422
