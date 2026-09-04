"""
MOIL Reserve Intelligence (SIH26009) — PART 3: Per-Site Training Data
======================================================================
  3.1  Training points restructured PER SITE (not pooled): ~15-20 deposit and
       ~60-80 non-deposit points per site (~1:4), reflecting realistic deposit
       sparsity and reducing overfitting risk.
  3.2  70/30 stratified train/test split per site (was 80/20 pooled).
  3.3  Features computed at NATIVE resolution per point (no downsampling here;
       aggregation to 100 m analysis cells happens later, in Part 5).

HONESTY NOTE — what is real here and what is not:
  * Point GEOMETRY is real: points are sampled inside each site's actual
    PostGIS boundary polygon, and structural_density is a true UTM-projected
    distance computation against the structural-lines dataset.
  * Point LABELS are synthetic. `is_deposit` is assigned by construction, not
    observed. No borehole or exploration ground truth exists in this repo.
  * Satellite features are left as NaN and marked pending, because Part 1
    cannot execute without Earth Engine credentials.

Consequence: this module produces a correctly-STRUCTURED dataset, but a model
trained on it learns the sampler, not the geology. See train_models.py (Part 4)
for why no metrics table is emitted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Part 3.1 — per-site point budget (~1:4 deposit : non-deposit)
N_DEPOSIT_RANGE = (15, 20)
N_NONDEPOSIT_RANGE = (60, 80)

TEST_SIZE = 0.30      # Part 3.2 — 70/30, matching the cited study
RANDOM_STATE = 42

# Satellite features come from Part 1 and cannot be computed without GEE.
PENDING_SATELLITE_FEATURES = [
    "ndvi_anomaly", "ndri", "ndwi", "iron_oxide_index",
    "clay_index", "manganese_spectral_ratio",
    "slope", "aspect", "terrain_ruggedness",
]


class SiteBoundaryError(RuntimeError):
    """Raised when a site's boundary polygon is missing or malformed."""


@dataclass
class SiteTrainingSet:
    site_id: str
    site_name: str
    points: pd.DataFrame
    area_km2: float

    @property
    def n_deposit(self) -> int:
        return int(self.points["is_deposit"].sum())

    @property
    def n_nondeposit(self) -> int:
        return int((~self.points["is_deposit"].astype(bool)).sum())


def load_site_boundaries(database_url: str | None = None) -> dict:
    """
    Part 3 / 5.1 — Retrieve each site's real boundary polygon from PostGIS.

    Fails loudly and per-site (SiteBoundaryError) on a missing or invalid
    polygon rather than silently skipping the site, per the robustness
    requirement.
    """
    import os
    from shapely import wkt
    from sqlalchemy import create_engine, text

    url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://oresight:oresight@localhost:5433/oresight"
    )
    engine = create_engine(url)

    sites = {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, ST_AsText(geom) AS wkt_geom, "
            "ST_Area(geom::geography)/1e6 AS area_km2 FROM sites ORDER BY id"
        )).fetchall()

    if not rows:
        raise SiteBoundaryError("No rows in `sites` — run seed_dev.py before building training data.")

    for row in rows:
        site_key = row.name.strip().lower()
        if not row.wkt_geom:
            raise SiteBoundaryError(f"Site '{row.name}' (id={row.id}) has a NULL boundary polygon.")
        try:
            geom = wkt.loads(row.wkt_geom)
        except Exception as exc:
            raise SiteBoundaryError(f"Site '{row.name}' has malformed geometry: {exc}") from exc
        if geom.is_empty or not geom.is_valid:
            raise SiteBoundaryError(f"Site '{row.name}' polygon is empty or invalid.")

        sites[site_key] = {
            "db_id": row.id, "name": row.name,
            "geom": geom, "area_km2": float(row.area_km2),
        }

    logger.info("Loaded %d site boundary polygons from PostGIS", len(sites))
    return sites


def _sample_points_in_polygon(geom, n: int, rng: np.random.Generator) -> list[tuple[float, float]]:
    """Rejection-sample n points uniformly inside a polygon."""
    from shapely.geometry import Point

    minx, miny, maxx, maxy = geom.bounds
    pts: list[tuple[float, float]] = []
    # Generous attempt ceiling; these are convex boxes so acceptance is ~100%.
    for _ in range(n * 200):
        if len(pts) >= n:
            break
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if geom.contains(Point(x, y)):
            pts.append((x, y))
    if len(pts) < n:
        raise SiteBoundaryError(
            f"Could only sample {len(pts)}/{n} points inside polygon — geometry may be degenerate."
        )
    return pts


def generate_site_training_points(
    site_key: str, site: dict, rng: np.random.Generator
) -> SiteTrainingSet:
    """Part 3.1 — generate one site's deposit / non-deposit point set."""
    n_dep = int(rng.integers(N_DEPOSIT_RANGE[0], N_DEPOSIT_RANGE[1] + 1))
    n_non = int(rng.integers(N_NONDEPOSIT_RANGE[0], N_NONDEPOSIT_RANGE[1] + 1))

    dep_pts = _sample_points_in_polygon(site["geom"], n_dep, rng)
    non_pts = _sample_points_in_polygon(site["geom"], n_non, rng)

    rows = (
        [{"lon": x, "lat": y, "is_deposit": 1} for x, y in dep_pts]
        + [{"lon": x, "lat": y, "is_deposit": 0} for x, y in non_pts]
    )
    df = pd.DataFrame(rows)
    df["site_id"] = site_key
    df["site_db_id"] = site["db_id"]

    # Part 3.3 — satellite features are computed at native resolution by Part 1.
    # Left explicitly NaN (not zero, not imputed) so downstream code cannot
    # mistake "not computed" for "computed and happens to be zero".
    for col in PENDING_SATELLITE_FEATURES:
        df[col] = np.nan

    return SiteTrainingSet(
        site_id=site_key, site_name=site["name"], points=df, area_km2=site["area_km2"]
    )


def attach_structural_features(df: pd.DataFrame, lines_csv: str = "data/structural_lines.csv") -> pd.DataFrame:
    """
    Part 1.8 / 3.3 — structural lineament density at native point resolution.

    This is the one feature that is genuinely computable offline: it is vector
    geometry, not imagery. Reuses geo_utils.compute_structural_features
    (verified correct: UTM 44N projection, true point-to-segment distances,
    2 km density radius) rather than reimplementing it.
    """
    import os
    from geo_utils import compute_structural_features

    if not os.path.exists(lines_csv):
        logger.warning("Structural lines CSV not found at %s — leaving density NaN", lines_csv)
        df["structural_density"] = np.nan
        df["dist_to_nearest_structure"] = np.nan
        return df

    lines = pd.read_csv(lines_csv)
    min_dist, density = compute_structural_features(df["lon"].values, df["lat"].values, lines)
    df["dist_to_nearest_structure"] = min_dist
    df["structural_density"] = density
    return df


def stratified_split(df: pd.DataFrame, test_size: float = TEST_SIZE, random_state: int = RANDOM_STATE):
    """Part 3.2 — 70/30 stratified split preserving the deposit ratio."""
    from sklearn.model_selection import train_test_split

    y = df["is_deposit"].values
    if len(np.unique(y)) < 2:
        raise ValueError("Cannot stratify: only one class present.")
    train_df, test_df = train_test_split(
        df, test_size=test_size, stratify=y, random_state=random_state
    )
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


def build_all_sites(random_state: int = RANDOM_STATE) -> dict[str, SiteTrainingSet]:
    """Build per-site training sets for every site with a valid boundary."""
    rng = np.random.default_rng(random_state)
    sites = load_site_boundaries()

    out: dict[str, SiteTrainingSet] = {}
    for key, site in sites.items():
        try:
            ts = generate_site_training_points(key, site, rng)
            ts.points = attach_structural_features(ts.points)
            out[key] = ts
        except SiteBoundaryError as exc:
            # Per robustness requirement: fail clearly for THAT site, keep going.
            logger.error("Site '%s' failed and was excluded: %s", key, exc)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sets = build_all_sites()

    print("\n" + "=" * 74)
    print(" PART 3 — PER-SITE TRAINING DATA (3.1 counts, 3.2 split)")
    print("=" * 74)
    print(f"{'site':<12}{'area km2':>10}{'deposit':>9}{'non-dep':>9}{'ratio':>8}{'train':>7}{'test':>6}")
    print("-" * 74)

    for key, ts in sets.items():
        train_df, test_df = stratified_split(ts.points)
        ratio = ts.n_nondeposit / max(ts.n_deposit, 1)
        print(f"{key:<12}{ts.area_km2:>10.1f}{ts.n_deposit:>9}{ts.n_nondeposit:>9}"
              f"{'1:' + format(ratio, '.1f'):>8}{len(train_df):>7}{len(test_df):>6}")

    print("-" * 74)
    total = sum(len(t.points) for t in sets.values())
    print(f"{'TOTAL':<12}{'':>10}{sum(t.n_deposit for t in sets.values()):>9}"
          f"{sum(t.n_nondeposit for t in sets.values()):>9}{'':>8}{total:>7} points")
    print("=" * 74)

    sample = next(iter(sets.values())).points
    computed = [c for c in sample.columns if sample[c].notna().any()
                and c not in ("lon", "lat", "is_deposit", "site_id", "site_db_id")]
    pending = [c for c in PENDING_SATELLITE_FEATURES if sample[c].isna().all()]
    print(f"\nFeatures computed offline : {computed}")
    print(f"Features pending GEE      : {pending}")
    print("\nLabels are synthetic by construction — see module docstring.")
