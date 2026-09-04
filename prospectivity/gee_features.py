"""
MOIL Reserve Intelligence (SIH26009) — PART 1: GEE Feature Engineering
=======================================================================
Computes the multi-source remote-sensing feature stack used by the reserve
prospectivity classifier, following the methodology of:

    Zhao et al. (2025), "Predicting Manganese Mineralization Using Multi-Source
    Remote Sensing and Machine Learning: A Case Study from the Malkansu
    Manganese Belt", Minerals 15(2), 113. DOI: 10.3390/min15020113

================================ RUN STATUS ================================
THIS MODULE HAS NEVER BEEN EXECUTED AGAINST LIVE EARTH ENGINE IN THIS REPO.

`earthengine-api` is not installed in either interpreter, there are no cached
credentials (~/.config/earthengine/), no service-account JSON, and no GCP
project configured. Every GEE code path in this repository has only ever run
its mock branch.

To actually run this module you need all three of:
    1. pip install earthengine-api
    2. A Google Cloud project with the Earth Engine API enabled
    3. Credentials — either `earthengine authenticate` (interactive OAuth) or
       a service-account key referenced by EE_SERVICE_ACCOUNT_JSON (see
       `initialize_ee` below).

Until then `initialize_ee()` raises GEEUnavailableError with an actionable
message rather than silently returning fabricated values. There is
deliberately no synthetic fallback in this module: the pre-existing
`gis/ndvi_pull.py` mock path exists for *tile rendering* demos, but silently
substituting noise for satellite features inside the *classifier* pipeline
is how a model ends up learning nothing while reporting a confident AUC.
============================================================================
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel-2 band reference (Sentinel-2A/2B, L2A Surface Reflectance)
# Center wavelengths / bandwidths per ESA Copernicus SentiWiki.
# ---------------------------------------------------------------------------
S2_BANDS = {
    "B2":  {"center_nm": 490,  "res_m": 10, "name": "Blue"},
    "B3":  {"center_nm": 560,  "res_m": 10, "name": "Green"},
    "B4":  {"center_nm": 665,  "res_m": 10, "name": "Red"},
    "B7":  {"center_nm": 783,  "res_m": 20, "name": "Red Edge 3"},
    "B8":  {"center_nm": 842,  "res_m": 10, "name": "NIR"},
    "B11": {"center_nm": 1610, "res_m": 20, "name": "SWIR 1"},
    "B12": {"center_nm": 2190, "res_m": 20, "name": "SWIR 2"},
}

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
DEM_COLLECTION = "COPERNICUS/DEM/GLO30"          # 30 m, per Part 1.7
DEM_FALLBACK = "USGS/SRTMGL1_003"                # 30 m fallback

# Part 1.10 — Scene Classification Layer values to mask out.
#   3 = cloud shadow, 8 = cloud medium probability,
#   9 = cloud high probability, 10 = thin cirrus
SCL_MASK_VALUES = [3, 8, 9, 10]

BASELINE_YEARS = 3          # Part 1.1 — 3 prior years for the seasonal median
BASELINE_CLOUD_PCT = 20     # Part 1.1 — <20% cloud cover filter
BASELINE_CACHE_TTL_DAYS = 7  # Part 1.1 — weekly regeneration, not per-request


class GEEUnavailableError(RuntimeError):
    """Raised when Earth Engine cannot be initialized. Never swallowed."""


class GEELayerError(RuntimeError):
    """A single layer failed (quota, transient). Caller may skip that layer."""


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def initialize_ee(service_account_json: str | None = None):
    """
    Initialize Earth Engine, preferring a service account when available so
    this can run unattended (cron / CI) rather than needing interactive OAuth.

    Set EE_SERVICE_ACCOUNT_JSON to a key-file path, or pass it explicitly.
    Raises GEEUnavailableError with remediation steps instead of degrading
    to synthetic data.
    """
    try:
        import ee
    except ImportError as exc:
        raise GEEUnavailableError(
            "earthengine-api is not installed. Install it with:\n"
            "    pip install earthengine-api\n"
            "then authenticate (see module docstring)."
        ) from exc

    key_path = service_account_json or os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    project = os.environ.get("EE_PROJECT")

    try:
        if key_path:
            if not os.path.exists(key_path):
                raise GEEUnavailableError(f"EE key file not found: {key_path}")
            with open(key_path, "r", encoding="utf-8") as fh:
                email = json.load(fh).get("client_email")
            if not email:
                raise GEEUnavailableError(f"No client_email in EE key file: {key_path}")
            credentials = ee.ServiceAccountCredentials(email, key_path)
            ee.Initialize(credentials, project=project)
        else:
            # Falls back to cached credentials from `earthengine authenticate`.
            ee.Initialize(project=project)

        # Probe: Initialize() can succeed lazily, so force a real round-trip.
        ee.Number(1).getInfo()
        logger.info("Earth Engine initialized (project=%s)", project or "<default>")
        return ee

    except GEEUnavailableError:
        raise
    except Exception as exc:
        raise GEEUnavailableError(
            f"Earth Engine failed to initialize: {exc}\n"
            "Checklist: (1) pip install earthengine-api, (2) GCP project with the "
            "Earth Engine API enabled, (3) `earthengine authenticate` or set "
            "EE_SERVICE_ACCOUNT_JSON to a service-account key path."
        ) from exc


def with_gee_retry(fn: Callable, *, what: str, attempts: int = 4, base_delay: float = 2.0):
    """
    Run a GEE call with exponential backoff on quota/rate-limit/transient errors.

    Per the robustness requirement: a failing layer must not take down the whole
    pipeline. Exhausting retries raises GEELayerError so the caller can skip that
    one layer and continue with the rest.
    """
    transient_markers = (
        "quota", "rate limit", "too many", "429", "503", "500",
        "timed out", "timeout", "deadline", "backend error", "unavailable",
    )
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — GEE raises bare EEException
            last_exc = exc
            msg = str(exc).lower()
            is_transient = any(marker in msg for marker in transient_markers)
            if not is_transient or attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "GEE call '%s' failed (attempt %d/%d): %s — retrying in %.1fs",
                what, attempt, attempts, exc, delay,
            )
            time.sleep(delay)

    raise GEELayerError(f"GEE layer '{what}' failed after {attempts} attempt(s): {last_exc}")


# ---------------------------------------------------------------------------
# Part 1.10 — Cloud masking (applied to EVERY index, current AND baseline)
# ---------------------------------------------------------------------------
def mask_s2_clouds(image, ee):
    """
    Mask cloud shadow / medium+high cloud probability / thin cirrus using the
    L2A Scene Classification Layer, then scale SR values to reflectance.

    Applied identically to the current-week pull and the 3-year baseline pull
    so the anomaly in 1.1 is a like-for-like difference rather than an artifact
    of one side being cloud-contaminated.
    """
    scl = image.select("SCL")
    mask = ee.Image.constant(1)
    for value in SCL_MASK_VALUES:
        mask = mask.And(scl.neq(value))
    # L2A SR is scaled by 10000.
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"])


def _s2_collection(ee, geometry, start, end, max_cloud_pct=BASELINE_CLOUD_PCT):
    return (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
        .map(lambda img: mask_s2_clouds(img, ee))
    )


# ---------------------------------------------------------------------------
# Spectral indices (Parts 1.1 - 1.6)
# ---------------------------------------------------------------------------
def compute_ndvi(image):
    """NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)."""
    return image.normalizedDifference(["B8", "B4"]).rename("ndvi")


def compute_ndri(image):
    """
    Part 1.2 — NDRI (Normalized Difference Rock Index).
    NDRI = (SWIR1 - Green) / (SWIR1 + Green) = (B11 - B3) / (B11 + B3).
    Highlights exposed rock/bare substrate against vegetated ground.
    """
    return image.normalizedDifference(["B11", "B3"]).rename("ndri")


def compute_ndwi(image):
    """
    Part 1.3 — NDWI = (Green - NIR) / (Green + NIR) = (B3 - B8) / (B3 + B8).

    NEGATIVE indicator: high NDWI means standing water, where a surface
    mineralization signal is meaningless. The classifier consumes this as a
    suppressor, and `water_mask` below is what downstream code should use to
    flag those cells rather than treating high NDWI as prospective.
    """
    return image.normalizedDifference(["B3", "B8"]).rename("ndwi")


def compute_iron_oxide(image):
    """
    Part 1.4 — Iron-oxide ratio = Red / Blue = B4 / B2. VERIFIED: this matches
    the ratio already used in the tile path (gis/ndvi_pull.py, gee_prep.py),
    so classifier and rendering now agree on one definition.

    NOTE: this ratio was previously computed ONLY for tile rendering and never
    reached the classifier, despite being the most geologically relevant band
    ratio available. Part 1 wires it into the feature stack.
    """
    return image.select("B4").divide(image.select("B2")).rename("iron_oxide_index")


def compute_clay_index(image):
    """Part 1.5 — Clay mineral index = SWIR1 / SWIR2 = B11 / B12."""
    return image.select("B11").divide(image.select("B12")).rename("clay_index")


def compute_manganese_ratio(image):
    """
    Part 1.6 — Custom manganese-specific spectral ratio.

    VERIFIED AGAINST THE SPECTROSCOPY LITERATURE — and the verification changed
    the design, so read this before trusting the feature:

    Rhodochrosite (MnCO3), a MOIL ore mineral, has its DIAGNOSTIC carbonate
    (CO3^2-) vibrational overtone absorption at ~2.36 um (Gaffey 1987; longer
    than calcite 2.34 um and magnesite 2.30 um, because Mn2+ does not follow the
    ionic-radius trend of the other carbonates).

    Sentinel-2 CANNOT SEE THAT FEATURE. B12 is centered at 2190 nm with a
    174-184 nm bandwidth, i.e. it covers ~2.10-2.28 um and stops short of
    2.36 um. So the single most diagnostic rhodochrosite band is out of reach of
    this sensor — the cited study's approach does NOT transfer wholesale.

    Pyrolusite (MnO2, Mn4+) is opaque and spectrally dark/featureless across
    VNIR-SWIR; it is better detected as a low-albedo anomaly than by any band
    ratio, so it is not represented here either.

    What IS defensible with Sentinel-2 is the VNIR reflectance-SHAPE signature
    the cited study reports — relative peaks near 0.55 um and 0.8 um. Mapping to
    the nearest S2 bands:
        0.55 um -> B3  (560 nm, near-exact)
        0.80 um -> B7  (783 nm; closer than B8 at 842 nm)
    We express it as a normalized difference for numerical stability.

    TREAT THIS AS A WEAK PROXY, NOT A MINERAL DETECTION. To actually resolve
    rhodochrosite you need a sensor covering 2.36 um: ASTER band 8
    (2.295-2.365 um) covers it directly, as would hyperspectral EnMAP / EMIT /
    AVIRIS. That is the highest-value sensor upgrade for this pipeline.
    """
    return image.normalizedDifference(["B7", "B3"]).rename("manganese_spectral_ratio")


# ---------------------------------------------------------------------------
# Part 1.1 — Seasonal NDVI anomaly with cached 3-year baseline
# ---------------------------------------------------------------------------
@dataclass
class BaselineCache:
    """
    Part 1.1 requires the 3-year seasonal baseline be cached and regenerated
    weekly, not recomputed per request — the multi-year median reduction is the
    expensive part of this pipeline.
    """
    cache_dir: str = "data/cache/ndvi_baseline"
    ttl_days: int = BASELINE_CACHE_TTL_DAYS

    def path_for(self, site_id: str, iso_week: int) -> str:
        return os.path.join(self.cache_dir, f"{site_id}_week{iso_week:02d}.json")

    def is_fresh(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        age = time.time() - os.path.getmtime(path)
        return age < self.ttl_days * 86400

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def store(self, path: str, payload: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)


def seasonal_ndvi_baseline(ee, geometry, reference_date: datetime, years: int = BASELINE_YEARS):
    """
    Part 1.1 — Per-pixel MEDIAN NDVI for the SAME calendar week across the last
    `years` available years, cloud-masked and <20% cloud cover.

    Using the same ISO week each year controls for phenology: comparing this
    week's NDVI against an annual mean would confound seasonal greening with a
    genuine anomaly.
    """
    iso_week = reference_date.isocalendar().week
    yearly = []

    for offset in range(1, years + 1):
        year = reference_date.year - offset
        # Reconstruct the same ISO week in the prior year.
        try:
            week_start = datetime.fromisocalendar(year, iso_week, 1).replace(tzinfo=timezone.utc)
        except ValueError:
            # ISO week 53 does not exist in every year — skip that year.
            logger.warning("ISO week %d does not exist in %d; skipping baseline year", iso_week, year)
            continue
        week_end = week_start + timedelta(days=7)

        coll = _s2_collection(ee, geometry, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
        yearly.append(coll.map(compute_ndvi).median())

    if not yearly:
        raise GEELayerError(
            f"No baseline imagery for ISO week {iso_week} across the last {years} years"
        )

    return ee.ImageCollection.fromImages(yearly).median().rename("ndvi_baseline")


def seasonal_ndvi_anomaly(ee, geometry, reference_date: datetime):
    """
    Part 1.1 — anomaly = current_week_NDVI - 3yr_seasonal_median_NDVI.

    This anomaly (NOT raw NDVI) is what feeds the classifier and the map.
    Negative values = vegetation loss vs the seasonal norm, the signal of
    interest for surface disturbance / exposure.
    """
    week_start = reference_date - timedelta(days=7)
    current = (
        _s2_collection(ee, geometry, week_start.strftime("%Y-%m-%d"), reference_date.strftime("%Y-%m-%d"))
        .map(compute_ndvi)
        .median()
    )
    baseline = seasonal_ndvi_baseline(ee, geometry, reference_date)
    return current.subtract(baseline).rename("ndvi_anomaly")


# ---------------------------------------------------------------------------
# Part 1.7 — Topographic factors from DEM
# ---------------------------------------------------------------------------
def terrain_features(ee, geometry, dem_asset: str = DEM_COLLECTION):
    """
    Part 1.7 — slope (degrees), aspect (compass degrees), and terrain
    ruggedness index from a 30 m DEM.

    TRI here is the standard-deviation-of-elevation formulation over a 5x5
    neighbourhood (Part 1.7 permits 3x3 or 5x5); 5x5 at 30 m ~= a 150 m window,
    which is a better match for the 100 m analysis cell used in Part 5 than 3x3
    would be.
    """
    try:
        dem = ee.ImageCollection(dem_asset).select("DEM").mosaic()
    except Exception:  # noqa: BLE001 — GLO30 is a collection, SRTM is an Image
        dem = ee.Image(dem_asset).select("elevation")

    dem = dem.clip(geometry)
    terrain = ee.Terrain.products(dem)

    ruggedness = dem.reduceNeighborhood(
        reducer=ee.Reducer.stdDev(),
        kernel=ee.Kernel.square(radius=2, units="pixels"),  # 5x5
    ).rename("terrain_ruggedness")

    return (
        terrain.select("slope").rename("slope")
        .addBands(terrain.select("aspect").rename("aspect"))
        .addBands(ruggedness)
    )


# ---------------------------------------------------------------------------
# Part 1.9 — Stratigraphic favorability: DELIBERATELY SKIPPED
# ---------------------------------------------------------------------------
STRATIGRAPHIC_LAYER_STATUS = {
    "feature": "stratigraphic_favorability",
    "status": "SKIPPED — no accessible public data source",
    "reason": (
        "No open, machine-readable lithology/geology polygon layer was found for the "
        "Balaghat / Nagpur / Bhandara manganese belts. The Geological Survey of India "
        "publishes Bhukosh map sheets, but not as an open programmatic feature service "
        "usable here, and no GEE-hosted equivalent covers Indian lithology at the needed "
        "scale. Per Part 1.9, this feature is omitted entirely rather than filled with "
        "fabricated synthetic lithology presented as real."
    ),
    "future_integration": (
        "Digitize GSI Bhukosh 1:50,000 lithology sheets for the three districts, or "
        "license a commercial geology layer, then join host-rock favorability "
        "(Gondite / Mn-bearing metasediment vs barren) as a categorical feature."
    ),
}


# ---------------------------------------------------------------------------
# Feature stack assembly
# ---------------------------------------------------------------------------
@dataclass
class FeatureStackResult:
    image: object | None                       # ee.Image of stacked bands
    computed: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


def build_feature_stack(ee, geometry, reference_date: datetime | None = None) -> FeatureStackResult:
    """
    Assemble the full Part 1 feature stack for `geometry`.

    Each layer is computed independently and guarded: if one layer exhausts its
    retries (quota, transient backend error), it is recorded in `skipped` and
    the remaining layers still return. A partial stack is far more useful than
    a crashed pipeline, and the caller can see exactly what is missing.
    """
    reference_date = reference_date or datetime.now(timezone.utc)

    # Single cloud-masked composite for the current week, shared by the
    # non-temporal indices so they are all derived from identical pixels.
    week_start = reference_date - timedelta(days=7)
    current = with_gee_retry(
        lambda: _s2_collection(
            ee, geometry,
            week_start.strftime("%Y-%m-%d"),
            reference_date.strftime("%Y-%m-%d"),
        ).median(),
        what="s2_current_week_composite",
    )

    layers: dict[str, Callable] = {
        "ndvi_anomaly": lambda: seasonal_ndvi_anomaly(ee, geometry, reference_date),
        "ndri": lambda: compute_ndri(current),
        "ndwi": lambda: compute_ndwi(current),
        "iron_oxide_index": lambda: compute_iron_oxide(current),
        "clay_index": lambda: compute_clay_index(current),
        "manganese_spectral_ratio": lambda: compute_manganese_ratio(current),
        "terrain": lambda: terrain_features(ee, geometry),
    }

    stack = None
    computed: list[str] = []
    skipped: dict[str, str] = {}

    for name, builder in layers.items():
        try:
            band = with_gee_retry(builder, what=name)
            stack = band if stack is None else stack.addBands(band)
            computed.extend(["slope", "aspect", "terrain_ruggedness"] if name == "terrain" else [name])
        except GEELayerError as exc:
            logger.error("Skipping layer '%s': %s", name, exc)
            skipped[name] = str(exc)

    # Part 1.3 — expose the water mask explicitly as a suppressor.
    if stack is not None and "ndwi" in computed:
        stack = stack.addBands(stack.select("ndwi").gt(0).rename("water_mask"))

    skipped[STRATIGRAPHIC_LAYER_STATUS["feature"]] = STRATIGRAPHIC_LAYER_STATUS["status"]

    return FeatureStackResult(image=stack, computed=computed, skipped=skipped)


# Part 1.8 — Structural lineament density is NOT computed here. It is a vector
# operation on the structural_lines dataset, not a raster pull, and it already
# exists and is correct in geo_utils.compute_structural_features(): points and
# line endpoints are projected to UTM 44N (EPSG:32644) and a true
# point-to-segment distance matrix gives both distance-to-nearest-structure and
# a count of structures within a 2 km radius. VERIFIED — reused as-is rather
# than reimplemented. Caveat: the underlying lines are synthetic
# (generate_features.py), so the feature is geometrically real but geologically
# invented until surveyed lineaments replace them.

FEATURE_NAMES = [
    "ndvi_anomaly",              # 1.1  (replaces raw NDVI)
    "ndri",                      # 1.2
    "ndwi",                      # 1.3  (negative indicator)
    "iron_oxide_index",          # 1.4
    "clay_index",                # 1.5
    "manganese_spectral_ratio",  # 1.6  (weak VNIR proxy — see docstring)
    "slope",                     # 1.7
    "aspect",                    # 1.7
    "terrain_ruggedness",        # 1.7
    "structural_density",        # 1.8  (from geo_utils, not GEE)
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        initialize_ee()
    except GEEUnavailableError as exc:
        print("\n=== Earth Engine unavailable ===")
        print(exc)
        print("\nPart 1 feature definitions are ready; they cannot be executed here.")
        raise SystemExit(1)
