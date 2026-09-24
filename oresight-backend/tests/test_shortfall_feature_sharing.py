"""Training and inference must compute blast_delay_days_lag with ONE function.

The model's highest-importance feature is computed from the blast_events table at
inference time and from blast_events.csv at training time. If those were two
implementations they could drift apart with no error and no test failure elsewhere,
so this file pins them together:

  * the training pipeline (shortfall_feature_engineering.build_feature_frame) and
    the inference reader (app.services.blast_features) both call
    app.services.shortfall_features.blast_delay_days_lag, asserted structurally and
    by patching that function and watching the training frame change;
  * the DB reader and the shared function agree on hand-built events;
  * (when the demo DB is seeded) the DB reader reproduces, for every site and a
    spread of dates, exactly what the shared function computes from the CSV.
"""

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.models import BlastDelayReason, BlastEvent, BlastStatus, Site
from app.services import blast_features, shortfall_features

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    # APPEND, never insert(0): the repo root has its own `scripts/` package that must not
    # shadow the backend's `scripts/` for other tests in this process.
    sys.path.append(str(REPO_ROOT))

import shortfall_feature_engineering as fe  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture
def db():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    session = SessionLocal()
    yield session
    session.close()


# -- pure function ------------------------------------------------------------------


def test_window_is_the_trailing_seven_days_ending_the_day_before_t():
    t = date(2026, 6, 20)
    events = [(date(2026, 6, 12), 1), (date(2026, 6, 13), 1), (date(2026, 6, 19), 1), (date(2026, 6, 20), 3)]
    # 06-12 is 8 days back (outside); 06-13 is 7 days back (inside); 06-19 inside;
    # 06-20 is t itself and must never count.
    assert shortfall_features.blast_delay_days_lag(events, t) == 2.0


def test_delay_in_progress_counts_only_days_already_elapsed():
    # a 4-day delay planned 06-18 has, at the start of 06-20, run 06-18 and 06-19 only
    assert shortfall_features.blast_delay_days_lag([(date(2026, 6, 18), 4)], date(2026, 6, 20)) == 2.0


def test_overlapping_events_count_each_calendar_day_once():
    events = [(date(2026, 6, 10), 3), (date(2026, 6, 11), 3)]  # days 10-12 and 11-13, union = 4 days
    assert shortfall_features.blast_delay_days_lag(events, date(2026, 6, 14)) == 4.0


def test_max_open_delay_matches_the_longest_delay_the_model_was_trained_on():
    generator = fe.load_generator_module()
    assert shortfall_features.BLAST_DELAY_MAX_DAYS == generator.BLAST_DELAY_DURATION_DAYS[1]


# -- one code path ---------------------------------------------------------------------


def test_training_and_inference_import_the_same_function():
    assert fe.shared is shortfall_features
    assert blast_features.blast_delay_days_lag is shortfall_features.blast_delay_days_lag
    assert fe.BLAST_LAG_WINDOW_DAYS == shortfall_features.BLAST_LAG_WINDOW_DAYS


def test_training_frame_is_produced_by_the_shared_function(monkeypatch):
    inputs = fe.load_inputs()
    inputs.production = inputs.production[inputs.production["date"] < "2025-03-01"]
    monkeypatch.setattr(shortfall_features, "blast_delay_days_lag", lambda events, t: 42.0)
    frame = fe.build_feature_frame(inputs, fe.machines_per_site())
    assert (frame["blast_delay_days_lag"] == 42.0).all()


# -- DB reader ----------------------------------------------------------------------------

FAR_FUTURE = date(2040, 6, 10)  # no seeded or hand-entered row lives here
NOTE = "test_shortfall_feature_sharing"


@pytest.fixture
def temp_events(db):
    ids: list[int] = []
    yield ids
    if ids:
        db.execute(delete(BlastEvent).where(BlastEvent.id.in_(ids)))
        db.commit()


def _add(db, ids, planned, actual, status, reason):
    row = BlastEvent(
        site_id=1, planned_date=planned, actual_date=actual, status=status, delay_reason=reason,
        expected_yield_tonnes=1000, notes=NOTE,
    )
    db.add(row)
    db.commit()
    ids.append(row.id)


def test_db_reader_matches_the_shared_function_on_hand_built_events(db, temp_events):
    d = FAR_FUTURE
    _add(db, temp_events, d - timedelta(days=5), d - timedelta(days=3), BlastStatus.DELAYED, BlastDelayReason.WEATHER_HOLD)  # 2 days
    _add(db, temp_events, d - timedelta(days=2), None, BlastStatus.DELAYED, BlastDelayReason.PERMIT_PENDING)  # open: 2 days so far
    _add(db, temp_events, d - timedelta(days=4), None, BlastStatus.CANCELLED, BlastDelayReason.WEATHER_HOLD)  # not a delay
    _add(db, temp_events, d - timedelta(days=6), None, BlastStatus.PLANNED, None)  # merely planned
    expected = shortfall_features.blast_delay_days_lag([(d - timedelta(days=5), 2), (d - timedelta(days=2), 2)], d)
    assert expected == 4.0
    assert blast_features.blast_delay_days_lag_for_site(db, 1, d) == expected


def test_open_ended_delay_is_capped_at_the_trained_maximum(db, temp_events):
    d = FAR_FUTURE
    # delayed 30 days ago with no new date: counts as at most BLAST_DELAY_MAX_DAYS from its planned
    # date, and those days are long outside the window, so a stale open row contributes nothing
    _add(db, temp_events, d - timedelta(days=30), None, BlastStatus.DELAYED, BlastDelayReason.PERMIT_PENDING)
    assert blast_features.blast_delay_days_lag_for_site(db, 1, d) == 0.0
    # delayed 3 days ago and still open: 3 elapsed days, all inside the window
    _add(db, temp_events, d - timedelta(days=3), None, BlastStatus.DELAYED, BlastDelayReason.SAFETY_HOLD)
    assert blast_features.blast_delay_days_lag_for_site(db, 1, d) == 3.0


def test_db_reader_reproduces_the_csv_feature_for_every_site_when_seeded(db):
    from scripts.seed_blast_events import SEED_TAG  # backend's own scripts package (pytest cwd = oresight-backend)

    seeded = db.scalars(select(BlastEvent).where(BlastEvent.notes.like(f"{SEED_TAG}%"))).all()
    if not seeded:
        pytest.skip("blast_events not seeded (run scripts.seed_blast_events / rebuild_demo_db)")
    with (REPO_ROOT / "data" / "blast_events.csv").open(newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    names = {s.name.lower(): s.id for s in db.scalars(select(Site)).all()}

    # Hand-entered delay rows (not from the CSV) legitimately change the DB reader's answer from
    # their planned date onward, so only compare dates before the earliest of them.
    others = db.scalars(
        select(BlastEvent.planned_date).where(
            BlastEvent.delay_reason.is_not(None),
            BlastEvent.status != BlastStatus.CANCELLED,
            BlastEvent.notes.not_like(f"{SEED_TAG}%") | BlastEvent.notes.is_(None),
        )
    ).all()
    horizon = min(others) if others else date(2026, 9, 23)

    checked = 0
    for site_key, site_id in names.items():
        events = [(date.fromisoformat(r["planned_date"]), int(r["delay_days"])) for r in csv_rows if r["site_id"] == site_key]
        as_of = date(2025, 1, 15)
        while as_of <= min(horizon, date(2026, 9, 23)):
            assert blast_features.blast_delay_days_lag_for_site(db, site_id, as_of) == shortfall_features.blast_delay_days_lag(
                events, as_of
            ), (site_key, as_of)
            checked += 1
            as_of += timedelta(days=3)
    assert checked > 400
