"""Tests for equipment performance metrics (Task 6, backend): downtime
interval reconstruction, availability/MTBF/MTTR arithmetic, maintenance-due
status, the backfill script, and the two /equipment/metrics endpoints.

Split like tests/test_cascade_service.py:
- Pure-function tests (top) use no database — plain _StatusEvent /
  _DowntimeInterval objects in, dicts out. Always run.
- Integration tests (bottom) hit the real stack, following
  tests/test_equipment_history.py's convention: SKIP rather than fail when
  Postgres is unreachable. Every row a test creates is deleted on teardown,
  except the backfill-script tests, which operate on the real seeded
  equipment roster (that's what the backfill script is for) and only ever
  touch source="downtime_log_import" rows, which are safe to
  delete-and-reinsert by design.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

import scripts.backfill_equipment_status_log as backfill_script
from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Equipment, EquipmentStatusLog, RiskEvent
from app.services import equipment_metrics

UTC = timezone.utc
SITE_ID = 1

# --------------------------------------------------------------------------
# Pure-function tests
# --------------------------------------------------------------------------


def _ev(hour: float, status: str, reason: str | None = None, source: str = "manual"):
    return equipment_metrics._StatusEvent(
        changed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        new_status=status,
        reason=reason,
        source=source,
    )


def _interval(start_hour: float, hours: float, category: str, reason: str | None = "x"):
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=start_hour)
    end = start + timedelta(hours=hours)
    return equipment_metrics._DowntimeInterval(
        start=start, end=end, reason=reason, source="manual", open=False, category=category
    )


class TestBuildDowntimeIntervals:
    def test_pairs_down_with_next_up(self):
        events = [_ev(0, "down", "electrical fault"), _ev(2, "up")]
        intervals, warnings = equipment_metrics._build_downtime_intervals(
            events, window_end=datetime(2026, 1, 2, tzinfo=UTC), now=datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert warnings == []
        assert len(intervals) == 1
        assert intervals[0].start == datetime(2026, 1, 1, 0, tzinfo=UTC)
        assert intervals[0].end == datetime(2026, 1, 1, 2, tzinfo=UTC)
        assert intervals[0].open is False
        assert intervals[0].category == "failure"

    def test_trailing_down_with_no_up_is_open_capped_at_now(self):
        events = [_ev(0, "down", "mechanical failure")]
        now = datetime(2026, 1, 1, 10, tzinfo=UTC)
        window_end = datetime(2026, 1, 5, tzinfo=UTC)
        intervals, _ = equipment_metrics._build_downtime_intervals(events, window_end=window_end, now=now)
        assert len(intervals) == 1
        assert intervals[0].open is True
        assert intervals[0].end == now  # now < window_end -> capped at now

    def test_trailing_down_capped_at_window_end_when_earlier_than_now(self):
        events = [_ev(0, "down", "mechanical failure")]
        now = datetime(2026, 1, 5, tzinfo=UTC)
        window_end = datetime(2026, 1, 2, tzinfo=UTC)
        intervals, _ = equipment_metrics._build_downtime_intervals(events, window_end=window_end, now=now)
        assert len(intervals) == 1
        assert intervals[0].open is True
        assert intervals[0].end == window_end

    def test_duplicate_consecutive_status_is_skipped_and_logged(self):
        events = [
            _ev(0, "down", "electrical fault"),
            _ev(1, "down", "electrical fault (still down)"),  # duplicate -> skipped
            _ev(3, "up"),
        ]
        intervals, warnings = equipment_metrics._build_downtime_intervals(
            events, window_end=datetime(2026, 1, 2, tzinfo=UTC), now=datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert len(intervals) == 1
        # The original down_start/reason survive the duplicate, unaffected.
        assert intervals[0].start == datetime(2026, 1, 1, 0, tzinfo=UTC)
        assert intervals[0].end == datetime(2026, 1, 1, 3, tzinfo=UTC)
        assert intervals[0].reason == "electrical fault"
        assert len(warnings) == 1
        assert "duplicate consecutive" in warnings[0]

    def test_leading_up_with_no_prior_down_creates_no_interval(self):
        events = [_ev(0, "up")]
        intervals, warnings = equipment_metrics._build_downtime_intervals(
            events, window_end=datetime(2026, 1, 2, tzinfo=UTC), now=datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert intervals == []
        assert warnings == []

    def test_events_need_not_be_pre_sorted(self):
        events = [_ev(2, "up"), _ev(0, "down", "hydraulic leak")]
        intervals, _ = equipment_metrics._build_downtime_intervals(
            events, window_end=datetime(2026, 1, 2, tzinfo=UTC), now=datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert len(intervals) == 1
        assert intervals[0].start == datetime(2026, 1, 1, 0, tzinfo=UTC)


class TestClipping:
    def test_clip_partial_overlap_both_sides(self):
        interval = _interval(0, 240, "failure")  # day 0 -> day 10
        clipped = equipment_metrics._clip_interval(
            interval, datetime(2026, 1, 3, tzinfo=UTC), datetime(2026, 1, 5, tzinfo=UTC)
        )
        assert clipped.start == datetime(2026, 1, 3, tzinfo=UTC)
        assert clipped.end == datetime(2026, 1, 5, tzinfo=UTC)

    def test_clip_no_overlap_returns_none(self):
        interval = _interval(0, 24, "failure")
        clipped = equipment_metrics._clip_interval(
            interval, datetime(2026, 1, 5, tzinfo=UTC), datetime(2026, 1, 6, tzinfo=UTC)
        )
        assert clipped is None

    def test_clip_interval_fully_inside_window_is_unchanged(self):
        interval = _interval(24, 2, "failure")
        clipped = equipment_metrics._clip_interval(
            interval, datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 10, tzinfo=UTC)
        )
        assert clipped.start == interval.start
        assert clipped.end == interval.end


class TestCategorizeReason:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("Scheduled Maintenance", "planned_maintenance"),
            ("scheduled maintenance", "planned_maintenance"),
            ("electrical fault", "failure"),
            ("hydraulic leak", "failure"),
            ("mechanical failure", "failure"),
            ("spare parts unavailable", "spare_parts_wait"),
            ("operator shift gap", "operational"),
            ("weather delay", "weather"),
        ],
    )
    def test_exact_matches(self, reason, expected):
        assert equipment_metrics._categorize_reason(reason) == expected

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("Needs PM before next shift", "planned_maintenance"),
            ("Routine service today", "planned_maintenance"),
            ("Hydraulic hose burst", "failure"),
            ("Conveyor belt seized", "failure"),
            ("Waiting on spare parts from vendor", "spare_parts_wait"),
            ("Operator crew short-staffed", "operational"),
            ("Heavy rain flooded access road", "weather"),
        ],
    )
    def test_keyword_rules(self, reason, expected):
        assert equipment_metrics._categorize_reason(reason) == expected

    def test_unrecognized_reason_and_none_fall_to_other(self):
        assert equipment_metrics._categorize_reason("unexplained anomaly") == "other"
        assert equipment_metrics._categorize_reason(None) == "other"
        assert equipment_metrics._categorize_reason("") == "other"


class TestWindowMetrics:
    def test_physical_vs_overall_availability_hand_worked(self):
        # 10-day window = 240 hours.
        #   planned_maintenance 6h, failure 4h, spare_parts_wait 2h,
        #   weather 8h, operational 3h  ->  total downtime = 23h
        # physical deduction = planned_maintenance + failure + spare_parts_wait
        #                     = 6 + 4 + 2 = 12h
        # physical_availability = (240 - 12) / 240 * 100 = 228/240*100 = 95.0
        # overall_availability  = (240 - 23) / 240 * 100 = 217/240*100 = 90.41666... -> 90.4
        # (weather + operational reduce overall but NOT physical availability —
        # the machine itself wasn't broken, it was externally blocked.)
        window_hours = 240.0
        intervals = [
            _interval(0, 6, "planned_maintenance", "scheduled maintenance"),
            _interval(10, 4, "failure", "electrical fault"),
            _interval(20, 2, "spare_parts_wait", "spare parts unavailable"),
            _interval(30, 8, "weather", "weather delay"),
            _interval(50, 3, "operational", "operator shift gap"),
        ]
        result = equipment_metrics._compute_window_metrics(intervals, window_hours)
        assert result["downtime_hours"] == 23.0
        assert result["physical_availability_pct"] == 95.0
        assert result["overall_availability_pct"] == 90.4

    def test_zero_failures_gives_null_mtbf_and_mttr(self):
        result = equipment_metrics._compute_window_metrics([], 240.0)
        assert result["failures"] == 0
        assert result["mtbf_hours"] is None
        assert result["mttr_hours"] is None

    def test_mtbf_and_mttr_hand_worked(self):
        # 240h window, two failure intervals: 4h and 6h (10h total failure time).
        # uptime = 240 - 10 = 230
        # mtbf = uptime / failures = 230 / 2 = 115.0
        # mttr = failure_hours / failures = 10 / 2 = 5.0
        intervals = [
            _interval(0, 4, "failure", "mechanical failure"),
            _interval(20, 6, "failure", "mechanical failure"),
        ]
        result = equipment_metrics._compute_window_metrics(intervals, 240.0)
        assert result["failures"] == 2
        assert result["mtbf_hours"] == 115.0
        assert result["mttr_hours"] == 5.0

    def test_top_failure_reason_by_count_then_hours_then_alpha(self):
        intervals = [
            _interval(0, 1, "failure", "hydraulic leak"),
            _interval(5, 1, "failure", "hydraulic leak"),
            _interval(10, 5, "failure", "mechanical failure"),  # more hours, fewer occurrences
        ]
        result = equipment_metrics._compute_window_metrics(intervals, 240.0)
        assert result["top_failure_reason"] == "hydraulic leak"

    def test_empty_window_defaults_to_full_availability(self):
        result = equipment_metrics._compute_window_metrics([], 0.0)
        assert result["physical_availability_pct"] == 100.0
        assert result["overall_availability_pct"] == 100.0


class TestMaintenanceStatus:
    @staticmethod
    def _maint(end_dt: datetime):
        return equipment_metrics._DowntimeInterval(
            start=end_dt - timedelta(hours=2),
            end=end_dt,
            reason="scheduled maintenance",
            source="manual",
            open=False,
            category="planned_maintenance",
        )

    def test_unknown_when_no_maintenance_record(self):
        result = equipment_metrics._compute_maintenance_status([], as_of=datetime(2026, 1, 1, tzinfo=UTC))
        assert result["maintenance_status"] == "unknown"
        assert result["last_maintenance_at"] is None
        assert result["next_maintenance_due"] is None
        assert result["days_since_last_maintenance"] is None

    def test_uses_latest_maintenance_end_regardless_of_list_order(self):
        early = self._maint(datetime(2026, 1, 1, tzinfo=UTC))
        late = self._maint(datetime(2026, 2, 1, tzinfo=UTC))
        result = equipment_metrics._compute_maintenance_status(
            [early, late], as_of=datetime(2026, 2, 2, tzinfo=UTC)
        )
        assert result["last_maintenance_at"] == datetime(2026, 2, 1, tzinfo=UTC)

    def test_maintenance_after_as_of_is_ignored(self):
        future = self._maint(datetime(2026, 3, 1, tzinfo=UTC))
        result = equipment_metrics._compute_maintenance_status(
            [future], as_of=datetime(2026, 2, 1, tzinfo=UTC)
        )
        assert result["maintenance_status"] == "unknown"

    def test_status_thresholds_ok_due_soon_overdue(self):
        last = datetime(2026, 1, 1, tzinfo=UTC)
        intervals = [self._maint(last)]
        interval_days = equipment_metrics.MAINTENANCE_INTERVAL_DAYS
        due_soon_days = equipment_metrics.DUE_SOON_DAYS
        next_due = last.date() + timedelta(days=interval_days)

        as_of_ok = datetime.combine(next_due - timedelta(days=due_soon_days + 1), datetime.min.time(), tzinfo=UTC)
        result_ok = equipment_metrics._compute_maintenance_status(intervals, as_of=as_of_ok)
        assert result_ok["maintenance_status"] == "ok"
        assert result_ok["next_maintenance_due"] == next_due

        as_of_due_soon = datetime.combine(next_due - timedelta(days=due_soon_days), datetime.min.time(), tzinfo=UTC)
        result_due_soon = equipment_metrics._compute_maintenance_status(intervals, as_of=as_of_due_soon)
        assert result_due_soon["maintenance_status"] == "due_soon"

        as_of_overdue = datetime.combine(next_due + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        result_overdue = equipment_metrics._compute_maintenance_status(intervals, as_of=as_of_overdue)
        assert result_overdue["maintenance_status"] == "overdue"


class TestFleetAggregation:
    def test_fleet_totals_sum_hours_not_average_percentages(self):
        # Machine A: 10h failure downtime out of 100h window (90% physical avail).
        # Machine B: 0h downtime (100% physical avail).
        # A naive average of percentages would give (90+100)/2 = 95.0, which
        # happens to match the hour-based answer here only by coincidence of
        # round numbers — the real assertion is that fleet totals are
        # computed from SUMMED hours (200h fleet window, 10h downtime), not
        # from averaging each machine's percentage.
        machine_a = {
            "downtime_hours_by_category": {
                "planned_maintenance": 0.0, "failure": 10.0, "spare_parts_wait": 0.0,
                "operational": 0.0, "weather": 0.0, "other": 0.0,
            },
            "failures": 2,
            "maintenance_status": "ok",
        }
        machine_b = {
            "downtime_hours_by_category": {
                "planned_maintenance": 0.0, "failure": 0.0, "spare_parts_wait": 0.0,
                "operational": 0.0, "weather": 0.0, "other": 0.0,
            },
            "failures": 0,
            "maintenance_status": "overdue",
        }
        fleet = equipment_metrics._aggregate_fleet([machine_a, machine_b], site_id=1, window_hours=100.0)

        assert fleet["equipment_count"] == 2
        assert fleet["failures"] == 2
        assert fleet["maintenance_overdue_count"] == 1
        assert fleet["maintenance_due_soon_count"] == 0
        # fleet_window_hours = 100 * 2 = 200; downtime = 10; deduction = 10 (failure)
        assert fleet["physical_availability_pct"] == round((200 - 10) / 200 * 100, 1)
        assert fleet["overall_availability_pct"] == round((200 - 10) / 200 * 100, 1)
        assert fleet["mtbf_hours"] == round((200 - 10) / 2, 2)
        assert fleet["mttr_hours"] == round(10 / 2, 2)

    def test_empty_fleet_defaults_to_full_availability_and_no_failures(self):
        fleet = equipment_metrics._aggregate_fleet([], site_id=1, window_hours=240.0)
        assert fleet["equipment_count"] == 0
        assert fleet["physical_availability_pct"] == 100.0
        assert fleet["overall_availability_pct"] == 100.0
        assert fleet["failures"] == 0
        assert fleet["mtbf_hours"] is None
        assert fleet["mttr_hours"] is None


# --------------------------------------------------------------------------
# Integration tests — real Postgres
# --------------------------------------------------------------------------


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
def backfilled_equipment():
    """One throwaway equipment unit, pre-seeded with old (60+ days ago)
    equipment_status_log rows carrying source="downtime_log_import" — enough
    of them that if they counted toward flap detection's trailing window,
    a live status change would falsely report flapping.
    """
    db = SessionLocal()
    equipment = Equipment(site_id=SITE_ID, name="Test Rig METRICS-1", equipment_type="Drill", status="up")
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    equipment_id = equipment.id

    old_base = datetime.now(timezone.utc) - timedelta(days=60)
    for i in range(6):
        old_status, new_status = ("up", "down") if i % 2 == 0 else ("down", "up")
        db.add(
            EquipmentStatusLog(
                equipment_id=equipment_id,
                site_id=SITE_ID,
                old_status=old_status,
                new_status=new_status,
                reason="mechanical failure" if new_status == "down" else "returned to service",
                changed_by="import",
                changed_at=old_base + timedelta(hours=i),
                source="downtime_log_import",
            )
        )
    db.commit()
    db.close()

    yield equipment_id

    db = SessionLocal()
    db.execute(
        delete(RiskEvent).where(
            RiskEvent.source_entity_type == "equipment", RiskEvent.source_entity_id == equipment_id
        )
    )
    db.execute(delete(EquipmentStatusLog).where(EquipmentStatusLog.equipment_id == equipment_id))
    db.execute(delete(Equipment).where(Equipment.id == equipment_id))
    db.commit()
    db.close()


def test_flap_detection_ignores_old_backfilled_rows(client, backfilled_equipment):
    settings = get_settings()
    assert 6 > settings.EQUIPMENT_FLAP_THRESHOLD  # the fixture seeded enough old rows to matter if counted

    response = client.post(
        f"/equipment/{backfilled_equipment}/status",
        json={"status": "down", "reason": "live check", "source": "manual"},
    )
    assert response.status_code == 200
    assert response.json()["flapping"] is False


# -- backfill script ---------------------------------------------------------
# Operates on the real seeded equipment roster (that's its job) and only
# ever touches source="downtime_log_import" rows — safe to run repeatedly.


def test_backfill_is_idempotent(client):
    result_1 = backfill_script.backfill(dry_run=False)
    result_2 = backfill_script.backfill(dry_run=False)

    assert result_1["rows_inserted"] == result_2["rows_inserted"]
    assert result_1["events_inserted"] == result_2["events_inserted"]
    assert result_1["rows_inserted"] > 0
    assert result_1["unmatched_roster_entries"] == []
    assert result_1["skipped_bad_data"] == []

    db = SessionLocal()
    total_rows = db.scalar(
        select(func.count())
        .select_from(EquipmentStatusLog)
        .where(EquipmentStatusLog.source == "downtime_log_import")
    )
    db.close()
    assert total_rows == result_2["rows_inserted"]


def test_backfill_does_not_touch_other_source_rows(client):
    db = SessionLocal()
    some_equipment = db.scalars(select(Equipment).limit(1)).first()
    marker = EquipmentStatusLog(
        equipment_id=some_equipment.id,
        site_id=some_equipment.site_id,
        old_status="up",
        new_status="down",
        reason="marker row",
        changed_by="test",
        changed_at=datetime.now(timezone.utc),
        source="manual",
    )
    db.add(marker)
    db.commit()
    marker_id = marker.id
    db.close()

    try:
        backfill_script.backfill(dry_run=False)
        db = SessionLocal()
        still_there = db.get(EquipmentStatusLog, marker_id)
        assert still_there is not None
        assert still_there.source == "manual"
        assert still_there.reason == "marker row"
        db.close()
    finally:
        db = SessionLocal()
        db.execute(delete(EquipmentStatusLog).where(EquipmentStatusLog.id == marker_id))
        db.commit()
        db.close()


def test_backfill_does_not_change_equipment_status(client):
    db = SessionLocal()
    before = {e.id: (e.status.value, e.last_status_change) for e in db.scalars(select(Equipment)).all()}
    db.close()

    backfill_script.backfill(dry_run=False)

    db = SessionLocal()
    after = {e.id: (e.status.value, e.last_status_change) for e in db.scalars(select(Equipment)).all()}
    db.close()
    assert before == after


def test_backfill_dry_run_writes_nothing(client):
    db = SessionLocal()
    before_count = db.scalar(
        select(func.count())
        .select_from(EquipmentStatusLog)
        .where(EquipmentStatusLog.source == "downtime_log_import")
    )
    db.close()

    result = backfill_script.backfill(dry_run=True)
    assert result["dry_run"] is True
    assert result["rows_inserted"] > 0  # it reports what it WOULD insert

    db = SessionLocal()
    after_count = db.scalar(
        select(func.count())
        .select_from(EquipmentStatusLog)
        .where(EquipmentStatusLog.source == "downtime_log_import")
    )
    db.close()
    assert after_count == before_count


# -- response contract --------------------------------------------------------

FLEET_TOP_KEYS = {"generated_at", "window", "assumptions", "fleet", "equipment", "data_note"}
WINDOW_KEYS = {"start", "end", "hours", "data_through"}
ASSUMPTIONS_KEYS = {"maintenance_interval_days", "due_soon_days", "categories"}
FLEET_KEYS = {
    "site_id", "equipment_count", "physical_availability_pct", "overall_availability_pct",
    "failures", "mtbf_hours", "mttr_hours", "downtime_hours_by_category",
    "maintenance_overdue_count", "maintenance_due_soon_count",
}
EQUIPMENT_ENTRY_KEYS = {
    "equipment_id", "name", "equipment_type", "site_id", "status",
    "physical_availability_pct", "overall_availability_pct", "failures",
    "mtbf_hours", "mttr_hours", "downtime_hours", "downtime_hours_by_category",
    "top_failure_reason", "last_maintenance_at", "days_since_last_maintenance",
    "next_maintenance_due", "maintenance_status", "utilisation_pct", "utilisation_note",
}
CATEGORY_KEYS_SET = {"planned_maintenance", "failure", "spare_parts_wait", "operational", "weather", "other"}


def test_fleet_metrics_response_keys_match_contract(client):
    response = client.get("/equipment/metrics")
    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == FLEET_TOP_KEYS
    assert set(body["window"].keys()) == WINDOW_KEYS
    assert set(body["assumptions"].keys()) == ASSUMPTIONS_KEYS
    assert set(body["assumptions"]["categories"].keys()) == CATEGORY_KEYS_SET
    assert set(body["fleet"].keys()) == FLEET_KEYS
    assert set(body["fleet"]["downtime_hours_by_category"].keys()) == CATEGORY_KEYS_SET
    assert len(body["equipment"]) > 0
    for entry in body["equipment"]:
        assert set(entry.keys()) == EQUIPMENT_ENTRY_KEYS
        assert set(entry["downtime_hours_by_category"].keys()) == CATEGORY_KEYS_SET
        assert entry["utilisation_pct"] is None


def test_equipment_metrics_response_keys_match_contract(client):
    fleet_body = client.get("/equipment/metrics").json()
    one_equipment_id = fleet_body["equipment"][0]["equipment_id"]

    response = client.get(f"/equipment/{one_equipment_id}/metrics")
    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == EQUIPMENT_ENTRY_KEYS | {"weekly", "events"}
    assert set(body["downtime_hours_by_category"].keys()) == CATEGORY_KEYS_SET
    for week in body["weekly"]:
        assert set(week.keys()) == {"week_start", "downtime_hours", "failures", "physical_availability_pct"}
    for event in body["events"]:
        assert set(event.keys()) == {"start", "end", "hours", "reason", "category", "source"}


# -- validation ----------------------------------------------------------------


def test_fleet_metrics_unknown_site_is_404(client):
    assert client.get("/equipment/metrics", params={"site_id": 999999}).status_code == 404


def test_equipment_metrics_unknown_id_is_404(client):
    assert client.get("/equipment/999999/metrics").status_code == 404


def test_fleet_metrics_start_after_end_is_422(client):
    response = client.get("/equipment/metrics", params={"start": "2026-06-01", "end": "2026-01-01"})
    assert response.status_code == 422


def test_equipment_metrics_start_after_end_is_422(client, backfilled_equipment):
    response = client.get(
        f"/equipment/{backfilled_equipment}/metrics",
        params={"start": "2026-06-01", "end": "2026-01-01"},
    )
    assert response.status_code == 422


def test_fleet_metrics_window_too_long_is_422(client):
    response = client.get("/equipment/metrics", params={"start": "2020-01-01", "end": "2026-01-01"})
    assert response.status_code == 422


def test_fleet_metrics_site_filter(client):
    response = client.get("/equipment/metrics", params={"site_id": SITE_ID})
    assert response.status_code == 200
    body = response.json()
    assert body["fleet"]["site_id"] == SITE_ID
    assert all(entry["site_id"] == SITE_ID for entry in body["equipment"])

    expected = client.get("/equipment", params={"site_id": SITE_ID})
    assert body["fleet"]["equipment_count"] == len(expected.json())


def test_fleet_metrics_default_window_is_90_days(client):
    # Exactly DEFAULT_WINDOW_DAYS*24 hours when data_through is safely in the
    # past (no `now`-clipping); up to one extra partial day if data_through
    # happens to be very recent (e.g. a live status change today), since the
    # exclusive end boundary then gets clipped to `now` mid-day rather than
    # landing on a clean midnight. Never less.
    response = client.get("/equipment/metrics")
    assert response.status_code == 200
    hours = response.json()["window"]["hours"]
    expected = equipment_metrics.DEFAULT_WINDOW_DAYS * 24
    assert expected <= hours <= expected + 24


# -- route order -----------------------------------------------------------


def test_metrics_route_is_not_captured_by_equipment_id_route(client):
    fleet_response = client.get("/equipment/metrics")
    assert fleet_response.status_code == 200
    fleet_body = fleet_response.json()
    assert "fleet" in fleet_body
    assert "equipment_id" not in fleet_body

    one_id = fleet_body["equipment"][0]["equipment_id"]
    single_response = client.get(f"/equipment/{one_id}/metrics")
    assert single_response.status_code == 200
    single_body = single_response.json()
    assert "weekly" in single_body
    assert "events" in single_body


# -- pre-existing behaviour unchanged --------------------------------------


def test_existing_equipment_list_endpoint_unchanged(client):
    response = client.get("/equipment")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0
    expected_keys = {
        "id", "site_id", "site_name", "name", "equipment_type",
        "status", "last_status_change", "status_reason", "flapping",
    }
    assert set(body[0].keys()) == expected_keys
