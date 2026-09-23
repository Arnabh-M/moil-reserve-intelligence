"""
Exports site daily satellite features from data/satellite_daily_features.csv
into a compact JSON structure for the frontend at
oresight-frontend/public/satellite/site_daily_features.json.
"""

from __future__ import annotations

import csv
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_float(val: str) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_int(val: str) -> int | None:
    if not val or val.strip() == "":
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def last_rainfall_date(sites_data: dict[str, list[dict]]) -> str | None:
    """Latest ISO date with a non-null rainfall value across all sites, or None."""
    dates = [r["date"] for recs in sites_data.values() for r in recs if r.get("rainfall_mm") is not None]
    return max(dates) if dates else None


def export_frontend_satellite_json(
    csv_path: str | None = None,
    meta_path: str | None = None,
    out_json_path: str | None = None,
    days_limit: int = 180,
) -> None:
    csv_file = csv_path or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.csv")
    meta_file = meta_path or os.path.join(PROJECT_ROOT, "data", "satellite_daily_features.meta.json")
    out_file = out_json_path or os.path.join(
        PROJECT_ROOT, "oresight-frontend", "public", "satellite", "site_daily_features.json"
    )

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Input CSV not found: {csv_file}")

    meta = {}
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as fh:
            meta = json.load(fh)

    sources = {}
    products = meta.get("products", {})
    if products:
        for prod_key, prod_info in products.items():
            sources[prod_key] = prod_info.get("dataset_id", "")
    else:
        sources = {
            "rainfall": "UCSB-CHG/CHIRPS/DAILY + NASA/GPM_L3/IMERG_V07",
            "soil_moisture": "NASA/SMAP/SPL4SMGP/008",
            "lst": "MODIS/061/MOD11A1",
            "ndvi": "COPERNICUS/S2_SR_HARMONIZED",
        }

    sites_data: dict[str, list[dict]] = {}

    with open(csv_file, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            site_id = row["site_id"].strip().lower()
            record = {
                "date": row["date"].strip(),
                "rainfall_mm": parse_float(row.get("rainfall_mm", "")),
                "soil_moisture_m3m3": parse_float(row.get("soil_moisture_m3m3", "")),
                "lst_day_c": parse_float(row.get("lst_day_c", "")),
                "ndvi": parse_float(row.get("ndvi", "")),
                "ndvi_age_days": parse_int(row.get("ndvi_age_days", "")),
            }
            sites_data.setdefault(site_id, []).append(record)

    # End at the most recent date that has rainfall for any site. The CSV runs
    # to today, which is always empty (satellite products lag by a day or more);
    # a trailing all-null row would make the panel's "Updated" date meaningless.
    cutoff = last_rainfall_date(sites_data)
    if cutoff is not None:
        for site_id in sites_data:
            sites_data[site_id] = [r for r in sites_data[site_id] if r["date"] <= cutoff]

    # Slice each site to the last `days_limit` days
    latest_date_overall = None
    for site_id in sites_data:
        sites_data[site_id].sort(key=lambda x: x["date"])
        if days_limit > 0:
            sites_data[site_id] = sites_data[site_id][-days_limit:]
        if sites_data[site_id]:
            site_latest = sites_data[site_id][-1]["date"]
            if latest_date_overall is None or site_latest > latest_date_overall:
                latest_date_overall = site_latest

    payload = {
        "generated_at": meta.get("generated_at"),
        "simulated": meta.get("simulated", False),
        "latest_date": latest_date_overall,
        "sources": sources,
        "sites": sites_data,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"[OK] Exported frontend satellite JSON: {out_file}")
    for site_id, recs in sites_data.items():
        print(f"  - {site_id}: {len(recs)} days ({recs[0]['date']} to {recs[-1]['date']})")


if __name__ == "__main__":
    export_frontend_satellite_json()
