"""Tests for the blast-event endpoints (plan, outcome update, delay summary).

Hits the real stack and SKIPs when Postgres is unreachable, matching
tests/test_site_notes.py. Every blast event a test creates is deleted on
teardown, so the seeded demo data is left untouched.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import BlastEvent

SITE_ID = 1
OTHER_SITE_ID = 2


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
def created_blast_ids():
    ids: list[int] = []
    yield ids
    if ids:
        db = SessionLocal()
        db.execute(delete(BlastEvent).where(BlastEvent.id.in_(ids)))
        db.commit()
        db.close()


def _plan(client, created_blast_ids, **overrides) -> dict:
    payload = {
        "site_id": SITE_ID,
        "planned_date": "2026-09-10",
        "expected_yield_tonnes": 1800.0,
        **overrides,
    }
    response = client.post("/blast-events", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    created_blast_ids.append(body["id"])
    return body


def test_create_defaults_to_planned(client, created_blast_ids):
    body = _plan(client, created_blast_ids, notes="Bench 4 north face.")
    assert body["status"] == "planned"
    assert body["delay_reason"] is None
    assert body["actual_date"] is None
    assert body["actual_yield_tonnes"] is None
    assert body["expected_yield_tonnes"] == 1800.0


def test_create_rejects_unknown_site(client):
    response = client.post(
        "/blast-events",
        json={
            "site_id": 99999,
            "planned_date": "2026-09-10",
            "expected_yield_tonnes": 500.0,
        },
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_patch_to_delayed_without_reason_is_422(client, created_blast_ids):
    blast = _plan(client, created_blast_ids)
    response = client.patch(f"/blast-events/{blast['id']}", json={"status": "delayed"})
    assert response.status_code == 422
    assert "delay_reason" in str(response.json()["detail"])


def test_patch_to_delayed_with_reason_persists(client, created_blast_ids):
    blast = _plan(client, created_blast_ids)
    response = client.patch(
        f"/blast-events/{blast['id']}",
        json={"status": "delayed", "delay_reason": "permit_pending"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "delayed"
    assert response.json()["delay_reason"] == "permit_pending"

    refetched = client.get(f"/blast-events/{blast['id']}").json()
    assert refetched["delay_reason"] == "permit_pending"


def test_patch_to_completed_with_actuals_succeeds(client, created_blast_ids):
    blast = _plan(client, created_blast_ids)
    response = client.patch(
        f"/blast-events/{blast['id']}",
        json={
            "status": "completed",
            "actual_date": "2026-09-11",
            "actual_yield_tonnes": 1725.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["actual_date"] == "2026-09-11"
    assert body["actual_yield_tonnes"] == 1725.5


def test_patch_to_completed_without_yield_is_422(client, created_blast_ids):
    blast = _plan(client, created_blast_ids)
    response = client.patch(
        f"/blast-events/{blast['id']}",
        json={"status": "completed", "actual_date": "2026-09-11"},
    )
    assert response.status_code == 422
    assert "actual_yield_tonnes" in str(response.json()["detail"])


def test_patch_unknown_id_is_404(client):
    response = client.patch("/blast-events/99999", json={"notes": "nope"})
    assert response.status_code == 404


def test_list_filters_by_site_and_status(client, created_blast_ids):
    here = _plan(client, created_blast_ids)
    elsewhere = _plan(client, created_blast_ids, site_id=OTHER_SITE_ID)
    client.patch(
        f"/blast-events/{here['id']}",
        json={"status": "cancelled", "delay_reason": "safety_hold"},
    )

    for_site = client.get("/blast-events", params={"site_id": SITE_ID}).json()
    assert {row["site_id"] for row in for_site} == {SITE_ID}
    assert elsewhere["id"] not in {row["id"] for row in for_site}

    cancelled = client.get(
        "/blast-events", params={"site_id": SITE_ID, "status": "cancelled"}
    ).json()
    assert here["id"] in {row["id"] for row in cancelled}
    assert {row["status"] for row in cancelled} == {"cancelled"}


def test_list_is_ordered_by_planned_date_desc(client, created_blast_ids):
    _plan(client, created_blast_ids, planned_date="2026-09-01")
    _plan(client, created_blast_ids, planned_date="2026-09-20")

    dates = [row["planned_date"] for row in client.get("/blast-events").json()]
    assert dates == sorted(dates, reverse=True)


def test_list_rejects_unknown_status(client):
    assert client.get("/blast-events", params={"status": "exploded"}).status_code == 422


def test_summary_groups_lost_tonnes_and_excludes_planned_and_completed(
    client, created_blast_ids
):
    # Two permit_pending delays: 1000 expected, 400 recovered -> 600 lost.
    partial = _plan(
        client, created_blast_ids, planned_date="2026-09-15", expected_yield_tonnes=1000.0
    )
    client.patch(
        f"/blast-events/{partial['id']}",
        json={
            "status": "delayed",
            "delay_reason": "permit_pending",
            "actual_yield_tonnes": 400.0,
        },
    )
    # A cancellation recovers nothing -> its full 500 is lost.
    cancelled = _plan(
        client, created_blast_ids, planned_date="2026-09-16", expected_yield_tonnes=500.0
    )
    client.patch(
        f"/blast-events/{cancelled['id']}",
        json={"status": "cancelled", "delay_reason": "permit_pending"},
    )
    # Neither of these may contribute: one never came due, one fired fine.
    _plan(client, created_blast_ids, planned_date="2026-09-17", expected_yield_tonnes=9999.0)
    completed = _plan(
        client, created_blast_ids, planned_date="2026-09-18", expected_yield_tonnes=8888.0
    )
    client.patch(
        f"/blast-events/{completed['id']}",
        json={
            "status": "completed",
            "actual_date": "2026-09-18",
            "actual_yield_tonnes": 8000.0,
        },
    )

    rows = client.get(
        "/blast-events/summary",
        params={"site_id": SITE_ID, "from": "2026-09-15", "to": "2026-09-18"},
    ).json()

    by_reason = {row["delay_reason"]: row for row in rows}
    assert set(by_reason) == {"permit_pending"}, "only delayed/cancelled rows aggregate"

    permit = by_reason["permit_pending"]
    assert permit["event_count"] == 2
    assert permit["expected_yield_tonnes"] == 1500.0
    assert permit["actual_yield_tonnes"] == 400.0
    assert permit["tonnes_lost"] == 1100.0


def test_summary_date_range_excludes_outside_events(client, created_blast_ids):
    blast = _plan(
        client, created_blast_ids, planned_date="2026-11-30", expected_yield_tonnes=777.0
    )
    client.patch(
        f"/blast-events/{blast['id']}",
        json={"status": "delayed", "delay_reason": "explosive_supply"},
    )

    inside = client.get(
        "/blast-events/summary",
        params={"site_id": SITE_ID, "from": "2026-11-01", "to": "2026-12-01"},
    ).json()
    assert "explosive_supply" in {row["delay_reason"] for row in inside}

    outside = client.get(
        "/blast-events/summary",
        params={"site_id": SITE_ID, "from": "2026-01-01", "to": "2026-01-31"},
    ).json()
    assert "explosive_supply" not in {row["delay_reason"] for row in outside}


def test_summary_unknown_site_is_404(client):
    assert client.get("/blast-events/summary", params={"site_id": 99999}).status_code == 404
