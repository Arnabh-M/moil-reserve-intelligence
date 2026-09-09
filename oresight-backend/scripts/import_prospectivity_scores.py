"""Overwrite reserve_zones.confidence_score with the trained RF + PyKrige
prospectivity surface (repo-root "Pipeline B").

Source (repo root, one level above oresight-backend/):
    data/reserve_zones.geojson  -> reserve_zones.confidence_score

That GeoJSON is the committed output of the offline chain
(generate_datasets -> generate_features -> train_reserve_classifier ->
build_confidence_surface -> export_reserve_zones): a FeatureCollection of
small rectangular grid cells, each carrying a continuous
`confidence_score` in [0, 1] (kriged RandomForest prospectivity
probability) and a LOWERCASE STRING `site_id` ("balaghat"/"nagpur"/
"bhandara").

Why this script exists: scripts/import_p2_data.py's
`_update_reserve_zone_stats` sets `confidence_score = len(confirmed) /
len(group)` where `group` is the handful of ground-truth point deposits
that land nearest a zone box. With 3-6 points per zone that ratio can
only take a few values (0.0, 0.5, 0.67, 1.0) -- a sample-size artifact,
not a real confidence gradient. This replaces that column (and only that
column) with the zone-averaged kriged probability, which is continuous.
grade/depth are left exactly as import_p2_data computed them -- those
still come from the CSV and are still correct.

What it does, per Postgres ReserveZone row:
  1. Take every grid cell in the GeoJSON whose centroid falls INSIDE the
     zone's `geom` polygon (boundary-exclusive containment, matching
     PostGIS ST_Contains semantics -- done here with shapely on the
     GeoAlchemy2 geometry so there's no per-cell DB round trip).
  2. The zone's new `confidence_score` = mean of those cells'
     `confidence_score`, rounded to 3 dp. `last_updated` is bumped too.
  3. If a zone contains ZERO cells, its existing value is LEFT UNCHANGED
     and a warning names it -- no 0.0 fallback, no interpolation, no
     silent skip.

The GeoJSON `site_id` string is mapped to the integer `sites.id` via
`import_p2_data._site_name_for_csv_id` (lowercase(Site.name) convention),
and used as a redundant guard alongside the geometric test.

Idempotent: same GeoJSON in, same `confidence_score` out on every re-run.
No inserts, no deletes, no geometry changes.

Run from oresight-backend/, AFTER scripts.import_p2_data (which
overwrites confidence_score every run and would otherwise clobber this)
and BEFORE the scenario seeds:

    python -m scripts.import_prospectivity_scores
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from geoalchemy2.shape import to_shape  # noqa: E402
from shapely.geometry import Point, shape  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import ReserveZone, Site  # noqa: E402
from scripts.import_p2_data import _site_name_for_csv_id  # noqa: E402

SURFACE_GEOJSON = REPO_ROOT / "data" / "reserve_zones.geojson"


def _load_surface_cells(path: Path) -> list[tuple[Point, float, str]]:
    """Return [(centroid, confidence_score, site_id_str), ...] for every
    grid cell in the exported prospectivity surface.
    """
    with path.open(encoding="utf-8") as f:
        fc = json.load(f)

    cells: list[tuple[Point, float, str]] = []
    for feature in fc.get("features", []):
        props = feature.get("properties", {})
        centroid = shape(feature["geometry"]).centroid
        cells.append(
            (centroid, float(props["confidence_score"]), str(props["site_id"]))
        )
    return cells


def _site_id_by_surface_key(db: Session) -> dict[str, int]:
    """Map each lowercase GeoJSON site_id string to the integer sites.id,
    via import_p2_data's lowercase(Site.name) convention.
    """
    mapping: dict[str, int] = {}
    for site in db.scalars(select(Site)).all():
        mapping[site.name.lower()] = site.id
    return mapping


def import_scores() -> dict:
    if not SURFACE_GEOJSON.exists():
        raise SystemExit(
            f"prospectivity surface not found: {SURFACE_GEOJSON}\n"
            "Run the offline chain first (generate_datasets -> generate_features "
            "-> train_reserve_classifier -> build_confidence_surface -> "
            "export_reserve_zones)."
        )

    cells = _load_surface_cells(SURFACE_GEOJSON)

    db = SessionLocal()
    try:
        surface_key_to_site_id = _site_id_by_surface_key(db)

        zones = db.scalars(
            select(ReserveZone).order_by(ReserveZone.site_id, ReserveZone.id)
        ).all()

        rows: list[dict] = []
        updated = 0
        empty_zones: list[str] = []
        now = datetime.now(timezone.utc)

        for zone in zones:
            polygon = to_shape(zone.geom)
            contained = [
                score
                for centroid, score, site_key in cells
                if surface_key_to_site_id.get(site_key) == zone.site_id
                and polygon.contains(centroid)
            ]

            before = zone.confidence_score
            if not contained:
                empty_zones.append(zone.zone_name or f"zone#{zone.id}")
                rows.append(
                    {
                        "id": zone.id,
                        "site_id": zone.site_id,
                        "zone_name": zone.zone_name,
                        "before": before,
                        "after": before,
                        "cells": 0,
                        "changed": False,
                    }
                )
                continue

            after = round(fmean(contained), 3)
            zone.confidence_score = after
            zone.last_updated = now
            updated += 1
            rows.append(
                {
                    "id": zone.id,
                    "site_id": zone.site_id,
                    "zone_name": zone.zone_name,
                    "before": before,
                    "after": after,
                    "cells": len(contained),
                    "changed": before != after,
                }
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "surface_cells": len(cells),
        "zones_total": len(zones),
        "zones_scored": updated,
        "zones_changed": sum(1 for r in rows if r["changed"]),
        "zones_empty": empty_zones,
        "rows": rows,
    }


def _print_summary(summary: dict) -> None:
    print("\nOreSight prospectivity-score import summary")
    print("-" * 72)
    print(
        f"  surface cells loaded: {summary['surface_cells']}   "
        f"zones: {summary['zones_total']}   "
        f"surface-scored: {summary['zones_scored']}   "
        f"values changed this run: {summary['zones_changed']}"
    )
    print("-" * 72)
    print(f"  {'id':>3}  {'zone':<24} {'cells':>5}  {'before':>8}  {'after':>8}")
    print(f"  {'-' * 3}  {'-' * 24} {'-' * 5}  {'-' * 8}  {'-' * 8}")
    for row in summary["rows"]:
        before = "n/a" if row["before"] is None else f"{row['before']:.3f}"
        after = "n/a" if row["after"] is None else f"{row['after']:.3f}"
        flag = "" if row["changed"] else "  (unchanged)"
        print(
            f"  {row['id']:>3}  {row['zone_name'] or '':<24} {row['cells']:>5}  "
            f"{before:>8}  {after:>8}{flag}"
        )
    print("-" * 72)

    if summary["zones_empty"]:
        print(
            "\n  WARNING: no prospectivity grid cell centroid fell inside these "
            "zones; their existing confidence_score was LEFT UNCHANGED "
            f"(not zeroed, not interpolated): {', '.join(summary['zones_empty'])}"
        )


if __name__ == "__main__":
    _print_summary(import_scores())
