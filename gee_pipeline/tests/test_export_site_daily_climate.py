"""
Unit tests for gee_pipeline/export_site_daily_climate.py
=========================================================
Tests all pure post-processing functions without network access or GEE dependencies.
"""

from datetime import date, timedelta
import math
import pytest

from gee_pipeline.export_site_daily_climate import (
    COLUMNS,
    convert_lst,
    convert_imerg_daily,
    compute_daily_ndvi_series,
    format_cell,
    merge_daily_features,
    generate_dry_run_dataset,
)


def test_column_order_and_names():
    """Verifies that the output contract's column names and order are exact."""
    expected_columns = [
        "site_id",
        "date",
        "rainfall_mm",
        "rainfall_source",
        "soil_moisture_m3m3",
        "soil_moisture_source",
        "lst_day_c",
        "lst_source",
        "ndvi",
        "ndvi_age_days",
        "ndvi_source",
    ]
    assert COLUMNS == expected_columns, f"Column mismatch: {COLUMNS} != {expected_columns}"


def test_uniqueness_and_date_completeness():
    """Verifies that exactly one row exists per (site_id, date) with no gaps or duplicates."""
    start_dt = date(2025, 1, 1)
    end_dt = date(2025, 1, 15)
    dates = [start_dt + timedelta(days=i) for i in range((end_dt - start_dt).days + 1)]

    site_id = "balaghat"
    ndvi_records = [(None, None, "")] * len(dates)

    rows = merge_daily_features(
        dates=dates,
        site_id=site_id,
        chirps_data={},
        imerg_data={},
        smap_data={},
        lst_data={},
        ndvi_records=ndvi_records,
    )

    assert len(rows) == len(dates), "Row count must match total dates in interval"

    seen_pairs = set()
    for i, r in enumerate(rows):
        pair = (r["site_id"], r["date"])
        assert pair not in seen_pairs, f"Duplicate (site_id, date) found: {pair}"
        seen_pairs.add(pair)
        assert r["date"] == dates[i].strftime("%Y-%m-%d"), "Dates must match chronologically"


def test_empty_not_zero_and_cell_formatting():
    """
    Missing values must be strictly empty cells in CSV output:
    never '0', never '0.0', never 'None', never 'NaN'.
    """
    assert format_cell(None) == ""
    assert format_cell(float("nan")) == ""
    assert format_cell(0) == "0"
    assert format_cell(0.0, precision=2) == "0.00"
    assert format_cell(12.3456, precision=2) == "12.35"
    assert format_cell(0.123456, precision=4) == "0.1235"

    dt = date(2025, 5, 1)
    rows = merge_daily_features(
        dates=[dt],
        site_id="nagpur",
        chirps_data={},
        imerg_data={},
        smap_data={},
        lst_data={},
        ndvi_records=[(None, None, "")],
    )
    r = rows[0]
    assert r["rainfall_mm"] is None
    assert r["rainfall_source"] == ""
    assert r["soil_moisture_m3m3"] is None
    assert r["soil_moisture_source"] == ""
    assert r["lst_day_c"] is None
    assert r["lst_source"] == ""
    assert r["ndvi"] is None
    assert r["ndvi_age_days"] is None
    assert r["ndvi_source"] == ""

    # Check simulated CSV row serialization
    csv_line = ",".join([
        r["site_id"],
        r["date"],
        format_cell(r["rainfall_mm"], precision=2),
        r["rainfall_source"],
        format_cell(r["soil_moisture_m3m3"], precision=4),
        r["soil_moisture_source"],
        format_cell(r["lst_day_c"], precision=2),
        r["lst_source"],
        format_cell(r["ndvi"], precision=4),
        format_cell(r["ndvi_age_days"]),
        r["ndvi_source"],
    ])
    assert csv_line == "nagpur,2025-05-01,,,,,,,,,"


def test_lst_conversion():
    """
    Verifies MODIS MOD11A1 digital number to Celsius conversion:
    Formula: value * 0.02 - 273.15
    """
    # 300.0 Kelvin -> 26.85 °C
    # 300 / 0.02 = 15000 raw DN
    assert convert_lst(15000) == 26.85

    # 320.0 Kelvin -> 46.85 °C
    # 320 / 0.02 = 16000 raw DN
    assert convert_lst(16000) == 46.85

    # Edge cases
    assert convert_lst(None) is None
    assert convert_lst(0) is None
    assert convert_lst(-100) is None
    assert convert_lst(float("nan")) is None


def test_imerg_conversion():
    """
    Verifies GPM IMERG half-hourly precipitation sum to daily total conversion:
    Formula: sum(mm/hr) * 0.5 hr
    """
    # 24 half-hourly periods averaging 2.0 mm/hr = sum 48.0 mm/hr -> 24.0 mm daily
    assert convert_imerg_daily(48.0) == 24.00
    assert convert_imerg_daily(0.0) == 0.00
    assert convert_imerg_daily(5.7) == 2.85
    assert convert_imerg_daily(None) is None
    assert convert_imerg_daily(float("nan")) is None


def test_ndvi_30_day_carry_forward_limit():
    """
    Verifies NDVI time-series construction:
    - ndvi_age_days = 0 on acquisition day.
    - Carries forward up to day 30 (ndvi_age_days = 30).
    - On day 31+, value, age, and source must be empty (None / '').
    """
    base_dt = date(2025, 6, 1)
    acquisitions = {
        base_dt: 0.4567,
    }
    # 35 days window: Day 0 to Day 34
    dates = [base_dt + timedelta(days=i) for i in range(35)]

    series = compute_daily_ndvi_series(acquisitions, dates, max_age_days=30)
    assert len(series) == 35

    # Day 0: Acquisition day
    val_0, age_0, src_0 = series[0]
    assert val_0 == 0.4567
    assert age_0 == 0
    assert src_0 == "S2_SR"

    # Day 15: Halfway through carry-forward window
    val_15, age_15, src_15 = series[15]
    assert val_15 == 0.4567
    assert age_15 == 15
    assert src_15 == "S2_SR"

    # Day 30: Final valid carry-forward day
    val_30, age_30, src_30 = series[30]
    assert val_30 == 0.4567
    assert age_30 == 30
    assert src_30 == "S2_SR"

    # Day 31: Expired carry-forward (> 30 days)
    val_31, age_31, src_31 = series[31]
    assert val_31 is None
    assert age_31 is None
    assert src_31 == ""

    # Day 34: Still expired
    val_34, age_34, src_34 = series[34]
    assert val_34 is None
    assert age_34 is None
    assert src_34 == ""


def test_chirps_priority_over_imerg():
    """
    Verifies that CHIRPS takes precedence over IMERG when both are available,
    and IMERG serves only as fallback when CHIRPS is absent.
    """
    d1 = date(2025, 7, 1)  # Both CHIRPS and IMERG present -> CHIRPS wins
    d2 = date(2025, 7, 2)  # Only IMERG present -> IMERG used
    d3 = date(2025, 7, 3)  # Neither present -> empty

    chirps = {d1: 15.20}
    imerg = {d1: 18.50, d2: 8.40}

    rows = merge_daily_features(
        dates=[d1, d2, d3],
        site_id="bhandara",
        chirps_data=chirps,
        imerg_data=imerg,
        smap_data={},
        lst_data={},
        ndvi_records=[(None, None, "")] * 3,
    )

    # Row 1 (d1): CHIRPS takes priority
    assert rows[0]["rainfall_mm"] == 15.20
    assert rows[0]["rainfall_source"] == "CHIRPS"

    # Row 2 (d2): IMERG fallback
    assert rows[1]["rainfall_mm"] == 8.40
    assert rows[1]["rainfall_source"] == "IMERG"

    # Row 3 (d3): Empty
    assert rows[2]["rainfall_mm"] is None
    assert rows[2]["rainfall_source"] == ""


def test_dry_run_generator_integrity():
    """
    Verifies that generate_dry_run_dataset generates sorted rows conforming
    strictly to the output contract and produces higher monsoon rainfall.
    """
    start_dt = date(2025, 1, 1)
    end_dt = date(2025, 10, 1)
    sites = ["balaghat", "nagpur", "bhandara"]

    rows, stats = generate_dry_run_dataset(sites, start_dt, end_dt)

    total_days = (end_dt - start_dt).days + 1
    assert len(rows) == total_days * len(sites)

    # Verify strictly sorted by site_id, then date
    for i in range(len(rows) - 1):
        r1 = rows[i]
        r2 = rows[i + 1]
        assert (r1["site_id"], r1["date"]) < (r2["site_id"], r2["date"])

    # Sanity check monsoon wetter than dry season
    for s in sites:
        monsoon = [
            r["rainfall_mm"]
            for r in rows
            if r["site_id"] == s and r["rainfall_mm"] is not None and "2025-06-01" <= r["date"] <= "2025-09-30"
        ]
        dry = [
            r["rainfall_mm"]
            for r in rows
            if r["site_id"] == s and r["rainfall_mm"] is not None and "2025-01-01" <= r["date"] <= "2025-04-30"
        ]
        assert sum(monsoon) / len(monsoon) > sum(dry) / len(dry), f"Site {s} monsoon must be wetter than dry season"
