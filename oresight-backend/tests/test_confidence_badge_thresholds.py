"""Pin the zone-confidence badge thresholds to the real score distribution.

The frontend tiers (oresight-frontend/src/lib/confidence.js) once used 0.4 / 0.7,
which the trained models' scores (zone means 0.20-0.41) can never reach, so every
zone showed the same colour. These tests fail if the thresholds are changed
without noticing, or if the score distribution shifts so the UI stops
differentiating zones again.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from geoalchemy2.shape import to_shape
from shapely.geometry import shape
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ReserveZone, Site
from scripts.import_prospectivity_scores import PROSPECTIVITY_DIR, aggregate_zone_score

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIDENCE_JS = REPO_ROOT / "oresight-frontend" / "src" / "lib" / "confidence.js"

PINNED = {"medium": 0.25, "higher": 0.40}


def _thresholds() -> dict[str, float]:
    text = CONFIDENCE_JS.read_text(encoding="utf-8")
    m = re.search(r"CONFIDENCE_TIER_THRESHOLDS\s*=\s*\{\s*medium:\s*([0-9.]+),\s*higher:\s*([0-9.]+)\s*\}", text)
    assert m, "could not parse CONFIDENCE_TIER_THRESHOLDS from confidence.js"
    return {"medium": float(m.group(1)), "higher": float(m.group(2))}


def _tier(score: float, t: dict[str, float]) -> str:
    return "higher" if score >= t["higher"] else "medium" if score >= t["medium"] else "lower"


def _cell_scores() -> list[float]:
    out = []
    for key in ("balaghat", "nagpur", "bhandara"):
        fc = json.loads((PROSPECTIVITY_DIR / f"{key}.geojson").read_text(encoding="utf-8"))
        out += [f["properties"]["ensemble_confidence_score"] for f in fc["features"]]
    return out


def test_thresholds_are_pinned():
    assert _thresholds() == PINNED, (
        "Zone badge thresholds changed. If intentional, re-derive them from the cell-score "
        "percentiles (see confidence.js) and update PINNED here."
    )


def test_cell_distribution_splits_into_a_sensible_share_per_tier():
    scores = _cell_scores()
    t = _thresholds()
    shares = {k: sum(_tier(s, t) == k for s in scores) / len(scores) for k in ("lower", "medium", "higher")}
    assert 0.10 <= shares["higher"] <= 0.25, shares   # top band ~ top 15-20% of real cells
    assert shares["medium"] >= 0.15, shares           # a meaningful middle
    assert shares["lower"] <= 0.70, shares            # bottom band is not "everything"


def test_zone_badges_are_not_all_the_same_tier():
    t = _thresholds()
    db = SessionLocal()
    try:
        keys = {s.id: s.name.lower() for s in db.scalars(select(Site)).all()}
        layers = {
            k: [
                (shape(f["geometry"]).centroid, f["properties"]["ensemble_confidence_score"])
                for f in json.loads((PROSPECTIVITY_DIR / f"{k}.geojson").read_text(encoding="utf-8"))["features"]
            ]
            for k in set(keys.values())
        }
        tiers_by_site: dict[int, set[str]] = {}
        all_tiers: set[str] = set()
        for z in db.scalars(select(ReserveZone)).all():
            score, _ = aggregate_zone_score(to_shape(z.geom), layers[keys[z.site_id]])
            tier = _tier(score, t)
            all_tiers.add(tier)
            tiers_by_site.setdefault(z.site_id, set()).add(tier)
    finally:
        db.close()

    assert len(all_tiers) >= 2, f"every zone shows the same badge tier: {all_tiers}"
    above_lowest = [site for site, tiers in tiers_by_site.items() if tiers != {"lower"}]
    assert len(above_lowest) >= 2, ("fewer than two sites show anything above the lowest tier", tiers_by_site)
