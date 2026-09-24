"""TRAINING/INFERENCE PARITY for the shortfall forecaster's feature row.

The model was trained on the frame built by shortfall_feature_engineering.build_feature_frame from
the CSVs. The API builds the same 14 features at request time from Postgres + the satellite CSV
(app/services/live_features.py). If the two ever disagree the model is silently fed inputs it was
not trained on. So for sampled (site, date) pairs across the whole training span, the live row,
built from the SEEDED DATABASE, must equal the training row for every feature.

Needs the rebuilt demo DB (rebuild_demo_db.py): equipment_status_log, production_records and
blast_events all come from the same CSVs the trainer reads. One comparison is skipped: the DB also
holds three hand-entered demo blast events (ids 29-31, dated 2026-08-29..09-04) that the CSV, by
design, does not, and id 29 is an open-ended Balaghat delay, so Balaghat's blast_delay_days_lag is
not compared from 2026-09-04 on. Everything else is compared for the whole span, including the last
days where SMAP soil moisture is genuinely NaN.
"""

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.models import Site
from app.services.live_features import FeatureConstants, build_live_features

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # APPEND: the repo root has its own `scripts/` package

import shortfall_feature_engineering as fe  # noqa: E402

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
DEMO_BLAST_ROWS_START = date(2026, 9, 4)  # id 29: an open-ended Balaghat delay the CSV does not have
SAMPLE_STRIDE = 11

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


@pytest.fixture(scope="module")
def db():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def constants():
    metrics = json.loads((MODELS_DIR / "model_metrics.json").read_text(encoding="utf-8"))
    return FeatureConstants.from_metrics(metrics)


@pytest.fixture(scope="module")
def training_frame():
    inputs = fe.load_inputs()
    frame = fe.build_feature_frame(inputs, fe.machines_per_site())
    return frame[~frame["in_warmup"]]


def _sample(frame):
    """Every SAMPLE_STRIDE-th row per site, plus rows that exercise the non-trivial branches
    (an active blast delay, an outage carried into the day, a NaN soil-moisture reading)."""
    parts = []
    for _, site_rows in frame.groupby("site_id"):
        parts.append(site_rows.iloc[::SAMPLE_STRIDE])
        parts.append(site_rows[site_rows["blast_delay_days_lag"] > 0].head(6))
        parts.append(site_rows[site_rows["equipment_down_today_pct"] > 0].head(6))
        parts.append(site_rows[site_rows["soil_moisture_m3m3"].isna()])
    return pd.concat(parts).drop_duplicates(subset=["site_id", "date"])


def test_live_features_equal_the_training_frame(db, constants, training_frame):
    sites = {s.name.lower(): s for s in db.scalars(select(Site)).all()}
    sample = _sample(training_frame)
    assert len(sample) > 150

    mismatches = []
    for row in sample.itertuples(index=False):
        live = build_live_features(db, sites[row.site_id], constants, as_of=row.date.date())
        for column in fe.FEATURE_COLUMNS:
            if column == "blast_delay_days_lag" and row.site_id == "balaghat" and row.date.date() >= DEMO_BLAST_ROWS_START:
                continue
            if not np.isclose(live.values[column], getattr(row, column), rtol=1e-6, atol=1e-6, equal_nan=True):
                mismatches.append((row.site_id, str(row.date.date()), column, live.values[column], float(getattr(row, column))))
    assert not mismatches, f"{len(mismatches)} live/training feature disagreements, first: {mismatches[:5]}"


def test_the_sample_reaches_every_branch(training_frame):
    sample = _sample(training_frame)
    assert (sample["blast_delay_days_lag"] > 0).any()
    assert (sample["equipment_down_today_pct"] > 0).any()
    assert sample["soil_moisture_m3m3"].isna().any()


# ---------------------------------------------------------------------
# default as-of: a day counts as observed only once it has finished
# ---------------------------------------------------------------------
def test_default_as_of_is_the_latest_finished_day_with_a_complete_rain_window(db, constants):
    site = db.scalars(select(Site).order_by(Site.id)).first()
    today = date(2026, 9, 26)
    asked = []

    def rain_lookup(site_key, start, end):
        asked.append(end)
        # observed through 09-23, exactly like the CSV + archive today; 09-24 onward not yet available
        return {date(2026, 9, 23) - timedelta(days=k): 1.5 for k in range(40)}

    live = build_live_features(
        db, site, constants, today=today, rain_lookup=rain_lookup, soil_lookup=lambda *_: {}
    )
    assert live.as_of == date(2026, 9, 23)
    assert max(asked) == today - timedelta(days=1), "today's in-progress rain must never be requested"
    assert live.values["rain_today_mm"] == 1.5 and live.values["rain_3d_mm"] == pytest.approx(4.5)


def test_a_value_no_source_has_stays_nan_and_is_reported(db, constants):
    site = db.scalars(select(Site).order_by(Site.id)).first()
    as_of = date(2026, 6, 15)
    hole = as_of - timedelta(days=2)
    observed = {as_of - timedelta(days=k): 2.0 for k in range(0, 8) if as_of - timedelta(days=k) != hole}

    live = build_live_features(
        db, site, constants, as_of=as_of, rain_lookup=lambda *_: observed, soil_lookup=lambda *_: {}
    )
    assert math.isnan(live.values["rain_3d_mm"]) and math.isnan(live.values["rain_7d_mm"])  # a hole -> NaN, not zero
    assert live.values["heavy_rain_lag1"] == 0.0  # yesterday itself was observed
    assert {"rain_3d_mm", "rain_7d_mm", "soil_moisture_m3m3"} <= set(live.missing)
