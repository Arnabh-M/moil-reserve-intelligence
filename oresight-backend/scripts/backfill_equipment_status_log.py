"""Backfill equipment_status_log from data/equipment_downtime_log.csv.

Task 6 (equipment performance metrics) needs real downtime *history* to
compute availability/MTBF/MTTR from. scripts/import_p2_data.py already reads
this same CSV, but only to derive Equipment.last_status_change/status — it
DELETES equipment_status_log rows for the imported equipment and never
re-inserts the individual events (see its `_import_equipment`). So today the
database has no downtime history at all except rows written live by
POST /equipment/{id}/status. This script fills that gap, additively, without
touching Equipment.status or Equipment.last_status_change.

Source (repo root, one level above oresight-backend/):
    data/equipment_downtime_log.csv  -> equipment_status_log (two rows per event)
    seed_graph.cypher                -> equipment_id code -> (site, name) roster,
                                         reused (not copied) from
                                         scripts.import_p2_data._parse_equipment_roster,
                                         since Postgres's Equipment table has no
                                         column for the CSV's eq_bal_03-style code.

For each CSV row (one downtime event), inserts two equipment_status_log rows:
    at down_start: old_status="up",   new_status="down", reason=<CSV reason>
    at down_end:   old_status="down", new_status="up",   reason="returned to service"
Both rows get source="downtime_log_import", changed_by="import".

Idempotent: re-running deletes and reinserts only source="downtime_log_import"
rows for the equipment this run actually produced events for, in one
transaction. Rows from any other source (manual/bulk/sync) are never touched.

Run from oresight-backend/, after `alembic upgrade head` and after equipment
exists (i.e. after app.seed_dev / scripts.import_p2_data have run):

    python -m scripts.backfill_equipment_status_log
    python -m scripts.backfill_equipment_status_log --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Equipment, EquipmentStatusLog, Site  # noqa: E402
from scripts.import_p2_data import (  # noqa: E402
    CYPHER_SEED_PATH,
    _parse_equipment_roster,
    _site_name_for_csv_id,
)

DOWNTIME_CSV = REPO_ROOT / "data" / "equipment_downtime_log.csv"
SOURCE = "downtime_log_import"
RETURNED_TO_SERVICE_REASON = "returned to service"


def _load_csv_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _build_code_to_equipment(db: Session) -> tuple[dict[str, Equipment], list[str]]:
    """Map each CSV/cypher equipment_id code (e.g. 'eq_bal_03') to a live DB
    Equipment row, matched on (site, name) — the same roster
    scripts.import_p2_data uses to build Equipment rows in the first place,
    so a code resolves to a row iff import_p2_data actually created one for it.

    Returns (code -> Equipment, unmatched roster entries as "code (name) — reason").
    """
    roster = _parse_equipment_roster(CYPHER_SEED_PATH)
    sites_by_name = {site.name: site for site in db.scalars(select(Site)).all()}

    code_to_equipment: dict[str, Equipment] = {}
    unmatched: list[str] = []
    for entry in roster:
        code = entry["id"]
        name = entry.get("name", "?")
        site_name = _site_name_for_csv_id(entry["site_id"])
        site = sites_by_name.get(site_name) if site_name else None
        if site is None:
            unmatched.append(f"{code} ({name}) — unknown site {entry['site_id']!r}")
            continue
        equipment = db.scalar(
            select(Equipment).where(Equipment.site_id == site.id, Equipment.name == name)
        )
        if equipment is None:
            unmatched.append(f"{code} ({name}) — no Equipment row at site {site.name!r}")
            continue
        code_to_equipment[code] = equipment
    return code_to_equipment, unmatched


def _build_rows(
    csv_rows: list[dict], code_to_equipment: dict[str, Equipment]
) -> tuple[list[tuple[dict, dict]], list[str], list[str]]:
    """Turn CSV rows into (down_row_kwargs, up_row_kwargs) pairs.

    Returns (pairs, unmatched_event_descriptions, bad_data_descriptions).
    """
    pairs: list[tuple[dict, dict]] = []
    unmatched_events: list[str] = []
    bad_data: list[str] = []

    for row in csv_rows:
        code = row["equipment_id"]
        equipment = code_to_equipment.get(code)
        if equipment is None:
            unmatched_events.append(f"{code} (site={row.get('site_id')!r}): no matching Equipment row")
            continue

        try:
            down_start = datetime.strptime(row["down_start"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            down_end = datetime.strptime(row["down_end"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError as exc:
            bad_data.append(f"{code} ({equipment.name}): unparseable timestamp — {exc}")
            continue

        if down_end <= down_start:
            bad_data.append(
                f"{code} ({equipment.name}): down_end {down_end.isoformat()} <= "
                f"down_start {down_start.isoformat()}"
            )
            continue

        pairs.append(
            (
                dict(
                    equipment_id=equipment.id,
                    site_id=equipment.site_id,
                    old_status="up",
                    new_status="down",
                    reason=row["reason"],
                    changed_by="import",
                    changed_at=down_start,
                    source=SOURCE,
                ),
                dict(
                    equipment_id=equipment.id,
                    site_id=equipment.site_id,
                    old_status="down",
                    new_status="up",
                    reason=RETURNED_TO_SERVICE_REASON,
                    changed_by="import",
                    changed_at=down_end,
                    source=SOURCE,
                ),
            )
        )

    return pairs, unmatched_events, bad_data


def backfill(dry_run: bool = False) -> dict:
    db = SessionLocal()
    try:
        code_to_equipment, unmatched_roster = _build_code_to_equipment(db)
        csv_rows = _load_csv_rows(DOWNTIME_CSV)
        pairs, unmatched_events, bad_data = _build_rows(csv_rows, code_to_equipment)
        equipment_ids_involved = sorted({p[0]["equipment_id"] for p in pairs})

        result = {
            "dry_run": dry_run,
            "rows_inserted": len(pairs) * 2,
            "events_inserted": len(pairs),
            "equipment_ids_involved": equipment_ids_involved,
            "unmatched_roster_entries": unmatched_roster,
            "unmatched_event_codes": unmatched_events,
            "skipped_bad_data": bad_data,
        }

        if dry_run:
            return result

        # Delete only this source's rows for the equipment this run touches —
        # rows from any other source (manual/bulk/sync/live PATCH) are untouched.
        db.execute(
            delete(EquipmentStatusLog).where(
                EquipmentStatusLog.source == SOURCE,
                EquipmentStatusLog.equipment_id.in_(equipment_ids_involved),
            )
        )
        for down_kwargs, up_kwargs in pairs:
            db.add(EquipmentStatusLog(**down_kwargs))
            db.add(EquipmentStatusLog(**up_kwargs))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _print_summary(result: dict) -> None:
    label = "Would insert" if result["dry_run"] else "Inserted"
    print(f"\nequipment_status_log backfill{' (dry run)' if result['dry_run'] else ''}")
    print("-" * 60)
    print(f"  {label} rows{'':<21} {result['rows_inserted']:>5}  ({result['events_inserted']} events x 2)")
    print(f"  {'Equipment units touched':<30} {len(result['equipment_ids_involved']):>5}")

    if result["unmatched_roster_entries"]:
        print("\n  WARNING: roster codes with no matching Equipment row (skipped):")
        for line in result["unmatched_roster_entries"]:
            print(f"    - {line}")
    if result["unmatched_event_codes"]:
        print("\n  WARNING: CSV events for codes with no matching Equipment row (skipped):")
        for line in result["unmatched_event_codes"]:
            print(f"    - {line}")
    if result["skipped_bad_data"]:
        print("\n  WARNING: events skipped for bad data:")
        for line in result["skipped_bad_data"]:
            print(f"    - {line}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would happen; write nothing."
    )
    args = parser.parse_args()

    summary = backfill(dry_run=args.dry_run)
    _print_summary(summary)
