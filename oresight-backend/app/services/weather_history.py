"""Historical daily rainfall loader for synthetic-data generation and features.

SOURCE CHAIN (per site, per date):
  1. data/satellite_daily_features.csv  — live GEE CHIRPS/IMERG rainfall_mm,
     already covering 2025-01-01..2026-09-22 for all 3 sites (see
     data/satellite_daily_features.meta.json). This is the primary source;
     its own `rainfall_source` value (e.g. "CHIRPS") is passed through.
  2. Open-Meteo historical archive API (archive-api.open-meteo.com), for any
     (site, date) the satellite CSV doesn't cover or has NaN for. Sampled at
     each site's centroid (mean lat/lon of its `included` mines in
     data/moil_sites.json) — same ~9-13km grid resolution caveat as
     app/services/weather_service.py's live forecast calls.
  3. NaN, rain_source="missing" — both of the above had nothing for that day.

Open-Meteo results are cached to disk (data/cache/weather_history_openmeteo.csv,
already gitignored via `data/cache/**`) keyed by (site_id, date), so a fallback
date is fetched from the network at most once across all future runs.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date as _date
from pathlib import Path

import httpx
import pandas as pd

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

logger = logging.getLogger("oresight.weather_history")

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent  # oresight-backend/
REPO_ROOT = BACKEND_ROOT.parent
# MOIL_DATA_DIR overrides the repo-root data/ folder. The api Docker image only contains
# oresight-backend/, so docker-compose.yml mounts ../data at /data and sets this explicitly.
DATA_DIR = Path(os.environ.get("MOIL_DATA_DIR") or REPO_ROOT / "data")
SATELLITE_CSV_PATH = DATA_DIR / "satellite_daily_features.csv"
MOIL_SITES_PATH = DATA_DIR / "moil_sites.json"
CACHE_PATH = DATA_DIR / "cache" / "weather_history_openmeteo.csv"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HTTP_TIMEOUT_SECONDS = 30.0
USER_AGENT = "OreSight-Reserve-Intelligence/1.0 (internal-demo; +https://github.com/Arnabh-M/moil-reserve-intelligence)"

OPENMETEO_SOURCE = "open-meteo-archive"
MISSING_SOURCE = "missing"

_CACHE_COLUMNS = ["site_id", "date", "rainfall_mm", "rain_source"]


# ---------------------------------------------------------------------
# Site centroids (mean lat/lon of `included` mines) — self-contained read
# of moil_sites.json rather than importing the root-level geo_utils module,
# since this file lives inside the backend app and shouldn't depend on the
# repo root being on sys.path.
# ---------------------------------------------------------------------
def _site_centroids() -> dict[str, tuple[float, float]]:
    definitions = json.loads(MOIL_SITES_PATH.read_text(encoding="utf-8"))
    centroids: dict[str, tuple[float, float]] = {}
    for site in definitions["sites"]:
        included = [m for m in site["mines"] if m.get("included")]
        lats = [m["lat"] for m in included]
        lons = [m["lon"] for m in included]
        centroids[site["key"]] = (sum(lats) / len(lats), sum(lons) / len(lons))
    return centroids


_SITE_CENTROIDS = _site_centroids()


# ---------------------------------------------------------------------
# Satellite CSV (primary source) — loaded once per process
# ---------------------------------------------------------------------
def _load_satellite_frame() -> pd.DataFrame:
    df = pd.read_csv(SATELLITE_CSV_PATH, parse_dates=["date"])
    return df[["site_id", "date", "rainfall_mm", "rainfall_source"]]


_SATELLITE_FRAME = _load_satellite_frame()


# ---------------------------------------------------------------------
# Open-Meteo archive fallback, with an on-disk cache
# ---------------------------------------------------------------------
def _load_cache() -> pd.DataFrame:
    if not CACHE_PATH.exists():
        return pd.DataFrame(columns=_CACHE_COLUMNS)
    return pd.read_csv(CACHE_PATH, parse_dates=["date"])


def _save_cache(df: pd.DataFrame) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["site_id", "date"]).to_csv(CACHE_PATH, index=False)


def _fetch_open_meteo_archive(
    site_id: str, start: _date, end: _date, http_timeout: float | None = None
) -> pd.DataFrame:
    """One archive call per site covering [start, end]. Returns
    DataFrame[site_id, date, rainfall_mm, rain_source] — empty if the call
    fails outright (network/HTTP error); callers treat those dates as
    genuinely missing rather than raising, since this is a best-effort
    fallback for a synthetic-data generator, not a user-facing request."""
    lat, lon = _SITE_CENTROIDS[site_id]
    params = {
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "precipitation_unit": "mm",
        "timezone": "UTC",
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=http_timeout or HTTP_TIMEOUT_SECONDS, headers=headers) as client:
            response = client.get(OPEN_METEO_ARCHIVE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Open-Meteo archive fetch failed for %s [%s..%s]: %s", site_id, start, end, exc
        )
        return pd.DataFrame(columns=_CACHE_COLUMNS)

    daily = data.get("daily")
    if not daily or "time" not in daily:
        logger.warning("Open-Meteo archive response missing 'daily' payload for %s", site_id)
        return pd.DataFrame(columns=_CACHE_COLUMNS)

    times = daily["time"]
    precips = daily.get("precipitation_sum", [])
    rows = []
    for i, t in enumerate(times):
        rain = precips[i] if i < len(precips) else None
        if rain is None:
            continue  # genuinely no observation for this day; leave it for "missing"
        rows.append(
            {
                "site_id": site_id,
                "date": pd.Timestamp(t),
                "rainfall_mm": float(rain),
                "rain_source": OPENMETEO_SOURCE,
            }
        )
    return pd.DataFrame(rows, columns=_CACHE_COLUMNS)


def _fill_gaps_from_open_meteo(gaps: pd.DataFrame, http_timeout: float | None = None) -> pd.DataFrame:
    """`gaps` has columns [site_id, date] for rows the satellite CSV doesn't
    cover. Returns rows fetched from the on-disk cache plus any newly fetched
    from Open-Meteo (which are appended to the cache file)."""
    if gaps.empty:
        return pd.DataFrame(columns=_CACHE_COLUMNS)

    cache = _load_cache()
    cache_keys = set(zip(cache["site_id"], cache["date"]))

    still_missing = gaps[
        ~gaps.apply(lambda r: (r["site_id"], r["date"]) in cache_keys, axis=1)
    ]

    new_rows = [cache] if not cache.empty else []
    if not still_missing.empty:
        for site_id, site_gaps in still_missing.groupby("site_id"):
            start, end = site_gaps["date"].min().date(), site_gaps["date"].max().date()
            fetched = _fetch_open_meteo_archive(site_id, start, end, http_timeout)
            if not fetched.empty:
                new_rows.append(fetched)

        if len(new_rows) > (1 if not cache.empty else 0):
            combined_cache = pd.concat(new_rows, ignore_index=True).drop_duplicates(
                subset=["site_id", "date"], keep="last"
            )
            try:
                _save_cache(combined_cache)
            except OSError as exc:  # the cache is an optimisation; a read-only data dir must not fail a request
                logger.warning("Could not write the Open-Meteo cache %s: %s", CACHE_PATH, exc)
            cache = combined_cache

    result = gaps.merge(cache, on=["site_id", "date"], how="left")
    return result[_CACHE_COLUMNS]


# ---------------------------------------------------------------------
# Soil moisture (satellite CSV only; there is no fallback source for it)
# ---------------------------------------------------------------------
_SOIL_FRAME: pd.DataFrame | None = None


def load_soil_moisture(site_id: str, start_date: str | _date, end_date: str | _date) -> dict[_date, float]:
    """Observed SMAP surface soil moisture (m3/m3) per date in [start_date, end_date] for one
    site. Dates the CSV has no value for (SMAP lags ~3 days) are simply absent: never filled."""
    global _SOIL_FRAME
    if _SOIL_FRAME is None:
        _SOIL_FRAME = pd.read_csv(
            SATELLITE_CSV_PATH, usecols=["site_id", "date", "soil_moisture_m3m3"], parse_dates=["date"]
        ).dropna(subset=["soil_moisture_m3m3"])
    frame = _SOIL_FRAME
    mask = (frame["site_id"] == site_id) & (frame["date"] >= pd.Timestamp(start_date)) & (frame["date"] <= pd.Timestamp(end_date))
    return {d.date(): float(v) for d, v in zip(frame.loc[mask, "date"], frame.loc[mask, "soil_moisture_m3m3"])}


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def load_rainfall_history(
    site_ids: list[str],
    start_date: str | _date,
    end_date: str | _date,
    use_fallback: bool = True,
    http_timeout: float | None = None,
) -> pd.DataFrame:
    """Per-site daily rainfall over [start_date, end_date] inclusive.

    Returns a DataFrame with one row per (site_id, date) — columns
    site_id, date, rainfall_mm, rain_source — sourced from the satellite
    CSV where available, the Open-Meteo archive as fallback, or NaN /
    rain_source="missing" if neither has data for that day.

    `use_fallback=False` skips the Open-Meteo step (satellite CSV only), and
    `http_timeout` shortens the per-call HTTP timeout for callers on a request path.
    """
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    date_index = pd.date_range(start_ts, end_ts, freq="D")

    skeleton = pd.DataFrame(
        [(s, d) for s in site_ids for d in date_index], columns=["site_id", "date"]
    )

    sat = _SATELLITE_FRAME[_SATELLITE_FRAME["site_id"].isin(site_ids)]
    merged = skeleton.merge(sat, on=["site_id", "date"], how="left")
    merged = merged.rename(columns={"rainfall_source": "rain_source"})

    gap_mask = merged["rainfall_mm"].isna()
    if use_fallback and gap_mask.any():
        gaps = merged.loc[gap_mask, ["site_id", "date"]]
        filled = _fill_gaps_from_open_meteo(gaps, http_timeout)
        filled_indexed = filled.set_index(["site_id", "date"])
        for idx in merged.index[gap_mask]:
            key = (merged.at[idx, "site_id"], merged.at[idx, "date"])
            if key in filled_indexed.index:
                row = filled_indexed.loc[key]
                if pd.notna(row["rainfall_mm"]):
                    merged.at[idx, "rainfall_mm"] = row["rainfall_mm"]
                    merged.at[idx, "rain_source"] = row["rain_source"]

    still_missing = merged["rainfall_mm"].isna()
    merged.loc[still_missing, "rain_source"] = MISSING_SOURCE

    return merged.sort_values(["site_id", "date"]).reset_index(drop=True)


if __name__ == "__main__":
    import sys

    sites = list(_SITE_CENTROIDS.keys())
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-09-22"

    df = load_rainfall_history(sites, start, end)
    print(f"Loaded {len(df)} rows for {sites} [{start}..{end}]")
    print(df["rain_source"].value_counts().to_string())
    missing = df[df["rain_source"] == MISSING_SOURCE]
    if not missing.empty:
        print(f"\n{len(missing)} rows still missing:")
        print(missing.to_string(index=False))
