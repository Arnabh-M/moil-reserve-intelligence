"""The demo DB's production series must end where the real (CSV) series ends.

seed_dev used to pad every missing day up to *today* with synthetic rows on its second pass, adding rows
dated after the real series whose target (1,250 vs 1,056) and actual (above target) contradicted it. Needs
the rebuilt demo DB."""

import csv
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.models import ProductionRecord, Site

CSV = Path(__file__).resolve().parents[2] / "data" / "production_history.csv"


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


def test_db_production_ends_with_the_real_series_and_matches_it():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    csv_end = {}
    csv_target = {}
    for r in rows:
        d = date.fromisoformat(r["date"])
        csv_end[r["site_id"]] = max(d, csv_end.get(r["site_id"], d))
        csv_target[(r["site_id"], d)] = float(r["target_output"])
    db = SessionLocal()
    try:
        for site in db.scalars(select(Site)).all():
            key = site.name.lower()
            last = db.scalar(select(func.max(ProductionRecord.date)).where(ProductionRecord.site_id == site.id))
            assert last == csv_end[key], f"{site.name}: DB production runs to {last}, the real series ends {csv_end[key]}"
            row = db.scalars(
                select(ProductionRecord).where(ProductionRecord.site_id == site.id, ProductionRecord.date == last)
            ).one()
            assert row.target_output == pytest.approx(csv_target[(key, last)])
    finally:
        db.close()
