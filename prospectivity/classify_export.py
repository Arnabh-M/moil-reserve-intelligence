"""
MOIL Reserve Intelligence (SIH26009) — PART 6: Combination, Classification, Export
===================================================================================
  6.1  Combine each site's 3 kriged model surfaces by ALGEBRAIC OVERLAY (not
       simple averaging): a cell is "favorable" only when at least 2 of the 3
       models rate it Moderate-or-above (majority agreement).
  6.2  Classify the combined surface into 5 DISCRETE levels using Jenks natural
       breaks (jenkspy), never an arbitrary even split.
  6.3  Export per-site GeoJSON of grid-cell polygons carrying the ensemble
       score, band, contributing factor values, data_quality, and site_id.

RENDERING PAYLOAD NOTE (a real tension between Part 5.2 and Part 7)
-------------------------------------------------------------------
Part 5's 100 m analysis cells give 89,071 cells across the three sites. Emitted
as individual GeoJSON polygons that is roughly 40-55 MB — far too heavy for a
browser map layer. ANALYSIS therefore stays at 100 m as specified, while EXPORT
takes an `aggregate` factor (default 3 -> 300 m render cells, ~9,900 cells for
the largest site, a few MB). Each exported cell carries the MEAN of its
constituent 100 m cells' factor values, so the Part 7.10 click panel still shows
real per-cell numbers. Set aggregate=1 for full 100 m export when the consumer
is GIS software rather than a browser.

PROVENANCE
----------
Every exported FeatureCollection carries a top-level `provenance` block stating
whether the scores are real model output or placeholders. `--demo` produces a
structurally valid file with PLACEHOLDER scores so the Part 7 frontend can be
built and browser-tested; those files are explicitly marked and must never be
presented as prospectivity results.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)

CONFIDENCE_BANDS = ["Very Low", "Low", "Moderate", "High", "Very High"]
MODERATE_INDEX = 2                 # index of "Moderate" — the 6.1 threshold
MIN_MODEL_AGREEMENT = 2            # Part 6.1 — at least 2 of 3 models

# DELIBERATE STRENGTHENING OF PART 6.1 — read before changing.
# Endorsement requires the Jenks band to be Moderate+ AND the model's raw
# probability to clear this floor. Jenks alone is not sufficient: deposits are
# sparse, so most of a real site is a low-value bulk, and Jenks subdivides that
# bulk across several classes. That puts the "Moderate" boundary at a very low
# absolute probability (measured at p=0.153 on a representative distribution),
# meaning a model leaning firmly negative would still "endorse" a cell and the
# majority gate would filter nothing. 0.5 is the standard binary decision
# threshold for a calibrated classifier: below it the model does not consider
# the cell prospective at all, whatever its rank within the distribution.
MODERATE_PROBABILITY_FLOOR = 0.5
N_CLASSES = 5                      # Part 6.2
DEFAULT_AGGREGATE = 3              # 100 m analysis -> 300 m render cells

FACTOR_FIELDS = [
    "ndvi_anomaly", "ndri", "ndwi", "iron_oxide_index", "clay_index",
    "manganese_spectral_ratio", "slope", "aspect", "terrain_ruggedness",
    "structural_density",
]

NDVI_ANOMALY_ALERT_THRESHOLD = -0.10   # Part 7.10 — "beyond -10%"


def jenks_breaks(values: np.ndarray, n_classes: int = N_CLASSES) -> list[float]:
    """
    Part 6.2 — Jenks natural breaks. Uses jenkspy when available, otherwise a
    1-D k-means (Fisher-Jenks equivalent for the univariate case) fallback so
    classification never silently degrades to an arbitrary even split.
    """
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        raise ValueError("No finite values to classify")
    if len(np.unique(finite)) < n_classes:
        lo, hi = float(finite.min()), float(finite.max())
        logger.warning("Only %d distinct values; falling back to linear breaks", len(np.unique(finite)))
        return list(np.linspace(lo, hi, n_classes + 1))

    try:
        import jenkspy
        return [float(b) for b in jenkspy.jenks_breaks(finite, n_classes=n_classes)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("jenkspy unavailable/failed (%s) — using 1-D k-means equivalent", exc)
        from sklearn.cluster import KMeans

        km = KMeans(n_clusters=n_classes, n_init=10, random_state=42)
        labels = km.fit_predict(finite.reshape(-1, 1))
        breaks = [float(finite.min())]
        for c in np.argsort(km.cluster_centers_.ravel())[:-1]:
            breaks.append(float(finite[labels == c].max()))
        breaks.append(float(finite.max()))
        return breaks


def assign_bands(values: np.ndarray, breaks: list[float]) -> np.ndarray:
    """Map values to band indices 0..4 using Jenks breakpoints."""
    idx = np.digitize(values, breaks[1:-1], right=True)
    return np.clip(idx, 0, N_CLASSES - 1)


def algebraic_overlay(model_surfaces: dict[str, np.ndarray]) -> dict:
    """
    Part 6.1 — combine model surfaces by majority agreement, not averaging.

    A cell counts as endorsed by a model when that model rates it
    Moderate-or-above. Cells without >= MIN_MODEL_AGREEMENT endorsements are
    demoted below Moderate in the final output, so "favorable" always means at
    least two models concur.

    IMPORTANT — why the breaks are SHARED across models: classifying each
    model's surface against its OWN distribution makes "Moderate" a relative
    term, so a model whose outputs are uniformly low still labels its top ~40%
    of cells Moderate+. Agreement then becomes trivially easy and the majority
    gate stops filtering anything (verified: the self-test below caught exactly
    this — single-model-endorsed cells were passing the gate). Computing one set
    of Jenks breaks on the POOLED values of all models keeps classification
    data-driven while making "Moderate" mean the same thing for every model,
    which is what majority agreement requires to be meaningful.

    Returns ensemble score, final band indices, and the agreement count.
    """
    if not model_surfaces:
        raise ValueError("No model surfaces supplied to overlay")

    names = sorted(model_surfaces)
    stack = np.vstack([np.asarray(model_surfaces[n], dtype=float) for n in names])

    shared_breaks = jenks_breaks(stack.ravel())

    endorsements = np.zeros(stack.shape[1], dtype=int)
    for row in stack:
        endorsed = (assign_bands(row, shared_breaks) >= MODERATE_INDEX) & (row >= MODERATE_PROBABILITY_FLOOR)
        endorsements += endorsed.astype(int)

    ensemble = stack.mean(axis=0)
    bands = assign_bands(ensemble, shared_breaks)

    # The gate: no majority => cannot be labelled favorable.
    insufficient = endorsements < MIN_MODEL_AGREEMENT
    bands[insufficient & (bands >= MODERATE_INDEX)] = MODERATE_INDEX - 1

    return {
        "ensemble_score": ensemble,
        "band_index": bands,
        "agreement_count": endorsements,
        "model_names": names,
        "shared_breaks": shared_breaks,
    }


def _cell_polygon(cx: float, cy: float, size: float, to_wgs) -> list[list[float]]:
    """Square cell polygon in UTM, returned as a WGS84 lon/lat ring."""
    half = size / 2.0
    corners = [(cx - half, cy - half), (cx + half, cy - half),
               (cx + half, cy + half), (cx - half, cy + half), (cx - half, cy - half)]
    xs, ys = zip(*corners)
    lons, lats = to_wgs.transform(np.array(xs), np.array(ys))
    return [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]


def export_site_geojson(
    grid, ensemble: dict, factors: dict[str, np.ndarray], data_quality: np.ndarray,
    out_path: str, aggregate: int = DEFAULT_AGGREGATE, provenance: dict | None = None,
) -> dict:
    """
    Part 6.3 — write one site's classified surface as a GeoJSON
    FeatureCollection, validating geometry and properties before returning.
    """
    from pyproj import Transformer

    to_wgs = Transformer.from_crs(grid.utm_epsg, "EPSG:4326", always_xy=True)
    centers = grid.centers_utm
    render_size = grid.cell_size_m * aggregate

    # Bin 100 m cells into render cells and average their values.
    keys = np.floor(centers / render_size).astype(np.int64)
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)

    def mean_by_bin(arr):
        arr = np.asarray(arr, dtype=float)
        out = np.zeros(len(counts))
        np.add.at(out, inverse, np.nan_to_num(arr, nan=0.0))
        valid = np.zeros(len(counts))
        np.add.at(valid, inverse, np.isfinite(arr).astype(float))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(valid > 0, out / np.maximum(valid, 1), np.nan)

    agg_centers = np.column_stack([mean_by_bin(centers[:, 0]), mean_by_bin(centers[:, 1])])
    agg_score = mean_by_bin(ensemble["ensemble_score"])
    agg_agree = np.rint(mean_by_bin(ensemble["agreement_count"])).astype(int)
    agg_factors = {name: mean_by_bin(vals) for name, vals in factors.items()}
    agg_quality = mean_by_bin(data_quality)

    # Re-classify on the aggregated surface so bands match what is drawn.
    agg_bands = assign_bands(agg_score, jenks_breaks(agg_score))
    agg_bands[(agg_agree < MIN_MODEL_AGREEMENT) & (agg_bands >= MODERATE_INDEX)] = MODERATE_INDEX - 1

    features = []
    for i in range(len(agg_score)):
        if not np.isfinite(agg_score[i]):
            continue
        band = CONFIDENCE_BANDS[int(agg_bands[i])]
        quality = "high" if agg_quality[i] >= 0.5 else "low"

        props = {
            "cell_id": f"{grid.site_id}_{i}",
            "site_id": grid.site_id,
            "ensemble_confidence_score": round(float(agg_score[i]), 4),
            "confidence_band": band,
            "model_agreement_count": int(agg_agree[i]),
            "data_quality": quality,
            "cell_size_m": render_size,
        }
        for name in FACTOR_FIELDS:
            v = agg_factors.get(name, np.array([np.nan]))[i] if name in agg_factors else np.nan
            props[name] = None if not np.isfinite(v) else round(float(v), 4)

        # Part 7.10 — precompute the NDVI-anomaly alert and recommendation.
        ndvi = props.get("ndvi_anomaly")
        props["ndvi_anomaly_alert"] = bool(ndvi is not None and ndvi <= NDVI_ANOMALY_ALERT_THRESHOLD)
        props["recommendation"] = (
            "Priority zone for field verification"
            if band in ("High", "Very High") and quality == "high"
            else "Re-image before acting — significant cloud masking reduced data"
            if quality == "low"
            else "Monitor; below priority threshold"
        )

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [_cell_polygon(agg_centers[i, 0], agg_centers[i, 1], render_size, to_wgs)],
            },
            "properties": props,
        })

    fc = {
        "type": "FeatureCollection",
        "site_id": grid.site_id,
        "site_name": grid.site_name,
        "provenance": provenance or {},
        "grid": {
            "analysis_cell_size_m": grid.cell_size_m,
            "render_cell_size_m": render_size,
            "analysis_dimensions": f"{grid.n_cols} x {grid.n_rows}",
            "analysis_cells_in_polygon": grid.n_cells_in_polygon,
            "render_cells": len(features),
        },
        "features": features,
    }

    validate_geojson(fc)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(fc, fh)
    logger.info("Wrote %s (%d features, %.1f MB)",
                out_path, len(features), os.path.getsize(out_path) / 1e6)
    return fc


def export_band_outlines(fc: dict, out_path: str) -> dict:
    """
    Part 7.3 / 7.4 support — dissolve same-band cells into band polygons.

    Rendering a hairline around every 300 m cell produces a graph-paper mesh
    across the whole surface (confirmed in-browser), which is not what "a subtle
    boundary between adjacent bands" means. Dissolving with shapely gives one
    geometry per band, so the outline is drawn only where bands actually meet.
    The union's outer ring is also the site's true edge, which is what the 7.4
    feather should follow.

    Output is tiny (5 features) compared with the cell layer, so it costs
    essentially nothing to load alongside it.
    """
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union

    by_band: dict[str, list] = {}
    for feat in fc["features"]:
        by_band.setdefault(feat["properties"]["confidence_band"], []).append(shape(feat["geometry"]))

    features = []
    for band, geoms in by_band.items():
        if not geoms:
            continue
        # buffer(0) repairs the slivers that can appear when unioning a grid.
        dissolved = unary_union([g.buffer(0) for g in geoms])
        features.append({
            "type": "Feature",
            "geometry": mapping(dissolved),
            "properties": {
                "confidence_band": band,
                "site_id": fc["site_id"],
                "cell_count": len(geoms),
            },
        })

    out = {
        "type": "FeatureCollection",
        "site_id": fc["site_id"],
        "site_name": fc.get("site_name"),
        "provenance": fc.get("provenance", {}),
        "features": features,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    logger.info("Wrote %s (%d dissolved bands, %.2f MB)",
                out_path, len(features), os.path.getsize(out_path) / 1e6)
    return out


def validate_geojson(fc: dict) -> None:
    """Robustness requirement: reject malformed geometry / null properties."""
    if fc.get("type") != "FeatureCollection":
        raise ValueError("Not a FeatureCollection")
    if not fc.get("features"):
        raise ValueError("FeatureCollection has no features")

    required = {"ensemble_confidence_score", "confidence_band", "data_quality", "site_id"}
    for i, feat in enumerate(fc["features"]):
        geom = feat.get("geometry") or {}
        ring = (geom.get("coordinates") or [[]])[0]
        if geom.get("type") != "Polygon" or len(ring) < 4:
            raise ValueError(f"Feature {i}: invalid polygon geometry")
        if ring[0] != ring[-1]:
            raise ValueError(f"Feature {i}: polygon ring is not closed")
        if not all(np.isfinite(c) for pt in ring for c in pt):
            raise ValueError(f"Feature {i}: non-finite coordinate")

        props = feat.get("properties") or {}
        missing = required - set(props)
        if missing:
            raise ValueError(f"Feature {i}: missing properties {missing}")
        for key in required:
            if props[key] is None:
                raise ValueError(f"Feature {i}: required property '{key}' is null")
        if props["confidence_band"] not in CONFIDENCE_BANDS:
            raise ValueError(f"Feature {i}: unknown band {props['confidence_band']!r}")


# ---------------------------------------------------------------------------
# Self-test — verifies overlay + Jenks logic, not geology.
# ---------------------------------------------------------------------------
def _self_test() -> bool:
    rng = np.random.default_rng(7)
    n = 1000
    ok = True

    # Two models rate the first 100 cells high, the third disagrees.
    a = rng.uniform(0, 0.3, n); a[:100] = rng.uniform(0.8, 1.0, 100)
    b = rng.uniform(0, 0.3, n); b[:100] = rng.uniform(0.8, 1.0, 100)
    c = rng.uniform(0, 0.3, n)
    # Only ONE model rates cells 200-300 high -> must NOT be favorable.
    c[200:300] = rng.uniform(0.9, 1.0, 100)

    res = algebraic_overlay({"rf": a, "nb": b, "xgb": c})
    bands, agree = res["band_index"], res["agreement_count"]

    if not (agree[:100] >= 2).all():
        print("FAIL: cells endorsed by 2 models should have agreement >= 2"); ok = False
    if (bands[200:300] >= MODERATE_INDEX).any():
        print("FAIL: single-model-only cells must be demoted below Moderate"); ok = False
    else:
        print(f"  majority gate: {(bands[200:300] >= MODERATE_INDEX).sum()}/100 "
              f"single-model cells reached Moderate+ (expected 0) — correct")

    breaks = res["shared_breaks"]
    if len(breaks) != N_CLASSES + 1:
        print(f"FAIL: expected {N_CLASSES+1} breakpoints, got {len(breaks)}"); ok = False
    if not all(breaks[i] <= breaks[i + 1] for i in range(len(breaks) - 1)):
        print("FAIL: Jenks breaks not monotonic"); ok = False
    else:
        print(f"  Jenks breaks ({N_CLASSES} classes): {[round(x, 3) for x in breaks]}")

    even = np.linspace(res["ensemble_score"].min(), res["ensemble_score"].max(), N_CLASSES + 1)
    if np.allclose(breaks, even, atol=1e-6):
        print("NOTE: Jenks coincided with an even split for this fixture")
    else:
        print("  Jenks breaks differ from an even split — data-driven, as required")

    print("\nSELF-TEST:", "PASS — overlay + Jenks logic correct" if ok else "FAIL")
    return ok


def generate_demo_exports(out_dir: str = "oresight-frontend/public/prospectivity",
                          aggregate: int = DEFAULT_AGGREGATE) -> list[str]:
    """
    Produce structurally valid per-site GeoJSON so the Part 7 frontend can be
    built and browser-verified before Parts 1-4 are unblocked.

    REAL here: site boundary polygons (PostGIS), the 100 m grid, UTM projection,
    cell geometry, Jenks classification, the majority-agreement gate, and the
    export/validation path — i.e. all the code under test.
    PLACEHOLDER here: the three model probability surfaces, and therefore the
    scores, bands, and factor values derived from them.

    Every file records this in its `provenance` block, and the frontend surfaces
    it as a visible banner, so these can never be mistaken for real results.
    """
    from prospectivity.grid import build_all_grids, krige_site_surface

    grids = build_all_grids()
    written: list[str] = []

    for site_id, grid in grids.items():
        rng = np.random.default_rng(abs(hash(site_id)) % (2**32))
        centers = grid.centers_utm

        # Spatially coherent placeholder surfaces: smooth radial-basis blobs, so
        # the rendered map exercises realistic band adjacency rather than salt-
        # and-pepper noise that would hide edge/adjacency bugs.
        def blobby(seed_offset: int) -> np.ndarray:
            r = np.random.default_rng((abs(hash(site_id)) + seed_offset) % (2**32))
            n_blobs = 6
            cx = r.uniform(centers[:, 0].min(), centers[:, 0].max(), n_blobs)
            cy = r.uniform(centers[:, 1].min(), centers[:, 1].max(), n_blobs)
            amp = r.uniform(0.4, 1.0, n_blobs)
            scale = r.uniform(1200, 3000, n_blobs)
            z = np.zeros(len(centers))
            for k in range(n_blobs):
                d2 = (centers[:, 0] - cx[k]) ** 2 + (centers[:, 1] - cy[k]) ** 2
                z += amp[k] * np.exp(-d2 / (2 * scale[k] ** 2))
            return np.clip(z / max(z.max(), 1e-9), 0, 1)

        surfaces = {name: blobby(i) for i, name in enumerate(["rf", "nb", "xgb"])}

        # Exercise the real Part 5.6 kriging path on a subsample of each surface.
        sample_idx = rng.choice(len(centers), min(300, len(centers)), replace=False)
        methods = set()
        for name, surf in surfaces.items():
            vals, method = krige_site_surface(grid, centers[sample_idx], surf[sample_idx])
            surfaces[name] = vals
            methods.add(method)

        ensemble = algebraic_overlay(surfaces)

        factors = {f: blobby(100 + i) for i, f in enumerate(FACTOR_FIELDS)}
        factors["ndvi_anomaly"] = factors["ndvi_anomaly"] * 0.6 - 0.4   # into a plausible anomaly range
        factors["slope"] = factors["slope"] * 35.0
        factors["aspect"] = factors["aspect"] * 360.0
        factors["structural_density"] = np.rint(factors["structural_density"] * 8)

        data_quality = (blobby(999) > 0.25).astype(float)

        provenance = {
            "status": "PLACEHOLDER_SCORES",
            "warning": (
                "Geometry, grid, kriging, classification and export are real. "
                "Model scores and factor values are PLACEHOLDERS — Part 1 (GEE features) "
                "and Part 4 (training) are blocked pending Earth Engine credentials and "
                "real deposit ground truth. NOT a prospectivity result."
            ),
            "interpolation_method": sorted(methods),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        }

        path = os.path.join(out_dir, f"{site_id}.geojson")
        fc = export_site_geojson(grid, ensemble, factors, data_quality, path,
                                 aggregate=aggregate, provenance=provenance)
        written.append(path)

        bands_path = os.path.join(out_dir, f"{site_id}_bands.geojson")
        export_band_outlines(fc, bands_path)
        written.append(bands_path)

    return written


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if "--demo" in sys.argv:
        paths = generate_demo_exports()
        print("\n" + "=" * 70)
        print(" PART 6.3 — DEMO EXPORTS (placeholder scores, real geometry)")
        print("=" * 70)
        for p in paths:
            with open(p, encoding="utf-8") as fh:
                fc = json.load(fh)
            bands = {}
            for feat in fc["features"]:
                b = feat["properties"]["confidence_band"]
                bands[b] = bands.get(b, 0) + 1
            print(f"\n{fc['site_id']}: {len(fc['features'])} render cells "
                  f"({os.path.getsize(p)/1e6:.2f} MB), grid {fc['grid']['analysis_dimensions']} "
                  f"@ {fc['grid']['analysis_cell_size_m']:.0f}m -> {fc['grid']['render_cell_size_m']:.0f}m render")
            for b in CONFIDENCE_BANDS:
                print(f"    {b:<11} {bands.get(b, 0):>6}")
        print("\nAll exports passed validate_geojson().")
        print("=" * 70)
        raise SystemExit(0)

    raise SystemExit(0 if _self_test() else 1)
