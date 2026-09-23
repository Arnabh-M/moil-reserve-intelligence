"""The site AOIs are defined once, in data/moil_sites.json, and copied to the
backend and the frontend by `python -m scripts.build_site_aois`. These tests
are what stops those copies drifting back apart.

The repo used to carry two incompatible box families for the same three sites
(a ~33 km set in geo_utils/generate_datasets and a ~20 km set in seed_dev and
the frontend), and nothing failed when they disagreed. That is the failure
mode these assertions cover.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

CANONICAL = REPO_ROOT / "data" / "moil_sites.json"
BACKEND_COPY = BACKEND_ROOT / "app" / "data" / "moil_sites.json"
FRONTEND_COPY = REPO_ROOT / "oresight-frontend" / "src" / "lib" / "moil_sites.json"
MINES_GEOJSON = REPO_ROOT / "oresight-frontend" / "public" / "moil_mines.geojson"

# Only meaningful in a full checkout; a backend-only deployment has the copy
# under app/data/ but not the repo root.
requires_repo = pytest.mark.skipif(
    not CANONICAL.exists(), reason="repo-root data/moil_sites.json not present"
)


@requires_repo
def test_backend_copy_matches_canonical():
    assert BACKEND_COPY.exists(), (
        "oresight-backend/app/data/moil_sites.json is missing -- run "
        "`python -m scripts.build_site_aois` from the repo root."
    )
    assert BACKEND_COPY.read_text(encoding="utf-8") == CANONICAL.read_text(
        encoding="utf-8"
    ), "backend copy of moil_sites.json has drifted -- run `python -m scripts.build_site_aois`"


@requires_repo
def test_frontend_copy_matches_canonical():
    assert FRONTEND_COPY.exists(), (
        "oresight-frontend/src/lib/moil_sites.json is missing -- run "
        "`python -m scripts.build_site_aois` from the repo root."
    )
    assert FRONTEND_COPY.read_text(encoding="utf-8") == CANONICAL.read_text(
        encoding="utf-8"
    ), "frontend copy of moil_sites.json has drifted -- run `python -m scripts.build_site_aois`"


@requires_repo
def test_generated_artifacts_are_current():
    """Full generator check: bboxes recompute, no AOIs overlap, every generated
    file (including public/moil_mines.geojson) is up to date."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.build_site_aois", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "scripts/build_site_aois.py --check failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_seed_specs_match_the_json():
    """seed_dev.SITE_SPECS -- and therefore every `sites.geom` polygon written
    to Postgres -- is the AOI from the file, not a second set of numbers."""
    from app import seed_dev

    doc = json.loads(BACKEND_COPY.read_text(encoding="utf-8"))
    by_key = {s["key"]: s for s in doc["sites"]}

    assert len(seed_dev.SITE_SPECS) == len(by_key)
    for spec in seed_dev.SITE_SPECS:
        site = by_key[spec["key"]]
        assert spec["name"] == site["name"]
        assert spec["min_lat"] == site["bbox"]["min_lat"]
        assert spec["max_lat"] == site["bbox"]["max_lat"]
        assert spec["min_lon"] == site["bbox"]["min_lon"]
        assert spec["max_lon"] == site["bbox"]["max_lon"]
        # Centroid is the box centre.
        assert spec["lat"] == pytest.approx(
            (site["bbox"]["min_lat"] + site["bbox"]["max_lat"]) / 2
        )
        assert spec["lon"] == pytest.approx(
            (site["bbox"]["min_lon"] + site["bbox"]["max_lon"]) / 2
        )


def test_every_included_mine_is_inside_its_site_box():
    """The whole point of the AOIs: each site's box contains its own mines.
    Sites used to be centred on Nagpur city and Bhandara town, with no MOIL
    mine inside either box."""
    doc = json.loads(BACKEND_COPY.read_text(encoding="utf-8"))

    for site in doc["sites"]:
        b = site["bbox"]
        for mine in site["mines"]:
            inside = (
                b["min_lat"] <= mine["lat"] <= b["max_lat"]
                and b["min_lon"] <= mine["lon"] <= b["max_lon"]
            )
            if mine.get("included", True):
                assert inside, f"{mine['name']} is outside the {site['key']} AOI"
            else:
                assert not inside, (
                    f"{mine['name']} is marked excluded but falls inside the "
                    f"{site['key']} AOI -- either include it or move the box"
                )


def test_reserve_zone_blocks_stay_inside_their_site():
    """Zone blocks are placed as a fraction of each site's half-extent. With a
    fixed degree offset they hung outside the smaller AOIs, which left the map
    showing blocks floating off the site and import_prospectivity_scores with
    no grid cells inside them."""
    from app import seed_dev

    for spec in seed_dev.SITE_SPECS:
        for template in seed_dev.ZONE_TEMPLATES:
            min_lon, min_lat, max_lon, max_lat = seed_dev.zone_bbox(spec, template)
            assert spec["min_lon"] <= min_lon and max_lon <= spec["max_lon"], (
                f"{spec['name']} {template['suffix']} is outside its site in longitude"
            )
            assert spec["min_lat"] <= min_lat and max_lat <= spec["max_lat"], (
                f"{spec['name']} {template['suffix']} is outside its site in latitude"
            )


def test_reserve_zone_blocks_do_not_overlap():
    from app import seed_dev

    for spec in seed_dev.SITE_SPECS:
        boxes = [seed_dev.zone_bbox(spec, t) for t in seed_dev.ZONE_TEMPLATES]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                overlap = (
                    a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                )
                assert not overlap, f"overlapping reserve-zone blocks in {spec['name']}"


@requires_repo
def test_site_boxes_are_the_mine_bounds_plus_the_buffer():
    """Recompute the buffer independently of scripts/build_site_aois.py, so a
    bug in the generator cannot certify itself."""
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    buffer_km = doc["buffer_km"]

    for site in doc["sites"]:
        included = [m for m in site["mines"] if m.get("included", True)]
        lats = [m["lat"] for m in included]
        lons = [m["lon"] for m in included]
        mid_lat = (min(lats) + max(lats)) / 2

        # 1 deg latitude ~ 110.574 km; 1 deg longitude ~ 111.320*cos(lat) km.
        d_lat = buffer_km / 110.574
        d_lon = buffer_km / (111.320 * math.cos(math.radians(mid_lat)))

        b = site["bbox"]
        assert b["min_lat"] == pytest.approx(min(lats) - d_lat, abs=1e-6)
        assert b["max_lat"] == pytest.approx(max(lats) + d_lat, abs=1e-6)
        assert b["min_lon"] == pytest.approx(min(lons) - d_lon, abs=1e-6)
        assert b["max_lon"] == pytest.approx(max(lons) + d_lon, abs=1e-6)


@requires_repo
def test_mines_geojson_covers_every_mine():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    geojson = json.loads(MINES_GEOJSON.read_text(encoding="utf-8"))

    expected = {m["name"] for s in doc["sites"] for m in s["mines"]}
    expected |= {m["name"] for m in doc.get("unassigned_mines", [])}
    actual = {f["properties"]["name"] for f in geojson["features"]}
    assert actual == expected


# ---------------------------------------------------------------------------
# Regression: re-seeding an existing database must correct stale geometry.
#
# seed_dev is skip-if-exists on (name) for sites and (site_id, zone_name) for
# reserve zones. That used to mean the geometry of an ALREADY-SEEDED row was
# never revisited: after the AOIs moved onto the real mines, rebuild_demo_db
# ran all ten steps successfully and left Postgres holding the old boxes
# centred on Nagpur city -- a silent fourth copy of the site definition, with
# nothing failing to indicate it.
# ---------------------------------------------------------------------------


def _postgres_reachable() -> bool:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    from app.config import get_settings

    try:
        engine = create_engine(
            get_settings().DATABASE_URL, connect_args={"connect_timeout": 3}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture
def db_session():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable")
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_seeded_site_geometry_matches_the_json(db_session):
    """What the DB actually holds is the AOI from the file."""
    from sqlalchemy import func, select

    from app import seed_dev
    from app.models import Site

    for spec in seed_dev.SITE_SPECS:
        site = db_session.scalar(select(Site).where(Site.name == spec["name"]))
        assert site is not None, f"{spec['name']} is not seeded"
        expected = seed_dev._bbox_polygon(
            spec["min_lon"], spec["min_lat"], spec["max_lon"], spec["max_lat"]
        )
        assert db_session.scalar(select(func.ST_Equals(site.geom, expected))), (
            f"{spec['name']}.geom in Postgres does not match data/moil_sites.json"
        )


def test_reseeding_rewrites_a_stale_site_polygon(db_session):
    """Deliberately corrupt a site's polygon, re-seed, and confirm it is fixed
    (and that the fix is a no-op when the geometry is already correct)."""
    from sqlalchemy import func, select

    from app import seed_dev
    from app.models import Site

    spec = seed_dev.SITE_SPECS[0]
    site = db_session.scalar(select(Site).where(Site.name == spec["name"]))
    correct = seed_dev._bbox_polygon(
        spec["min_lon"], spec["min_lat"], spec["max_lon"], spec["max_lat"]
    )

    # The pre-fix Balaghat box: a square around the wrong centre.
    site.geom = seed_dev._bbox_polygon(80.10, 21.71, 80.28, 21.89)
    db_session.flush()
    assert not db_session.scalar(select(func.ST_Equals(site.geom, correct)))

    returned, created = seed_dev._get_or_create_site(db_session, spec)
    assert created is False
    assert db_session.scalar(select(func.ST_Equals(returned.geom, correct))), (
        "_get_or_create_site left a stale polygon in place"
    )

    # Idempotent: a second pass over correct geometry changes nothing.
    seed_dev._get_or_create_site(db_session, spec)
    assert db_session.scalar(select(func.ST_Equals(returned.geom, correct)))
    # db_session fixture rolls back, so the real row is untouched.


def test_seeded_reserve_zones_sit_inside_their_site(db_session):
    from sqlalchemy import func, select

    from app.models import ReserveZone, Site

    rows = db_session.execute(
        select(ReserveZone.zone_name, func.ST_Within(ReserveZone.geom, Site.geom))
        .join(Site, Site.id == ReserveZone.site_id)
    ).all()

    assert rows, "no reserve zones seeded"
    outside = [name for name, inside in rows if not inside]
    assert not outside, f"reserve zones outside their site polygon: {outside}"
