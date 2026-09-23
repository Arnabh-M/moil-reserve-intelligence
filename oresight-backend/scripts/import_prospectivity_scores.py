"""Set reserve_zones.confidence_score from the trained-model map layer.

ONE SOURCE OF TRUTH. The number stored here (and therefore served by
GET /reserve-zones, shown in the zone detail panel and averaged into
/sites and /kpi/summary) is the same `ensemble_confidence_score` the map
heatmap draws, aggregated up to each zone polygon:

    repo-root prospectivity.classify_export
        -> oresight-frontend/public/prospectivity/{site}.geojson
        -> this script -> reserve_zones.confidence_score

The per-site GeoJSONs are the committed output of the trained per-site
models (prospectivity/train_models.py: the 9 Sentinel-2 / DEM features plus
structural features, scored by RF + XGBoost + Naive Bayes). The old kriged
surface (build_confidence_surface -> data/reserve_zones.geojson) used
synthetic fields, not the real features, and has been retired; it is not read
anywhere.

What it does, per Postgres ReserveZone row:
  1. Take every map cell of that site whose centroid falls INSIDE the zone's
     `geom` polygon (boundary-exclusive, like PostGIS ST_Contains).
  2. confidence_score = arithmetic MEAN of those cells'
     `ensemble_confidence_score`, rounded to 3 dp. Render cells are equal
     size, so this is area-weighted, and it is exactly the set of cells the
     heatmap draws inside the zone. (Cell scores are right-skewed, so the mean
     sits above the median; the mean is used so that the zone number is the
     average colour the map shows there.)
  3. A zone with ZERO cells inside gets confidence_score = NULL and a logged
     reason. No score is invented, and the old value is not kept (it came from
     a different, retired pipeline).

Refuses to run on a GeoJSON whose provenance is not TRAINED_MODEL_SCORES
(e.g. the `--demo` placeholder scores).

Idempotent: same GeoJSONs in, same scores out. No inserts, deletes or
geometry changes.

Run from oresight-backend/, AFTER scripts.import_p2_data (which overwrites
confidence_score with a placeholder ratio every run) and BEFORE the scenario
seeds:

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

from app.db import SessionLocal  # noqa: E402
from app.models import ReserveZone, Site  # noqa: E402

PROSPECTIVITY_DIR = REPO_ROOT / "oresight-frontend" / "public" / "prospectivity"
SCORE_FIELD = "ensemble_confidence_score"
REQUIRED_STATUS = "TRAINED_MODEL_SCORES"


def load_site_cells(path: Path, site_key: str) -> list[tuple[Point, float]]:
    """[(centroid, ensemble_confidence_score), ...] for one site's map layer.

    Raises SystemExit if the file is missing or is not trained-model output.
    """
    if not path.exists():
        raise SystemExit(
            f"prospectivity map layer not found: {path}\n"
            "Generate it first: python -m prospectivity.train_models --allow-synthetic && "
            "python -m prospectivity.classify_export (repo root)."
        )
    with path.open(encoding="utf-8") as f:
        fc = json.load(f)

    status = (fc.get("provenance") or {}).get("status")
    if status != REQUIRED_STATUS:
        raise SystemExit(
            f"{path.name}: provenance status is {status!r}, expected {REQUIRED_STATUS!r}. "
            "Refusing to write placeholder scores onto reserve zones."
        )
    if fc.get("site_id") != site_key:
        raise SystemExit(f"{path.name}: site_id is {fc.get('site_id')!r}, expected {site_key!r}")

    return [
        (shape(feat["geometry"]).centroid, float(feat["properties"][SCORE_FIELD]))
        for feat in fc.get("features", [])
    ]


def aggregate_zone_score(polygon, cells: list[tuple[Point, float]]) -> tuple[float | None, int]:
    """(mean score rounded to 3 dp, number of cells) for cells whose centroid is
    inside `polygon`; (None, 0) when no cell is inside."""
    scores = [score for centroid, score in cells if polygon.contains(centroid)]
    if not scores:
        return None, 0
    return round(fmean(scores), 3), len(scores)


def import_scores(prospectivity_dir: Path = PROSPECTIVITY_DIR) -> dict:
    db = SessionLocal()
    try:
        sites = {site.id: site.name.lower() for site in db.scalars(select(Site)).all()}
        cells_by_site = {
            site_id: load_site_cells(prospectivity_dir / f"{key}.geojson", key)
            for site_id, key in sites.items()
        }

        zones = db.scalars(
            select(ReserveZone).order_by(ReserveZone.site_id, ReserveZone.id)
        ).all()

        rows: list[dict] = []
        empty_zones: list[str] = []
        now = datetime.now(timezone.utc)

        for zone in zones:
            polygon = to_shape(zone.geom)
            after, n_cells = aggregate_zone_score(polygon, cells_by_site.get(zone.site_id, []))
            before = zone.confidence_score
            name = zone.zone_name or f"zone#{zone.id}"
            if after is None:
                empty_zones.append(name)
            zone.confidence_score = after
            zone.last_updated = now
            rows.append(
                {
                    "id": zone.id,
                    "site_id": zone.site_id,
                    "zone_name": zone.zone_name,
                    "before": before,
                    "after": after,
                    "cells": n_cells,
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
        "map_cells": sum(len(c) for c in cells_by_site.values()),
        "zones_total": len(zones),
        "zones_scored": len(zones) - len(empty_zones),
        "zones_changed": sum(1 for r in rows if r["changed"]),
        "zones_empty": empty_zones,
        "rows": rows,
    }


def _print_summary(summary: dict) -> None:
    print("\nOreSight zone confidence import (source: trained-model map layer)")
    print("-" * 72)
    print(
        f"  map cells loaded: {summary['map_cells']}   "
        f"zones: {summary['zones_total']}   "
        f"scored: {summary['zones_scored']}   "
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
            "\n  WARNING: no map cell centroid fell inside these zones, so their "
            "confidence_score was set to NULL (not zeroed, not interpolated, not "
            f"carried over): {', '.join(summary['zones_empty'])}"
        )


if __name__ == "__main__":
    _print_summary(import_scores())
