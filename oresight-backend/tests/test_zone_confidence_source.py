"""reserve_zones.confidence_score has ONE source: the trained-model map layer.

It is the mean of `ensemble_confidence_score` over the per-site heatmap cells
whose centroid lies inside each zone (scripts/import_prospectivity_scores.py).
The old kriged surface (build_confidence_surface -> data/reserve_zones.geojson)
disagreed with the heatmap by an order of magnitude and has been retired.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import fmean

import pytest
from geoalchemy2.shape import to_shape
from shapely.geometry import Point, box, shape
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ReserveZone, Site
from scripts.import_prospectivity_scores import (
    PROSPECTIVITY_DIR,
    aggregate_zone_score,
    import_scores,
    load_site_cells,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_aggregation_math_on_hand_built_example():
    zone = box(0, 0, 1, 1)
    cells = [
        (Point(0.25, 0.25), 0.2),
        (Point(0.75, 0.25), 0.4),
        (Point(0.25, 0.75), 0.6),
        (Point(2.0, 2.0), 0.99),   # outside the zone: ignored
        (Point(1.0, 0.5), 0.9),    # exactly on the boundary: excluded (ST_Contains semantics)
    ]
    score, n = aggregate_zone_score(zone, cells)
    assert n == 3
    assert score == 0.4  # (0.2 + 0.4 + 0.6) / 3


def test_aggregation_rounds_to_three_decimals():
    score, n = aggregate_zone_score(box(0, 0, 1, 1), [(Point(0.1, 0.1), 0.1), (Point(0.2, 0.2), 0.1), (Point(0.3, 0.3), 0.2)])
    assert (score, n) == (0.133, 3)


def test_zone_with_no_cells_is_null_not_zero():
    assert aggregate_zone_score(box(10, 10, 11, 11), [(Point(0.5, 0.5), 0.7)]) == (None, 0)
    assert aggregate_zone_score(box(0, 0, 1, 1), []) == (None, 0)


def test_placeholder_or_missing_layer_is_refused(tmp_path):
    placeholder = tmp_path / "nagpur.geojson"
    placeholder.write_text(json.dumps({"site_id": "nagpur", "provenance": {"status": "PLACEHOLDER_SCORES"}, "features": []}))
    with pytest.raises(SystemExit, match="PLACEHOLDER_SCORES"):
        load_site_cells(placeholder, "nagpur")
    with pytest.raises(SystemExit, match="not found"):
        load_site_cells(tmp_path / "missing.geojson", "nagpur")


def test_db_zone_scores_match_hand_computed_aggregate_of_the_real_map_layer():
    """Every zone's stored score == an independent mean over the actual per-site
    heatmap GeoJSON, so the zone panel and the map cannot disagree."""
    import_scores()  # same effect as the rebuild chain's step 5

    db = SessionLocal()
    try:
        sites = {s.id: s.name.lower() for s in db.scalars(select(Site)).all()}
        zones = db.scalars(select(ReserveZone).order_by(ReserveZone.id)).all()
        assert len(zones) == 12

        layers = {}
        for key in set(sites.values()):
            fc = json.loads((PROSPECTIVITY_DIR / f"{key}.geojson").read_text(encoding="utf-8"))
            layers[key] = [
                (shape(f["geometry"]).centroid, f["properties"]["ensemble_confidence_score"])
                for f in fc["features"]
            ]

        for zone in zones:
            poly = to_shape(zone.geom)
            inside = [s for c, s in layers[sites[zone.site_id]] if poly.contains(c)]
            assert inside, f"{zone.zone_name}: no map cells inside"
            expected = round(fmean(inside), 3)
            assert zone.confidence_score == pytest.approx(expected, abs=1e-9), zone.zone_name
            # a mean can never leave the range of the cells it averages
            assert min(inside) <= zone.confidence_score <= max(inside)
    finally:
        db.close()


def test_retired_kriging_pipeline_is_gone():
    for name in ("build_confidence_surface.py", "export_reserve_zones.py", "train_reserve_classifier.py",
                 "data/confidence_surface.npz", "data/reserve_zones.geojson", "models/reserve_classifier.pkl"):
        assert not (REPO_ROOT / name).exists(), f"{name} should have been retired"
