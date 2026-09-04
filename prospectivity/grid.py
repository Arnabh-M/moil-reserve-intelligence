"""
MOIL Reserve Intelligence (SIH26009) — PART 5: Per-Site Fixed-Size Grid
========================================================================
  5.1  Retrieve each site's real boundary polygon from PostGIS.
  5.2  FIXED CELL SIZE of 100 m x 100 m for all sites (a physical size, close
       to the cited study's 130 m analysis unit) — NOT a fixed row/col count.
  5.3  Derive each site's grid DIMENSIONS from its real extent in meters, so
       differently-sized sites get different row/column counts.
  5.4  Aggregate native-resolution features into each 100 m cell.
  5.5  Score each cell with that site's trained models.
  5.6  Krige each site's cell probabilities into a continuous surface WITHIN
       that site's boundary only — never across sites or the gaps between them.

WHAT THIS REPLACES
------------------
build_confidence_surface.py used a fixed 100x100 grid stretched over the
COMBINED bbox of all three sites. Consequences:
  * Cell size was an accident of the bbox: ~1.46 km E-W by ~1.12 km N-S
    (non-square, and ~14x coarser than intended) — the direct cause of the
    map's blurry, low-detail appearance.
  * The grid spanned the empty space BETWEEN sites, so kriging interpolated
    across ~100 km of terrain containing no data, then export_reserve_zones.py
    discarded most of those cells.
This module fixes both: real per-site extents, true 100 m cells, and kriging
strictly inside one site's polygon at a time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

CELL_SIZE_M = 100.0          # Part 5.2 — physical size, not a count
VARIOGRAM_MODEL = "spherical"
KRIGE_MAX_POINTS = 2000      # guard: OK is O(n^3) in conditioning points


@dataclass
class SiteGrid:
    site_id: str
    site_name: str
    n_cols: int
    n_rows: int
    cell_size_m: float
    width_m: float
    height_m: float
    area_km2: float
    centers_utm: np.ndarray      # (N, 2) easting/northing of in-polygon cells
    centers_lonlat: np.ndarray   # (N, 2) lon/lat of the same cells
    utm_epsg: str

    @property
    def n_cells_total(self) -> int:
        return self.n_cols * self.n_rows

    @property
    def n_cells_in_polygon(self) -> int:
        return len(self.centers_utm)


def _utm_epsg_for(lon: float) -> str:
    """UTM zone for a longitude, northern hemisphere (all MOIL sites are N)."""
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{32600 + zone}"


def build_site_grid(site_id: str, site: dict) -> SiteGrid:
    """
    Parts 5.1 - 5.3 — build one site's grid at a fixed 100 m cell size.

    The polygon is projected to UTM before measuring so width/height are true
    meters. Measuring in degrees would make cells non-square and latitude-
    dependent, which is exactly the bug in the previous implementation.
    """
    from pyproj import Transformer
    from shapely.geometry import Point
    from shapely.ops import transform as shapely_transform

    geom_wgs84 = site["geom"]
    if geom_wgs84.is_empty or not geom_wgs84.is_valid:
        raise ValueError(f"Site '{site_id}' has an empty or invalid boundary polygon")

    centroid = geom_wgs84.centroid
    utm_epsg = _utm_epsg_for(centroid.x)

    to_utm = Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)
    to_wgs = Transformer.from_crs(utm_epsg, "EPSG:4326", always_xy=True)
    geom_utm = shapely_transform(to_utm.transform, geom_wgs84)

    minx, miny, maxx, maxy = geom_utm.bounds
    width_m, height_m = maxx - minx, maxy - miny

    # Part 5.3 — dimensions follow from real extent / fixed cell size.
    n_cols = max(1, int(np.ceil(width_m / CELL_SIZE_M)))
    n_rows = max(1, int(np.ceil(height_m / CELL_SIZE_M)))

    xs = minx + (np.arange(n_cols) + 0.5) * CELL_SIZE_M
    ys = miny + (np.arange(n_rows) + 0.5) * CELL_SIZE_M
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    flat = np.column_stack([mesh_x.ravel(), mesh_y.ravel()])

    # Keep only cells whose center falls inside the actual polygon, so the
    # surface is masked to the site's shape rather than its bounding box.
    inside = np.fromiter(
        (geom_utm.contains(Point(x, y)) for x, y in flat), dtype=bool, count=len(flat)
    )
    centers_utm = flat[inside]

    lons, lats = to_wgs.transform(centers_utm[:, 0], centers_utm[:, 1])
    centers_lonlat = np.column_stack([lons, lats])

    return SiteGrid(
        site_id=site_id, site_name=site["name"],
        n_cols=n_cols, n_rows=n_rows, cell_size_m=CELL_SIZE_M,
        width_m=width_m, height_m=height_m, area_km2=site["area_km2"],
        centers_utm=centers_utm, centers_lonlat=centers_lonlat, utm_epsg=utm_epsg,
    )


def krige_site_surface(grid: SiteGrid, sample_xy: np.ndarray, sample_z: np.ndarray) -> tuple[np.ndarray, str]:
    """
    Part 5.6 — Ordinary Kriging of per-cell probabilities within ONE site.

    Returns (values, method). Falls back to inverse-distance weighting if
    kriging fails to converge on sparse/degenerate data, per the robustness
    requirement, and reports which method was actually used so the fallback
    is never silent.
    """
    if len(sample_xy) < 3:
        logger.warning("[%s] only %d conditioning points — using IDW", grid.site_id, len(sample_xy))
        return _idw(grid.centers_utm, sample_xy, sample_z), "idw_insufficient_points"

    # Subsample for tractability; OK solves an n x n system.
    if len(sample_xy) > KRIGE_MAX_POINTS:
        idx = np.random.default_rng(42).choice(len(sample_xy), KRIGE_MAX_POINTS, replace=False)
        sample_xy, sample_z = sample_xy[idx], sample_z[idx]

    try:
        from pykrige.ok import OrdinaryKriging

        ok = OrdinaryKriging(
            sample_xy[:, 0], sample_xy[:, 1], sample_z,
            variogram_model=VARIOGRAM_MODEL,
            enable_plotting=False, coordinates_type="euclidean",
        )
        values, _ = ok.execute("points", grid.centers_utm[:, 0], grid.centers_utm[:, 1])
        values = np.asarray(values, dtype=float)

        if not np.all(np.isfinite(values)):
            raise ValueError("kriging produced non-finite values")
        return np.clip(values, 0.0, 1.0), f"ordinary_kriging_{VARIOGRAM_MODEL}"

    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] kriging failed (%s) — falling back to IDW", grid.site_id, exc)
        return _idw(grid.centers_utm, sample_xy, sample_z), "idw_fallback"


def _idw(targets: np.ndarray, sample_xy: np.ndarray, sample_z: np.ndarray, power: float = 2.0) -> np.ndarray:
    """Inverse-distance-weighted interpolation — the Part 5.6 fallback."""
    out = np.empty(len(targets), dtype=float)
    for i, (tx, ty) in enumerate(targets):
        d = np.hypot(sample_xy[:, 0] - tx, sample_xy[:, 1] - ty)
        if np.any(d < 1e-9):
            out[i] = sample_z[d.argmin()]
            continue
        w = 1.0 / np.power(d, power)
        out[i] = float(np.sum(w * sample_z) / np.sum(w))
    return np.clip(out, 0.0, 1.0)


def build_all_grids() -> dict[str, SiteGrid]:
    from prospectivity.training_data import load_site_boundaries

    sites = load_site_boundaries()
    grids: dict[str, SiteGrid] = {}
    for key, site in sites.items():
        try:
            grids[key] = build_site_grid(key, site)
        except Exception as exc:  # noqa: BLE001
            # Robustness requirement: fail clearly for THAT site, don't abort all.
            logger.error("Grid build failed for site '%s': %s", key, exc)
    return grids


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    grids = build_all_grids()

    print("\n" + "=" * 86)
    print(f" PART 5.3 — PER-SITE GRID DIMENSIONS AT FIXED {CELL_SIZE_M:.0f} m x {CELL_SIZE_M:.0f} m CELLS")
    print("=" * 86)
    print(f"{'site':<12}{'area km2':>10}{'width m':>10}{'height m':>10}"
          f"{'cols x rows':>16}{'bbox cells':>12}{'in-polygon':>12}")
    print("-" * 86)
    for key, g in grids.items():
        print(f"{key:<12}{g.area_km2:>10.1f}{g.width_m:>10.0f}{g.height_m:>10.0f}"
              f"{f'{g.n_cols} x {g.n_rows}':>16}{g.n_cells_total:>12,}{g.n_cells_in_polygon:>12,}")
    print("-" * 86)

    dims = {k: (g.n_cols, g.n_rows) for k, g in grids.items()}
    print(f"\nDistinct (cols x rows) across sites: {len(set(dims.values()))} of {len(dims)}")
    if len(set(dims.values())) == len(dims):
        print("CONFIRMED: every site has different grid dimensions, derived from its real")
        print("physical extent — not forced into a uniform row/column count.")
    else:
        print("WARNING: some sites share dimensions — check for equal-sized boundary boxes.")

    print(f"\nFor contrast, the previous implementation used a fixed 100 x 100 grid over the")
    print(f"combined bbox: ~1460 m x ~1120 m non-square cells (~14x coarser than 100 m).")
    print("=" * 86)
