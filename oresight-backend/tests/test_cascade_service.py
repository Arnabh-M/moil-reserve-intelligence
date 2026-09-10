"""Tests for the cascade/ripple-impact feature.

Split into two groups:

- Unit tests (top of file) use a FakeDriver/FakeSession — no live Postgres
  or Neo4j required, always run. These cover compute_cascade's failure
  contract, hop cap, classification, and severity rules directly.
- Integration tests (bottom of file) run against the real seeded stack,
  following this repo's existing convention (see test_graph_and_agents.py):
  SKIP rather than fail when infra isn't reachable.
"""

from __future__ import annotations

from neo4j.exceptions import ServiceUnavailable

from app.services.cascade_service import (
    _cascade_severity,
    _classify_impacted,
    compute_cascade,
)

# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def single(self):
        return self._rows[0] if self._rows else None

    def data(self):
        return self._rows


class FakeSession:
    """Returns one canned response per call to `.run()`, in order, regardless
    of the query text — the call sequence in cascade_service is fixed
    (target lookup, then up to max_hops BFS calls, then an optional
    date-conflict check), so tests just queue up responses for that sequence.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def run(self, query, **params):
        self.calls += 1
        if not self._responses:
            return FakeResult([])
        return FakeResult(self._responses.pop(0))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeDriver:
    def __init__(self, responses=None, raise_on_session=None):
        self._responses = responses or []
        self._raise = raise_on_session
        self.last_session: FakeSession | None = None

    def session(self):
        if self._raise is not None:
            raise self._raise
        self.last_session = FakeSession(self._responses)
        return self.last_session


def _target_row(entity_id="bp_nag_01", label="BlastPlan", site_id="nagpur", scheduled_date="2026-09-02", status=None):
    return {
        "id": entity_id, "label": label, "name": entity_id,
        "site_id": site_id, "scheduled_date": scheduled_date, "status": status,
    }


# --------------------------------------------------------------------------
# 1. Neo4j unreachable -> None, never raises
# --------------------------------------------------------------------------


def test_compute_cascade_returns_none_when_neo4j_unreachable():
    driver = FakeDriver(raise_on_session=ServiceUnavailable("Neo4j down"))
    result = compute_cascade(
        action_type="reschedule_plan", target_entity_id="bp_nag_01",
        proposed_change={"new_date": "2026-09-10"}, site_id=2, driver=driver,
    )
    assert result is None


# --------------------------------------------------------------------------
# 2. Target entity not found -> None
# --------------------------------------------------------------------------


def test_compute_cascade_returns_none_when_target_missing():
    driver = FakeDriver(responses=[[]])  # target lookup returns no row
    result = compute_cascade(
        action_type="reschedule_plan", target_entity_id="does_not_exist",
        proposed_change={}, site_id=2, driver=driver,
    )
    assert result is None


def test_compute_cascade_returns_none_for_unknown_action_type():
    driver = FakeDriver(responses=[[_target_row()]])
    result = compute_cascade(
        action_type="teleport_the_mine", target_entity_id="bp_nag_01",
        proposed_change={}, site_id=2, driver=driver,
    )
    assert result is None


# --------------------------------------------------------------------------
# 3. Hop cap enforced
# --------------------------------------------------------------------------


def test_compute_cascade_respects_hop_cap():
    responses = [
        [_target_row()],  # target lookup
        [{"start_id": "bp_nag_01", "id": "oz_nag_01", "label": "OreZone", "name": "Zone A", "edge_type": "AFFECTS", "status": None}],  # hop 1
        [{"start_id": "oz_nag_01", "id": "re_far", "label": "RiskEvent", "name": "Far risk", "edge_type": "CORRELATES_WITH", "status": None}],  # hop 2
    ]
    driver = FakeDriver(responses=responses)
    result = compute_cascade(
        action_type="redeploy_equipment", target_entity_id="bp_nag_01",
        proposed_change={}, site_id=2, max_hops=2, driver=driver,
    )
    assert result is not None
    ids = {e.entity_id for e in result.impacted}
    assert ids == {"oz_nag_01", "re_far"}
    assert max(e.hops for e in result.impacted) == 2
    # exactly 3 session.run calls: target lookup + 2 BFS hops, no 3rd hop attempted
    assert driver.last_session.calls == 3


def test_compute_cascade_clamps_max_hops_above_the_hard_cap():
    responses = [[_target_row()], [], [], []]
    driver = FakeDriver(responses=responses)
    result = compute_cascade(
        action_type="redeploy_equipment", target_entity_id="bp_nag_01",
        proposed_change={}, site_id=2, max_hops=99, driver=driver,
    )
    assert result is not None
    # target lookup + at most MAX_HOP_CAP (3) BFS calls, not 99
    assert driver.last_session.calls <= 4


# --------------------------------------------------------------------------
# 4. Blocking classification on date collision
# --------------------------------------------------------------------------


def test_compute_cascade_blocking_on_date_collision():
    responses = [
        [_target_row()],  # target lookup
        [],  # hop 1 BFS (empty -> BFS stops here, no hop 2 call is made)
        [{"id": "bp_nag_02"}],  # date conflict check
    ]
    driver = FakeDriver(responses=responses)
    result = compute_cascade(
        action_type="reschedule_plan", target_entity_id="bp_nag_01",
        proposed_change={"new_date": "2026-09-10"}, site_id=2, projected_impact=53.4, driver=driver,
    )
    assert result is not None
    assert result.blocking_count == 1
    assert result.cascade_severity == "high"
    conflict = next(e for e in result.impacted if e.entity_id == "bp_nag_02")
    assert conflict.classification == "blocking"
    assert "2026-09-10" in conflict.detail
    assert result.cascade_adjusted_impact == round(53.4 * 0.60, 1)


# --------------------------------------------------------------------------
# 5. cascade_severity is "high" whenever blocking_count >= 1
# --------------------------------------------------------------------------


def test_cascade_severity_high_whenever_blocking_present():
    assert _cascade_severity(blocking_count=1, entities_affected=0) == "high"
    assert _cascade_severity(blocking_count=1, entities_affected=50) == "high"
    assert _cascade_severity(blocking_count=3, entities_affected=1) == "high"


def test_cascade_severity_other_thresholds():
    assert _cascade_severity(0, 0) == "none"
    assert _cascade_severity(0, 2) == "low"
    assert _cascade_severity(0, 3) == "moderate"


def test_classify_impacted_marks_down_equipment_as_blocking():
    records = [
        {"id": "eq_nag_02", "label": "Equipment", "name": "Drill NAG-1", "status": "down", "hops": 1, "path": ["DEPENDS_ON"]},
        {"id": "oz_nag_01", "label": "OreZone", "name": "Zone A", "status": None, "hops": 1, "path": ["AFFECTS"]},
        {"id": "re_x", "label": "RiskEvent", "name": "Some risk", "status": None, "hops": 2, "path": ["AFFECTS", "CORRELATES_WITH"]},
    ]
    classified = _classify_impacted(records)
    by_id = {e.entity_id: e for e in classified}
    assert by_id["eq_nag_02"].classification == "blocking"
    assert by_id["oz_nag_01"].classification == "shifted"
    assert by_id["re_x"].classification == "downstream"


# --------------------------------------------------------------------------
# Integration tests — real stack, skip if unreachable
# --------------------------------------------------------------------------

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from neo4j.exceptions import Neo4jError  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.graph_db import init_graph_driver  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Equipment, EquipmentStatus, RiskEvent  # noqa: E402


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 3})
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
    if not (_postgres_reachable() and _neo4j_reachable()):
        pytest.skip("needs both Postgres and Neo4j")

    from datetime import datetime, timedelta, timezone

    from app.agents.watcher import WatcherAgent

    db = SessionLocal()
    driver = init_graph_driver()
    risk_event_id = None
    equipment_id = None
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
        equipment.status_reason = "cascade test — transient"
        db.commit()

        created = WatcherAgent(db, driver).check_for_changes(
            since=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        risk_event_id = next(
            c["id"] for c in created
            if c["site_id"] == equipment.site_id and c["risk_type"] == "equipment_failure"
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
                session.run("MATCH (r:RiskEvent {external_ref: $ref}) DETACH DELETE r", ref=str(risk_event_id))
        db.close()


def test_recommendations_response_has_optional_cascade_field(client, linked_risk_event):
    r = client.get(f"/recommendations?risk_event_id={linked_risk_event}")
    assert r.status_code == 200
    body = r.json()
    for rec in body:
        for option in rec["options"]:
            assert "cascade" in option  # additive field always present (possibly null)


def test_projected_impact_unchanged_when_cascade_computation_fails(client, linked_risk_event, monkeypatch):
    """Regression guard: cascade computation must never change the existing
    projected_impact/confidence/type/description numbers, even when it fails.
    """
    baseline = client.get(f"/recommendations?risk_event_id={linked_risk_event}").json()

    import app.agents.planner as planner_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated cascade failure")

    monkeypatch.setattr(planner_module, "compute_cascade", _boom)

    after = client.get(f"/recommendations?risk_event_id={linked_risk_event}").json()

    assert len(baseline) == len(after)
    for base_rec, after_rec in zip(baseline, after):
        assert len(base_rec["options"]) == len(after_rec["options"])
        for base_opt, after_opt in zip(base_rec["options"], after_rec["options"]):
            assert base_opt["type"] == after_opt["type"]
            assert base_opt["description"] == after_opt["description"]
            assert base_opt["projected_impact"] == after_opt["projected_impact"]
            assert base_opt["confidence"] == after_opt["confidence"]
            assert after_opt["cascade"] is None


def test_derive_dependency_edges_is_idempotent():
    if not _neo4j_reachable():
        pytest.skip("Neo4j not reachable")
    from app.services.dependency_derivation import derive_dependency_edges

    first = derive_dependency_edges()
    second = derive_dependency_edges()

    first_scheduled = next(r for r in first.edge_reports if r.edge_type == "SCHEDULED_ON")
    second_scheduled = next(r for r in second.edge_reports if r.edge_type == "SCHEDULED_ON")
    assert not first_scheduled.skipped
    assert first_scheduled.total_edges == second_scheduled.total_edges


def test_derive_dependency_edges_reports_skipped_edge_types():
    if not _neo4j_reachable():
        pytest.skip("Neo4j not reachable")
    from app.services.dependency_derivation import derive_dependency_edges

    report = derive_dependency_edges()
    skipped_types = {r.edge_type for r in report.skipped}
    assert "TARGETS" in skipped_types
    assert "COMMITTED_TO" in skipped_types
    for r in report.skipped:
        assert r.skip_reason
