"""
MOIL Reserve Intelligence -- site AOI generator / drift checker.

`data/moil_sites.json` is THE definition of where the three sites are. This
script is what keeps every other copy of that definition honest:

  1. Recomputes each site's bbox from its included mines + `buffer_km` and
     verifies it matches the committed `bbox`. The bbox is committed rather
     than derived at import time so that the number in the file is the number
     in the DB, in GEE and on the map -- and so a diff shows when it moves.
  2. Verifies `combined_bbox`, and that no two site bboxes overlap (a silent
     overlap makes geo_utils.assign_site_id's first-match-wins loop assign
     points to whichever site happens to be declared first).
  3. Writes the generated copies:
       oresight-frontend/src/lib/moil_sites.json   byte-identical
       oresight-backend/app/data/moil_sites.json   byte-identical
       oresight-frontend/public/moil_mines.geojson derived point layer

Run:
    python -m scripts.build_site_aois            # verify + write copies
    python -m scripts.build_site_aois --check    # verify only, non-zero exit
                                                 # on drift (CI / pre-commit)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = REPO_ROOT / "data" / "moil_sites.json"

COPIES = [
    REPO_ROOT / "oresight-frontend" / "src" / "lib" / "moil_sites.json",
    REPO_ROOT / "oresight-backend" / "app" / "data" / "moil_sites.json",
]
MINES_GEOJSON = REPO_ROOT / "oresight-frontend" / "public" / "moil_mines.geojson"

# Degrees per km. Latitude is effectively constant; longitude is taken at each
# site's mid-latitude so the buffer is `buffer_km` on both axes rather than
# `buffer_km`-worth of degrees (which would be ~7% short E-W at 21.5N).
_KM_PER_DEG_LAT = 110.574
_KM_PER_DEG_LON_EQ = 111.320

# Committed coordinates are rounded to this many decimals (~0.1 m).
_ROUND = 6


def load_canonical() -> dict:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))


def compute_bbox(mines: list[dict], buffer_km: float) -> dict:
    """Bounding box of the *included* mines, buffered by `buffer_km` a side."""
    included = [m for m in mines if m.get("included", True)]
    if not included:
        raise ValueError("site has no included mines")

    lats = [m["lat"] for m in included]
    lons = [m["lon"] for m in included]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    d_lat = buffer_km / _KM_PER_DEG_LAT
    mid_lat = (min_lat + max_lat) / 2.0
    d_lon = buffer_km / (_KM_PER_DEG_LON_EQ * math.cos(math.radians(mid_lat)))

    return {
        "min_lat": round(min_lat - d_lat, _ROUND),
        "max_lat": round(max_lat + d_lat, _ROUND),
        "min_lon": round(min_lon - d_lon, _ROUND),
        "max_lon": round(max_lon + d_lon, _ROUND),
    }


def bbox_size_km(bbox: dict) -> tuple[float, float]:
    mid_lat = (bbox["min_lat"] + bbox["max_lat"]) / 2.0
    width = (bbox["max_lon"] - bbox["min_lon"]) * _KM_PER_DEG_LON_EQ * math.cos(
        math.radians(mid_lat)
    )
    height = (bbox["max_lat"] - bbox["min_lat"]) * _KM_PER_DEG_LAT
    return width, height


def _overlaps(a: dict, b: dict) -> bool:
    return (
        a["min_lon"] < b["max_lon"]
        and b["min_lon"] < a["max_lon"]
        and a["min_lat"] < b["max_lat"]
        and b["min_lat"] < a["max_lat"]
    )


def verify(doc: dict) -> list[str]:
    """Return a list of problems; empty means the file is self-consistent."""
    problems: list[str] = []
    buffer_km = doc["buffer_km"]
    sites = doc["sites"]

    for site in sites:
        expected = compute_bbox(site["mines"], buffer_km)
        if site["bbox"] != expected:
            problems.append(
                f"site '{site['key']}': committed bbox {site['bbox']} != "
                f"recomputed {expected} (mines + {buffer_km} km buffer)"
            )

    keys = [s["key"] for s in sites]
    if len(set(keys)) != len(keys):
        problems.append(f"duplicate site keys: {keys}")

    db_ids = [s["db_id"] for s in sites]
    if len(set(db_ids)) != len(db_ids):
        problems.append(f"duplicate db_ids: {db_ids}")

    for i, a in enumerate(sites):
        for b in sites[i + 1:]:
            if _overlaps(a["bbox"], b["bbox"]):
                problems.append(
                    f"site bboxes '{a['key']}' and '{b['key']}' overlap -- "
                    "assign_site_id would assign shared points to whichever "
                    "is declared first"
                )

    expected_combined = [
        round(min(s["bbox"]["min_lon"] for s in sites), _ROUND),
        round(min(s["bbox"]["min_lat"] for s in sites), _ROUND),
        round(max(s["bbox"]["max_lon"] for s in sites), _ROUND),
        round(max(s["bbox"]["max_lat"] for s in sites), _ROUND),
    ]
    if doc["combined_bbox"] != expected_combined:
        problems.append(
            f"combined_bbox {doc['combined_bbox']} != recomputed {expected_combined}"
        )

    return problems


def build_mines_geojson(doc: dict) -> dict:
    """Every mine in the file as a point -- included and excluded alike, so the
    map shows what was left out of each AOI and why."""
    features = []
    for site in doc["sites"]:
        for mine in site["mines"]:
            features.append(_mine_feature(mine, site["key"], site["name"]))
    for mine in doc.get("unassigned_mines", []):
        features.append(_mine_feature(mine, None, None))

    return {
        "type": "FeatureCollection",
        "name": "moil_mines",
        "generated_by": "scripts/build_site_aois.py -- do not edit by hand",
        "features": features,
    }


def _mine_feature(mine: dict, site_key: str | None, site_name: str | None) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [mine["lon"], mine["lat"]]},
        "properties": {
            "name": mine["name"],
            "site_key": site_key,
            "site_name": site_name,
            "confidence": mine["confidence"],
            "in_aoi": bool(mine.get("included", True)),
            "source": mine.get("source", ""),
            "note": mine.get("note", ""),
            "source_urls": mine.get("source_urls", []),
        },
    }


def write_outputs(raw_text: str, doc: dict) -> list[Path]:
    written = []
    for path in COPIES:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw_text, encoding="utf-8", newline="\n")
        written.append(path)

    MINES_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    MINES_GEOJSON.write_text(
        json.dumps(build_mines_geojson(doc), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    written.append(MINES_GEOJSON)
    return written


def check_outputs(raw_text: str, doc: dict) -> list[str]:
    problems = []
    for path in COPIES:
        if not path.exists():
            problems.append(f"missing generated copy: {path.relative_to(REPO_ROOT)}")
        elif path.read_text(encoding="utf-8") != raw_text:
            problems.append(
                f"generated copy out of date: {path.relative_to(REPO_ROOT)} "
                "-- run `python -m scripts.build_site_aois`"
            )

    expected = json.dumps(build_mines_geojson(doc), indent=2) + "\n"
    if not MINES_GEOJSON.exists():
        problems.append(f"missing generated file: {MINES_GEOJSON.relative_to(REPO_ROOT)}")
    elif MINES_GEOJSON.read_text(encoding="utf-8") != expected:
        problems.append(
            f"generated file out of date: {MINES_GEOJSON.relative_to(REPO_ROOT)} "
            "-- run `python -m scripts.build_site_aois`"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify only; do not write. Exits non-zero on any drift.",
    )
    args = parser.parse_args()

    raw_text = CANONICAL.read_text(encoding="utf-8")
    doc = json.loads(raw_text)

    problems = verify(doc)
    if args.check:
        problems += check_outputs(raw_text, doc)

    if problems:
        print(f"FAIL -- {len(problems)} problem(s) in data/moil_sites.json:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"data/moil_sites.json is self-consistent (buffer {doc['buffer_km']} km)\n")
    header = f"{'site':<10}{'lat range':<24}{'lon range':<24}{'km (W x H)':<16}{'centre'}"
    print(header)
    print("-" * len(header))
    for site in doc["sites"]:
        b = site["bbox"]
        w, h = bbox_size_km(b)
        c_lat = (b["min_lat"] + b["max_lat"]) / 2
        c_lon = (b["min_lon"] + b["max_lon"]) / 2
        n_in = sum(1 for m in site["mines"] if m.get("included", True))
        n_out = len(site["mines"]) - n_in
        print(
            f"{site['key']:<10}"
            f"{b['min_lat']:.4f} .. {b['max_lat']:.4f}      "
            f"{b['min_lon']:.4f} .. {b['max_lon']:.4f}      "
            f"{w:6.2f} x {h:6.2f}  "
            f"{c_lat:.4f}, {c_lon:.4f}"
            f"   ({n_in} mine{'s' if n_in != 1 else ''}"
            f"{f', {n_out} excluded' if n_out else ''})"
        )
    print(f"\ncombined_bbox (W,S,E,N): {doc['combined_bbox']}")

    n_unassigned = len(doc.get("unassigned_mines", []))
    if n_unassigned:
        names = ", ".join(m["name"] for m in doc["unassigned_mines"])
        print(f"unassigned mines (markers only, in no AOI): {names}")

    if args.check:
        print("\nGenerated copies are in sync.")
    else:
        print()
        for path in write_outputs(raw_text, doc):
            print(f"wrote {path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
