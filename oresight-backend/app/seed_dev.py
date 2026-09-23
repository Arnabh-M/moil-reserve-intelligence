"""Idempotent development seed data for OreSight's Twin State layer.

Safe to re-run: every insert is guarded by an existence check on a natural
key, so running this twice never creates duplicates. Run with:

    python -m app.seed_dev
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Equipment,
    EquipmentStatus,
    ProductionRecord,
    ReserveZone,
    RiskEvent,
    RiskSeverity,
    Site,
)

random.seed(2026)  # deterministic across re-runs

# The three site AOIs are NOT defined here. They come from the canonical
# data/moil_sites.json (copied to app/data/moil_sites.json by
# `python -m scripts.build_site_aois`), which is also what geo_utils,
# generate_datasets, the GEE/prospectivity pipelines and the frontend read.
# There is deliberately no fallback: seeding the DB with a box that differs
# from everything else is the failure this file was restructured to remove.
SITES_JSON_PATH = Path(__file__).resolve().parent / "data" / "moil_sites.json"


def _load_site_specs() -> list[dict]:
    with SITES_JSON_PATH.open(encoding="utf-8") as f:
        doc = json.load(f)

    specs = []
    for site in doc["sites"]:
        bbox = site["bbox"]
        specs.append(
            {
                "key": site["key"],
                "name": site["name"],
                "belt_name": site["belt_name"],
                "district": site["district"],
                "state": site["state"],
                "min_lat": bbox["min_lat"],
                "max_lat": bbox["max_lat"],
                "min_lon": bbox["min_lon"],
                "max_lon": bbox["max_lon"],
                # Box centre, kept as `lat`/`lon` because that is what
                # `sites.centroid` and every existing caller expects.
                "lat": (bbox["min_lat"] + bbox["max_lat"]) / 2,
                "lon": (bbox["min_lon"] + bbox["max_lon"]) / 2,
                "base_output": site["base_output"],
            }
        )
    return specs


SITE_SPECS = _load_site_specs()

# Reserve-zone blocks are placed as a FRACTION of each site's half-extent, not
# as a fixed number of degrees. The AOIs are now real rectangles of different
# sizes (Balaghat is ~35 x 23 km, Nagpur ~11 x 12 km), so the old fixed
# +/-0.035 deg offset with a 0.025 deg half-width pushed blocks outside the
# smaller boxes entirely. With offset 0.50 and half-extent 0.24, every block
# reaches at most 0.74 of the way to its site's edge and no two blocks
# overlap, at any box size.
ZONE_OFFSET_FRAC = 0.50
ZONE_HALF_FRAC = 0.24

ZONE_TEMPLATES = [
    {"suffix": "North Block", "fx": 0.0, "fy": 1.0, "confidence": 0.88, "grade": 38.5, "depth": 42.0},
    {"suffix": "South Block", "fx": 0.0, "fy": -1.0, "confidence": 0.42, "grade": 21.5, "depth": 81.0},
    {"suffix": "East Block", "fx": 1.0, "fy": 0.0, "confidence": 0.63, "grade": 29.4, "depth": 60.0},
    {"suffix": "West Block", "fx": -1.0, "fy": 0.0, "confidence": 0.75, "grade": 33.2, "depth": 52.0},
]


def site_half_extent(spec: dict) -> tuple[float, float]:
    """(half_lon_deg, half_lat_deg) of a site's AOI rectangle."""
    return (
        (spec["max_lon"] - spec["min_lon"]) / 2.0,
        (spec["max_lat"] - spec["min_lat"]) / 2.0,
    )


def zone_centroid(spec: dict, template: dict) -> tuple[float, float]:
    """(lon, lat) centre of one reserve-zone block within a site's AOI."""
    half_lon, half_lat = site_half_extent(spec)
    return (
        spec["lon"] + template["fx"] * ZONE_OFFSET_FRAC * half_lon,
        spec["lat"] + template["fy"] * ZONE_OFFSET_FRAC * half_lat,
    )


def zone_bbox(spec: dict, template: dict) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) of one reserve-zone block."""
    half_lon, half_lat = site_half_extent(spec)
    zone_lon, zone_lat = zone_centroid(spec, template)
    dx = ZONE_HALF_FRAC * half_lon
    dy = ZONE_HALF_FRAC * half_lat
    return (zone_lon - dx, zone_lat - dy, zone_lon + dx, zone_lat + dy)


EQUIPMENT_TEMPLATES = [
    {"prefix": "Excavator", "code": "EX", "equipment_type": "Excavator"},
    {"prefix": "Rock Drill", "code": "DR", "equipment_type": "Drill"},
    {"prefix": "Haul Truck", "code": "HT", "equipment_type": "Haul Truck"},
    {"prefix": "Jaw Crusher", "code": "CR", "equipment_type": "Crusher"},
    {"prefix": "Wheel Loader", "code": "LD", "equipment_type": "Loader"},
]

DOWN_EQUIPMENT = {
    ("Balaghat", "Excavator EX-201"): (
        "Hydraulic pump failure - spare part on order, ETA 3 days"
    ),
    ("Nagpur", "Haul Truck HT-302"): "Engine overheating - pulled for inspection",
}

RISK_EVENT_SPECS = [
    {
        "site": "Balaghat",
        "risk_type": "equipment_failure",
        "severity": RiskSeverity.HIGH,
        "score": 0.81,
        "description": "Excavator EX-201 hydraulic failure is stalling ore loading at Balaghat.",
        "source_entity_type": "equipment",
        "days_ago": 1,
        "resolved": False,
    },
    {
        "site": "Nagpur",
        "risk_type": "weather_delay",
        "severity": RiskSeverity.MEDIUM,
        "score": 0.55,
        "description": "Heavy monsoon rainfall forecast to delay haul road access at Nagpur.",
        "source_entity_type": "weather",
        "days_ago": 3,
        "resolved": True,
    },
    {
        "site": "Bhandara",
        "risk_type": "production_shortfall",
        "severity": RiskSeverity.HIGH,
        "score": 0.70,
        "description": "Bhandara actual output fell sharply below target for the day.",
        "source_entity_type": "production",
        "days_ago": 5,
        "resolved": False,
    },
    {
        "site": "Balaghat",
        "risk_type": "blast_delay",
        "severity": RiskSeverity.LOW,
        "score": 0.30,
        "description": "Scheduled blast at Balaghat postponed pending safety clearance.",
        "source_entity_type": None,
        "days_ago": 7,
        "resolved": True,
    },
    {
        "site": "Nagpur",
        "risk_type": "equipment_failure",
        "severity": RiskSeverity.CRITICAL,
        "score": 0.93,
        "description": "Haul Truck HT-302 engine overheating has taken the unit fully offline.",
        "source_entity_type": "equipment",
        "days_ago": 0,
        "resolved": False,
    },
    {
        "site": "Bhandara",
        "risk_type": "weather_delay",
        "severity": RiskSeverity.MEDIUM,
        "score": 0.48,
        "description": "Waterlogged pit access road reported after overnight rain at Bhandara.",
        "source_entity_type": "weather",
        "days_ago": 9,
        "resolved": False,
    },
]


def _bbox_polygon(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> WKTElement:
    """Rectangle from explicit bounds. The AOIs are rectangles, not squares --
    a single `half_deg` cannot express a 35 x 23 km box."""
    ring = (
        f"{min_lon} {min_lat}, "
        f"{max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, "
        f"{min_lon} {max_lat}, "
        f"{min_lon} {min_lat}"
    )
    return WKTElement(f"POLYGON(({ring}))", srid=4326)


def _point(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def _geom_matches(session: Session, stored, expected: WKTElement) -> bool:
    """True if a stored geometry is the same shape as the one the spec wants.

    Compared with ST_Equals in the database rather than by WKT string: PostGIS
    renders coordinates its own way, so a text comparison would report a
    difference on every run and rewrite geometry that is already correct.
    """
    if stored is None:
        return False
    return bool(session.scalar(select(func.ST_Equals(stored, expected))))


def _get_or_create_site(session: Session, spec: dict) -> tuple[Site, bool]:
    existing = session.scalar(select(Site).where(Site.name == spec["name"]))
    if existing is not None:
        # Skip-if-exists applies to the ROW, not to its geometry. The AOI is
        # defined in data/moil_sites.json, so if the stored polygon no longer
        # matches that file the row is stale and gets rewritten. Without this,
        # re-seeding an existing DB after the AOIs move leaves Postgres holding
        # the old boxes forever while every other consumer has the new ones —
        # a silent fourth copy of the site definition.
        geom = _bbox_polygon(
            spec["min_lon"], spec["min_lat"], spec["max_lon"], spec["max_lat"]
        )
        centroid = _point(spec["lon"], spec["lat"])
        if not _geom_matches(session, existing.geom, geom):
            print(
                f"  [seed_dev] {spec['name']}: AOI polygon differs from "
                f"moil_sites.json — updating sites.geom and sites.centroid"
            )
            existing.geom = geom
            existing.centroid = centroid
            session.flush()
        return existing, False

    site = Site(
        name=spec["name"],
        belt_name=spec["belt_name"],
        district=spec["district"],
        state=spec["state"],
        geom=_bbox_polygon(
            spec["min_lon"], spec["min_lat"], spec["max_lon"], spec["max_lat"]
        ),
        centroid=_point(spec["lon"], spec["lat"]),
    )
    session.add(site)
    session.flush()
    return site, True


def _seed_reserve_zones(session: Session, site: Site, spec: dict) -> int:
    inserted = 0
    for i, template in enumerate(ZONE_TEMPLATES):
        zone_name = f"{site.name} {template['suffix']}"
        existing = session.scalar(
            select(ReserveZone).where(
                ReserveZone.site_id == site.id, ReserveZone.zone_name == zone_name
            )
        )
        if existing is not None:
            # Same rule as the site row above: the block's POSITION is derived
            # from the site's AOI, so a stale polygon is rewritten. Its
            # confidence/grade/depth are NOT touched here — those are owned
            # downstream by import_p2_data and import_prospectivity_scores.
            zone_geom = _bbox_polygon(*zone_bbox(spec, template))
            if not _geom_matches(session, existing.geom, zone_geom):
                print(
                    f"  [seed_dev] {zone_name}: block position differs from the "
                    f"site AOI — updating reserve_zones.geom"
                )
                existing.geom = zone_geom
                session.flush()
            continue

        # Small deterministic per-site, per-zone spread so no two sites look identical.
        site_index = SITE_SPECS.index(spec)
        site_offset = (i - 1) * 0.02 + site_index * 0.015
        confidence = min(0.92, max(0.35, template["confidence"] + site_offset * 0.1))

        session.add(
            ReserveZone(
                site_id=site.id,
                zone_name=zone_name,
                geom=_bbox_polygon(*zone_bbox(spec, template)),
                confidence_score=round(confidence, 2),
                estimated_grade_pct=round(template["grade"] + site_offset, 1),
                estimated_depth_m=round(template["depth"] + site_offset * 10, 1),
                last_updated=datetime.now(timezone.utc) - timedelta(days=i),
            )
        )
        inserted += 1

    session.flush()
    return inserted


def _seed_equipment(session: Session, site: Site) -> tuple[int, dict[str, Equipment]]:
    inserted = 0
    by_name: dict[str, Equipment] = {}
    now = datetime.now(timezone.utc)

    for template in EQUIPMENT_TEMPLATES:
        # Deterministic, spec-matching numbering: EX-201/202/203, DR-101/102/103, etc.
        number = {
            "Excavator": 200,
            "Drill": 100,
            "Haul Truck": 300,
            "Crusher": 400,
            "Loader": 500,
        }[template["equipment_type"]] + SITE_SPECS.index(
            next(s for s in SITE_SPECS if s["name"] == site.name)
        ) + 1
        name = f"{template['prefix']} {template['code']}-{number}"

        existing = session.scalar(
            select(Equipment).where(
                Equipment.site_id == site.id, Equipment.name == name
            )
        )
        if existing is not None:
            by_name[name] = existing
            continue

        down_reason = DOWN_EQUIPMENT.get((site.name, name))
        equipment = Equipment(
            site_id=site.id,
            name=name,
            equipment_type=template["equipment_type"],
            status=EquipmentStatus.DOWN if down_reason else EquipmentStatus.UP,
            status_reason=down_reason,
            last_status_change=now - timedelta(days=1 if down_reason else random.randint(30, 90)),
        )
        session.add(equipment)
        inserted += 1
        by_name[name] = equipment

    session.flush()
    return inserted, by_name


def _seed_production_records(
    session: Session, site: Site
) -> tuple[int, list[ProductionRecord]]:
    spec = next(s for s in SITE_SPECS if s["name"] == site.name)
    base_output = spec["base_output"]

    today = date.today()
    start = today - timedelta(days=59)
    shortfall_count = random.choice([3, 4])
    shortfall_days = set(random.sample(range(60), shortfall_count))

    inserted = 0
    shortfall_records: list[ProductionRecord] = []

    for offset in range(60):
        record_date = start + timedelta(days=offset)
        existing = session.scalar(
            select(ProductionRecord).where(
                ProductionRecord.site_id == site.id,
                ProductionRecord.date == record_date,
            )
        )
        if existing is not None:
            if offset in shortfall_days:
                shortfall_records.append(existing)
            continue

        weekday = record_date.weekday()
        if weekday == 6:  # Sunday
            weekday_multiplier = 0.55
        elif weekday == 5:  # Saturday
            weekday_multiplier = 0.85
        else:
            weekday_multiplier = 1.0

        target = round(base_output * weekday_multiplier, 1)

        if offset in shortfall_days:
            actual = round(target * random.uniform(0.60, 0.75), 1)
        else:
            actual = round(target * random.uniform(0.95, 1.05), 1)

        record = ProductionRecord(
            site_id=site.id,
            date=record_date,
            actual_output=actual,
            target_output=target,
        )
        session.add(record)
        inserted += 1
        if offset in shortfall_days:
            shortfall_records.append(record)

    session.flush()
    return inserted, shortfall_records


def _seed_risk_events(
    session: Session,
    sites_by_name: dict[str, Site],
    down_equipment_by_site: dict[str, dict[str, Equipment]],
    shortfall_records_by_site: dict[str, list[ProductionRecord]],
) -> int:
    inserted = 0
    now = datetime.now(timezone.utc)

    for spec in RISK_EVENT_SPECS:
        site = sites_by_name[spec["site"]]
        existing = session.scalar(
            select(RiskEvent).where(
                RiskEvent.site_id == site.id,
                RiskEvent.description == spec["description"],
            )
        )
        if existing is not None:
            continue

        detected_at = now - timedelta(days=spec["days_ago"], hours=random.randint(0, 6))

        source_entity_id = None
        if spec["source_entity_type"] == "equipment":
            down_equipment = [
                eq
                for eq in down_equipment_by_site.get(site.name, {}).values()
                if eq.status == EquipmentStatus.DOWN
            ]
            if down_equipment:
                source_entity_id = down_equipment[0].id
        elif spec["source_entity_type"] == "production":
            shortfalls = shortfall_records_by_site.get(site.name, [])
            if shortfalls:
                source_entity_id = shortfalls[0].id

        resolved_at = None
        if spec["resolved"]:
            resolved_at = detected_at + timedelta(hours=random.randint(6, 48))

        session.add(
            RiskEvent(
                site_id=site.id,
                risk_type=spec["risk_type"],
                severity=spec["severity"],
                score=spec["score"],
                description=spec["description"],
                source_entity_type=spec["source_entity_type"],
                source_entity_id=source_entity_id,
                resolved=spec["resolved"],
                detected_at=detected_at,
                resolved_at=resolved_at,
            )
        )
        inserted += 1

    session.flush()
    return inserted


def seed() -> dict[str, int]:
    session = SessionLocal()
    summary = {
        "sites": 0,
        "reserve_zones": 0,
        "equipment": 0,
        "production_records": 0,
        "risk_events": 0,
    }

    try:
        sites_by_name: dict[str, Site] = {}
        down_equipment_by_site: dict[str, dict[str, Equipment]] = {}
        shortfall_records_by_site: dict[str, list[ProductionRecord]] = {}

        for spec in SITE_SPECS:
            site, created = _get_or_create_site(session, spec)
            sites_by_name[site.name] = site
            summary["sites"] += 1 if created else 0

            summary["reserve_zones"] += _seed_reserve_zones(session, site, spec)

            equipment_inserted, equipment_by_name = _seed_equipment(session, site)
            summary["equipment"] += equipment_inserted
            down_equipment_by_site[site.name] = equipment_by_name

            production_inserted, shortfalls = _seed_production_records(session, site)
            summary["production_records"] += production_inserted
            shortfall_records_by_site[site.name] = shortfalls

        summary["risk_events"] = _seed_risk_events(
            session, sites_by_name, down_equipment_by_site, shortfall_records_by_site
        )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return summary


def _print_summary(summary: dict[str, int]) -> None:
    print("\nOreSight dev seed summary (rows newly inserted this run)")
    print("-" * 55)
    for table, count in summary.items():
        print(f"  {table:<20} {count:>5}")
    print("-" * 55)


if __name__ == "__main__":
    result = seed()
    _print_summary(result)
