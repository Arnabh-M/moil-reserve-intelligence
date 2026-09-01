"""Import P2's real datasets into Postgres, replacing seed_dev.py's synthetic
equipment and production data with the real thing.

Sources (repo root, one level above oresight-backend/):
    data/production_history.csv      -> production_records (full replace per site)
    data/equipment_downtime_log.csv  -> equipment.status / last_status_change
    data/deposit_ground_truth.csv    -> reserve_zones confidence/grade/depth
    seed_graph.cypher                -> equipment master roster (id/name/type/site)

P2's downtime log has no type/name columns -- it's an event log, not an
equipment master list, and only covers units that ever went down (13 of 15).
So the equipment *roster* comes from Neo4j's seed_graph.cypher instead, which
is also how the Postgres/Neo4j type-vocabulary mismatch documented in this
repo's README gets closed: Postgres equipment stops being an independently
-invented fleet and becomes the same 15 units Neo4j already knows about, in
Neo4j's own Title-Case vocabulary (Excavator/Drill/Conveyor/Loader/
Compressor). See the printed summary for what that means for the two
Postgres-only types (haul_truck, crusher) that this removes.

Sites and reserve-zone *geometry* are NOT sourced from these CSVs (none of
them carry polygon data) -- this script reuses app/seed_dev.py's site + zone
bootstrap helpers as-is for that part, then overwrites each zone's
confidence_score/estimated_grade_pct/estimated_depth_m with real per-zone
aggregates computed from deposit_ground_truth.csv (nearest-centroid assignment
of each point deposit to one of seed_dev's 4 zone boxes per site).

Idempotent, but not uniformly so:
  - sites, reserve_zones (existence + geometry): additive/skip-if-exists,
    exactly like seed_dev.py.
  - reserve_zones (confidence/grade/depth attributes): recomputed and
    overwritten every run from the CSV -- same input, same output.
  - equipment, production_records: FULLY REPLACED every run (delete all rows
    for the 3 sites, reinsert fresh from source). This is a hard reset, not a
    merge -- any manual edits made via POST /equipment/{id}/status or
    POST /production since the last import are discarded. That's intentional
    for an import/reset script, but don't re-run this mid-demo expecting it to
    leave manual test data alone.

Run from oresight-backend/, after `alembic upgrade head` (and ideally after
`python -m app.seed_dev`, so risk_events still get seeded -- see README):

    python -m scripts.import_p2_data
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.seed_dev as seed_dev  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Equipment,
    EquipmentStatus,
    ProductionRecord,
    ReserveZone,
    Site,
)

DATA_DIR = REPO_ROOT / "data"
PRODUCTION_CSV = DATA_DIR / "production_history.csv"
DOWNTIME_CSV = DATA_DIR / "equipment_downtime_log.csv"
DEPOSITS_CSV = DATA_DIR / "deposit_ground_truth.csv"
CYPHER_SEED_PATH = REPO_ROOT / "seed_graph.cypher"

_EQUIPMENT_BLOCK_RE = re.compile(r"CREATE\s*\(:Equipment\s*\{(?P<body>[^}]*)\}\)")
_FIELD_RE = re.compile(r"(\w+):\s*(?:'([^']*)'|datetime\('([^']*)'\))")


def _site_name_for_csv_id(csv_site_id: str) -> str | None:
    """Map a lowercase CSV/cypher site_id ("balaghat") to seed_dev's Site.name
    ("Balaghat"). All three datasets + seed_graph.cypher happen to agree on
    this lowercase(name) convention, so a simple case-insensitive match is
    exact -- no separate lookup table needed.
    """
    return next(
        (spec["name"] for spec in seed_dev.SITE_SPECS if spec["name"].lower() == csv_site_id),
        None,
    )


def _parse_equipment_roster(cypher_path: Path) -> list[dict[str, str]]:
    """Parse the 15 `CREATE (:Equipment {...})` lines out of seed_graph.cypher.

    Regex, not a Cypher parser -- good enough for this file's flat literal
    syntax, and avoids a new dependency for one script.
    """
    text = cypher_path.read_text(encoding="utf-8")
    roster: list[dict[str, str]] = []
    for block in _EQUIPMENT_BLOCK_RE.finditer(text):
        fields: dict[str, str] = {}
        for fm in _FIELD_RE.finditer(block.group("body")):
            key = fm.group(1)
            value = fm.group(2) if fm.group(2) is not None else fm.group(3)
            fields[key] = value
        roster.append(fields)
    return roster


def _load_downtime_log(csv_path: Path) -> dict[str, dict]:
    """Return {equipment_id: {"last_status_change", "event_count", "total_hours"}}
    derived from the real downtime log.

    Every window in the log is closed (has a down_end) as of the data's latest
    date, so every equipment ends up status=UP here -- there's no currently
    -open outage to import. See the printed summary / README for what that
    means for demo scenarios that want a visibly-down unit.
    """
    by_id: dict[str, dict] = defaultdict(
        lambda: {"last_status_change": None, "event_count": 0, "total_hours": 0.0}
    )
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry = by_id[row["equipment_id"]]
            down_end = datetime.strptime(row["down_end"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            if entry["last_status_change"] is None or down_end > entry["last_status_change"]:
                entry["last_status_change"] = down_end
            entry["event_count"] += 1
            entry["total_hours"] += float(row["duration_hours"])
    return dict(by_id)


def _load_production_rows(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "site_id": row["site_id"],
                    "date": datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    "actual_output": float(row["actual_output"]),
                    "target_output": float(row["target_output"]),
                }
            )
    return rows


def _load_deposits(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "site_id": row["site_id"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "depth_m": float(row["depth_m"]),
                    "grade_percent": float(row["grade_percent"]),
                    "is_confirmed": row["is_confirmed_deposit"].strip().lower() == "true",
                }
            )
    return rows


def _import_equipment(
    db: Session, sites_by_name: dict[str, Site]
) -> tuple[int, dict[str, dict], list[str]]:
    """Full replace: delete equipment for these 3 sites, reinsert from the
    Neo4j roster with status/last_status_change derived from real downtime
    history.
    """
    roster = _parse_equipment_roster(CYPHER_SEED_PATH)
    downtime = _load_downtime_log(DOWNTIME_CSV)

    site_ids = [site.id for site in sites_by_name.values()]
    db.execute(delete(Equipment).where(Equipment.site_id.in_(site_ids)))
    db.flush()

    inserted = 0
    unmatched: list[str] = []
    for row in roster:
        site_name = _site_name_for_csv_id(row["site_id"])
        site = sites_by_name.get(site_name) if site_name else None
        if site is None:
            unmatched.append(row["id"])
            continue

        info = downtime.get(row["id"])
        db.add(
            Equipment(
                site_id=site.id,
                name=row["name"],
                equipment_type=row["type"],
                status=EquipmentStatus.UP,
                status_reason=None,
                last_status_change=info["last_status_change"] if info else None,
            )
        )
        inserted += 1

    db.flush()
    return inserted, downtime, unmatched


def _import_production(db: Session, sites_by_name: dict[str, Site]) -> tuple[int, list[str]]:
    rows = _load_production_rows(PRODUCTION_CSV)
    site_ids = [site.id for site in sites_by_name.values()]
    db.execute(delete(ProductionRecord).where(ProductionRecord.site_id.in_(site_ids)))
    db.flush()

    inserted = 0
    unmatched: list[str] = []
    for row in rows:
        site_name = _site_name_for_csv_id(row["site_id"])
        site = sites_by_name.get(site_name) if site_name else None
        if site is None:
            if row["site_id"] not in unmatched:
                unmatched.append(row["site_id"])
            continue
        db.add(
            ProductionRecord(
                site_id=site.id,
                date=row["date"],
                actual_output=row["actual_output"],
                target_output=row["target_output"],
            )
        )
        inserted += 1

    db.flush()
    return inserted, unmatched


def _assign_deposits_to_zones(spec: dict, site_deposits: list[dict]) -> dict[str, list[dict]]:
    """Nearest-centroid assignment of point deposits to seed_dev's 4 zone
    boxes per site. Deposits scatter well beyond any single zone's small
    bounding box (some fall outside the site's own box), so a containment
    test would leave most deposits unassigned -- nearest-centroid is simple,
    deterministic, and gives every deposit a zone.
    """
    centroids = [
        (t["suffix"], spec["lon"] + t["dx"], spec["lat"] + t["dy"]) for t in seed_dev.ZONE_TEMPLATES
    ]
    groups: dict[str, list[dict]] = {suffix: [] for suffix, _, _ in centroids}
    for deposit in site_deposits:
        suffix, _, _ = min(
            centroids,
            key=lambda c: (c[1] - deposit["longitude"]) ** 2 + (c[2] - deposit["latitude"]) ** 2,
        )
        groups[suffix].append(deposit)
    return groups


def _update_reserve_zone_stats(db: Session, sites_by_name: dict[str, Site]) -> tuple[int, list[str]]:
    """Overwrite each zone's confidence_score/estimated_grade_pct/
    estimated_depth_m with real aggregates from deposit_ground_truth.csv.
    Geometry is untouched -- it still comes from seed_dev.py's templates,
    since the CSV has no zone polygons, only point deposits.
    """
    deposits = _load_deposits(DEPOSITS_CSV)
    updated = 0
    empty_zones: list[str] = []

    for spec in seed_dev.SITE_SPECS:
        site = sites_by_name[spec["name"]]
        site_key = spec["name"].lower()
        site_deposits = [d for d in deposits if d["site_id"] == site_key]
        groups = _assign_deposits_to_zones(spec, site_deposits)

        for template in seed_dev.ZONE_TEMPLATES:
            zone_name = f"{site.name} {template['suffix']}"
            zone = db.scalar(
                select(ReserveZone).where(
                    ReserveZone.site_id == site.id, ReserveZone.zone_name == zone_name
                )
            )
            if zone is None:
                continue

            group = groups.get(template["suffix"], [])
            if not group:
                empty_zones.append(zone_name)
                continue

            confirmed = [d for d in group if d["is_confirmed"]]
            grade_source = confirmed or group
            depth_source = confirmed or group

            zone.confidence_score = round(len(confirmed) / len(group), 2)
            zone.estimated_grade_pct = round(
                sum(d["grade_percent"] for d in grade_source) / len(grade_source), 1
            )
            zone.estimated_depth_m = round(
                sum(d["depth_m"] for d in depth_source) / len(depth_source), 1
            )
            zone.last_updated = datetime.now(timezone.utc)
            updated += 1

    db.flush()
    return updated, empty_zones


def import_data() -> dict:
    db = SessionLocal()
    try:
        sites_by_name: dict[str, Site] = {}
        sites_created = 0
        zones_created = 0
        for spec in seed_dev.SITE_SPECS:
            site, created = seed_dev._get_or_create_site(db, spec)
            sites_by_name[site.name] = site
            sites_created += 1 if created else 0
            zones_created += seed_dev._seed_reserve_zones(db, site, spec)
        db.flush()

        equipment_count, downtime, unmatched_equipment_sites = _import_equipment(db, sites_by_name)
        production_count, unmatched_production_sites = _import_production(db, sites_by_name)
        zones_updated, empty_zones = _update_reserve_zone_stats(db, sites_by_name)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    events_with_downtime = sum(1 for v in downtime.values() if v["event_count"] > 0)
    return {
        "sites_created": sites_created,
        "reserve_zones_created": zones_created,
        "reserve_zones_stats_updated": zones_updated,
        "reserve_zones_no_deposits": empty_zones,
        "equipment_replaced": equipment_count,
        "equipment_with_downtime_history": events_with_downtime,
        "production_records_replaced": production_count,
        "unmatched_equipment_sites": unmatched_equipment_sites,
        "unmatched_production_sites": unmatched_production_sites,
    }


def _print_summary(summary: dict) -> None:
    print("\nOreSight P2 data import summary")
    print("-" * 60)
    print(f"  {'sites (newly created)':<38} {summary['sites_created']:>5}")
    print(f"  {'reserve_zones (newly created)':<38} {summary['reserve_zones_created']:>5}")
    print(f"  {'reserve_zones (stats refreshed from CSV)':<38} {summary['reserve_zones_stats_updated']:>5}")
    print(f"  {'equipment (replaced from Neo4j roster)':<38} {summary['equipment_replaced']:>5}")
    print(f"  {'  - with real downtime history':<38} {summary['equipment_with_downtime_history']:>5}")
    print(f"  {'production_records (replaced)':<38} {summary['production_records_replaced']:>5}")
    print("-" * 60)

    if summary["reserve_zones_no_deposits"]:
        print(
            "\n  NOTE: no deposits landed nearest these zones, stats left at "
            f"seed_dev's template defaults: {', '.join(summary['reserve_zones_no_deposits'])}"
        )
    if summary["unmatched_equipment_sites"] or summary["unmatched_production_sites"]:
        print(
            "\n  WARNING: rows skipped -- site_id in CSV/cypher didn't match any "
            f"known site. equipment={summary['unmatched_equipment_sites']} "
            f"production={summary['unmatched_production_sites']}"
        )

    print(
        "\n  Equipment status is derived entirely from equipment_downtime_log.csv: "
        "every logged window is closed as of the data's latest date (2026-08-30), "
        "so ALL equipment now imports as status='up'. seed_dev.py's 2 hardcoded "
        "'down' units are gone. If a demo scenario needs a visibly-down unit, set "
        "one explicitly via POST /equipment/{id}/status -- this importer won't "
        "invent one."
    )
    print(
        "\n  Equipment types now come verbatim from seed_graph.cypher's 15-unit "
        "roster (Excavator/Drill/Conveyor/Loader/Compressor), not invented "
        "independently -- this closes the Postgres/Neo4j taxonomy gap by "
        "construction. haul_truck/crusher no longer appear anywhere in Postgres "
        "because they never existed in Neo4j's fleet to begin with. If MOIL's "
        "real equipment roster includes haul trucks or crushers, that's a content "
        "gap in seed_graph.cypher to raise with P2 -- not a naming mismatch this "
        "script can fix."
    )


if __name__ == "__main__":
    result = import_data()
    _print_summary(result)
