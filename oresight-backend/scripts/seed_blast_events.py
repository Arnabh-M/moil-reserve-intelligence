"""Seed the blast_events table from data/blast_events.csv (scripts/synthetic_operations.py).

Why this exists: the shortfall model's highest-importance feature,
blast_delay_days_lag, is computed at inference time from this table. Before this
script nothing seeded it, so the model's best signal would have been empty.

CSV row (site_id, planned_date, delay_days, delay_reason, weather_triggered) ->
one blast_events row:
    site_id            resolved from the seeded sites table by name
    planned_date       planned_date
    actual_date        planned_date + delay_days   (so the delay days are exactly
                       planned_date .. actual_date - 1, the same days the CSV and
                       the training pipeline count)
    status             delayed
    delay_reason       the CSV reason (BlastDelayReason enum values match)
    expected_yield_tonnes  PLACEHOLDER - see below
    notes              tagged so this script can find and replace its own rows

Two deliberate gaps, because the CSV does not carry the information:
  * reserve_zone_id is left NULL. The synthetic delays are per site, not per
    zone; picking a zone would put a fabricated relationship into the demo.
  * expected_yield_tonnes is NOT NULL in the schema but the CSV has no yield.
    ASSUMPTION: one day of the site's target output on the planned date. It is a
    placeholder, not a modelled blast yield; actual_yield_tonnes stays NULL.

Idempotent: deletes only rows carrying SEED_TAG in notes, then reinserts. Rows
entered by hand or by tests are never touched.

Run from oresight-backend/, after the sites exist (after app.seed_dev):

    python -m scripts.seed_blast_events
    python -m scripts.seed_blast_events --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import BlastDelayReason, BlastEvent, BlastStatus, Site  # noqa: E402
from scripts.import_p2_data import _site_name_for_csv_id  # noqa: E402

BLAST_CSV = REPO_ROOT / "data" / "blast_events.csv"
PRODUCTION_CSV = REPO_ROOT / "data" / "production_history.csv"
SEED_TAG = "synthetic:blast_events.csv"


def _target_output_by_site_date() -> dict[tuple[str, date], float]:
    with PRODUCTION_CSV.open(newline="", encoding="utf-8") as f:
        return {
            (r["site_id"], date.fromisoformat(r["date"])): float(r["target_output"])
            for r in csv.DictReader(f)
        }


def seed(dry_run: bool = False) -> dict:
    with BLAST_CSV.open(newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    targets = _target_output_by_site_date()

    db = SessionLocal()
    try:
        sites_by_name = {s.name: s for s in db.scalars(select(Site)).all()}
        new_rows: list[BlastEvent] = []
        site_names: list[str] = []
        skipped: list[str] = []
        for r in csv_rows:
            site_name = _site_name_for_csv_id(r["site_id"]) or ""
            site = sites_by_name.get(site_name)
            planned = date.fromisoformat(r["planned_date"])
            target = targets.get((r["site_id"], planned))
            if site is None or target is None:
                skipped.append(f"{r['site_id']} {r['planned_date']}: no site row or no target_output")
                continue
            n_days = int(r["delay_days"])
            reason = BlastDelayReason(r["delay_reason"])  # raises on an unknown reason: fail loudly
            new_rows.append(
                BlastEvent(
                    site_id=site.id,
                    reserve_zone_id=None,
                    planned_date=planned,
                    actual_date=planned + timedelta(days=n_days),
                    status=BlastStatus.DELAYED,
                    delay_reason=reason,
                    expected_yield_tonnes=Decimal(str(round(target, 2))),
                    actual_yield_tonnes=None,
                    notes=f"{SEED_TAG} delay_days={n_days} weather_triggered={r['weather_triggered']}",
                )
            )
            site_names.append(site_name)

        summary = {
            "dry_run": dry_run,
            "rows": len(new_rows),
            "by_site": dict(Counter(site_names)),
            "by_reason": dict(Counter(e.delay_reason.value for e in new_rows)),
            "skipped": skipped,
        }
        if dry_run:
            return summary

        removed = db.execute(delete(BlastEvent).where(BlastEvent.notes.like(f"{SEED_TAG}%"))).rowcount
        db.add_all(new_rows)
        db.commit()
        summary["replaced_previous_rows"] = removed
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen; write nothing.")
    args = parser.parse_args()
    result = seed(dry_run=args.dry_run)
    print(f"\nblast_events seed{' (dry run)' if result['dry_run'] else ''}")
    print("-" * 60)
    print(f"  rows: {result['rows']}   by site: {result['by_site']}")
    print(f"  by reason: {result['by_reason']}")
    if "replaced_previous_rows" in result:
        print(f"  replaced {result['replaced_previous_rows']} previously-seeded rows (tag {SEED_TAG!r})")
    for line in result["skipped"]:
        print(f"  WARNING skipped: {line}")
