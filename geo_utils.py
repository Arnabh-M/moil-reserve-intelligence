"""
MOIL Reserve Intelligence (SIH26009) — shared geospatial utilities.

Used by generate_features.py, build_confidence_surface.py, and
export_reserve_zones.py so that projection, distance, and random-field
logic is defined exactly once and stays consistent between the
training-feature pipeline and the grid-prediction pipeline.

Site bounding boxes match data/generate_datasets.py (Day 1) exactly.
"""

import joblib
import numpy as np
from pyproj import Transformer
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter

# ---------------------------------------------------------------------
# Site bounding boxes (west/south/east/north order kept implicit as
# lon_range / lat_range, matching Day 1's SITES dict)
# ---------------------------------------------------------------------
SITE_BBOXES = {
    "balaghat": {"lat_range": (21.7, 22.0), "lon_range": (80.1, 80.4)},
    "nagpur":   {"lat_range": (21.0, 21.3), "lon_range": (79.0, 79.3)},
    "bhandara": {"lat_range": (21.1, 21.4), "lon_range": (79.5, 79.8)},
}

# Combined bounding box: west, south, east, north
COMBINED_BBOX = (79.0, 21.0, 80.4, 22.0)

# All three sites fall in UTM zone 44N (78E-84E, northern hemisphere)
_UTM_EPSG = "EPSG:32644"
_WGS84_EPSG = "EPSG:4326"

_to_utm = Transformer.from_crs(_WGS84_EPSG, _UTM_EPSG, always_xy=True)
_to_lonlat = Transformer.from_crs(_UTM_EPSG, _WGS84_EPSG, always_xy=True)


def lonlat_to_utm(lon, lat):
    """Project lon/lat (deg, WGS84) to (x, y) meters in UTM zone 44N."""
    x, y = _to_utm.transform(lon, lat)
    return np.asarray(x), np.asarray(y)


def utm_to_lonlat(x, y):
    lon, lat = _to_lonlat.transform(x, y)
    return np.asarray(lon), np.asarray(lat)


def assign_site_id(lon, lat):
    """Return the site_id whose bbox contains (lon, lat), else None."""
    for site_id, box in SITE_BBOXES.items():
        lat_lo, lat_hi = box["lat_range"]
        lon_lo, lon_hi = box["lon_range"]
        if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi:
            return site_id
    return None


# ---------------------------------------------------------------------
# Point-to-segment distance in projected meters (vectorized: `px`, `py`
# may be arrays; segment endpoints are scalars for a single line)
# ---------------------------------------------------------------------
def point_to_segment_distance_m(px, py, x1, y1, x2, y2):
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return np.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = np.clip(t, 0.0, 1.0)
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return np.hypot(px - proj_x, py - proj_y)


def compute_structural_features(points_lon, points_lat, lines_df, density_radius_km=2.0):
    """
    For arrays of point lon/lat, compute (dist_to_nearest_structure_m,
    structural_density) against every line in lines_df (with columns
    start_lat, start_lon, end_lat, end_lon).

    Both point and line coordinates are projected to UTM meters so
    distances are proper planar distances, not raw lat/lon Euclidean.
    """
    points_lon = np.asarray(points_lon, dtype=float)
    points_lat = np.asarray(points_lat, dtype=float)
    px, py = lonlat_to_utm(points_lon, points_lat)

    line_x1, line_y1 = lonlat_to_utm(lines_df["start_lon"].values, lines_df["start_lat"].values)
    line_x2, line_y2 = lonlat_to_utm(lines_df["end_lon"].values, lines_df["end_lat"].values)

    n_points = len(px)
    n_lines = len(line_x1)
    dist_matrix = np.empty((n_points, n_lines), dtype=float)

    for j in range(n_lines):
        dist_matrix[:, j] = point_to_segment_distance_m(
            px, py, line_x1[j], line_y1[j], line_x2[j], line_y2[j]
        )

    min_dist = dist_matrix.min(axis=1)
    radius_m = density_radius_km * 1000.0
    density = (dist_matrix <= radius_m).sum(axis=1)
    return min_dist, density


# ---------------------------------------------------------------------
# Spatially-correlated random field (proxy for a 2D Gaussian random
# field): white noise on a coarse grid, Gaussian-smoothed for spatial
# correlation, exposed as a RegularGridInterpolator over (lon, lat) so
# it can be sampled at arbitrary points and pickled for reuse.
# ---------------------------------------------------------------------
def build_correlated_field(bbox, seed, grid_res=120, smoothing_sigma=6.0):
    """
    bbox: (west, south, east, north) in degrees.
    Returns a RegularGridInterpolator mapping (lon, lat) -> value,
    normalized to roughly [0, 1].
    """
    west, south, east, north = bbox
    rng = np.random.default_rng(seed)

    noise = rng.normal(0, 1, size=(grid_res, grid_res))
    smoothed = gaussian_filter(noise, sigma=smoothing_sigma, mode="reflect")

    # Normalize to [0, 1]
    smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min())

    lons = np.linspace(west, east, grid_res)
    lats = np.linspace(south, north, grid_res)

    # RegularGridInterpolator expects the grid array indexed [x, y] to
    # match the (lons, lats) axes order.
    interp = RegularGridInterpolator(
        (lons, lats), smoothed.T, bounds_error=False, fill_value=None
    )
    return interp


def sample_field(interp, lon, lat):
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    pts = np.column_stack([lon, lat])
    return interp(pts)


def save_field(interp, path):
    joblib.dump(interp, path)


def load_field(path):
    return joblib.load(path)
