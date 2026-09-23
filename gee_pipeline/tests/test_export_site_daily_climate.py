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
    NDVI_COMPOSITE_DAYS,
    NDVI_SOURCE_LABEL,
    convert_lst,
    convert_imerg_daily,
    compute_daily_ndvi_series,
    assign_ndvi_window_values,
    chunk_date_ranges,
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


def test_ndvi_composite_window_assignment():
    """
    Verifies the NDVI composite-window model (replacing per-image acquisition
    carry-forward for the live fetch path):
    - Every date inside a window gets that window's single value.
    - ndvi_age_days is always 0 when a value is present (no aging/carry-forward).
    - A window with value None (no images / low coverage) is empty for every
      date in that window, not interpolated from a neighboring window.
    - A date with no covering window at all is empty.
    """
    w1_start, w1_end = date(2025, 6, 1), date(2025, 6, 10)
    w2_start, w2_end = date(2025, 6, 11), date(2025, 6, 20)
    window_results = [
        (w1_start, w1_end, 0.4567),
        (w2_start, w2_end, None),  # e.g. low valid-pixel coverage that window
    ]

    dates = [w1_start + timedelta(days=i) for i in range(20)]  # covers both windows
    dates.append(date(2025, 7, 1))  # outside any window

    series = assign_ndvi_window_values(window_results, dates)
    assert len(series) == len(dates)

    # Every day of window 1 gets the same value, age 0, labeled source.
    for i in range(10):
        val, age, src = series[i]
        assert val == 0.4567
        assert age == 0
        assert src == NDVI_SOURCE_LABEL

    # Every day of window 2 (value None) is empty, not carried forward from window 1.
    for i in range(10, 20):
        val, age, src = series[i]
        assert val is None
        assert age is None
        assert src == ""

    # A date outside any window is also empty.
    val, age, src = series[20]
    assert val is None
    assert age is None
    assert src == ""


def test_ndvi_composite_window_rounds_to_4_decimals():
    """NDVI composite means must be rounded to 4 decimal places, matching the CSV contract."""
    w_start, w_end = date(2025, 8, 1), date(2025, 8, 10)
    window_results = [(w_start, w_end, 0.123456789)]
    dates = [w_start]

    series = assign_ndvi_window_values(window_results, dates)
    val, _, _ = series[0]
    assert val == 0.1235


def test_chunk_date_ranges_partitions_without_gaps_or_overlap():
    """The window-splitting helper NDVI composites rely on must fully cover the
    range with consecutive, non-overlapping windows of the requested length."""
    start_dt = date(2025, 1, 1)
    end_dt = date(2025, 1, 25)
    windows = chunk_date_ranges(start_dt, end_dt, chunk_days=10)

    assert windows[0] == (date(2025, 1, 1), date(2025, 1, 10))
    assert windows[1] == (date(2025, 1, 11), date(2025, 1, 20))
    assert windows[2] == (date(2025, 1, 21), date(2025, 1, 25))  # final short window

    # No gaps or overlaps: each window starts the day after the previous ends.
    for i in range(len(windows) - 1):
        assert windows[i + 1][0] == windows[i][1] + timedelta(days=1)

    # Full coverage of the requested range.
    assert windows[0][0] == start_dt
    assert windows[-1][1] == end_dt


def test_ndvi_composite_days_env_override(monkeypatch):
    """NDVI_COMPOSITE_DAYS must be overridable via the NDVI_COMPOSITE_DAYS env var."""
    import importlib
    import gee_pipeline.export_site_daily_climate as mod

    monkeypatch.setenv("NDVI_COMPOSITE_DAYS", "5")
    try:
        importlib.reload(mod)
        assert mod.NDVI_COMPOSITE_DAYS == 5
        assert mod.NDVI_SOURCE_LABEL == "S2_median_5d"
    finally:
        monkeypatch.delenv("NDVI_COMPOSITE_DAYS", raising=False)
        importlib.reload(mod)
        assert mod.NDVI_COMPOSITE_DAYS == 10  # restored to default


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


# ---------------------------------------------------------------------------
# build_safe_ndvi_composite — empty-window guard
#
# Sentinel-2's ~5-day revisit means a short window (in practice the trailing
# remainder of a date range) can hold zero images. `col.map(fn).median()` is
# then band-less, and the caller's reduceRegion(...).get("ndvi") raised
# "Dictionary does not contain key: 'ndvi'" — reported as a permanent layer
# failure for an entirely normal condition. Verified live against
# 2026-03-31 (0 images) and 2026-08-31 (0 images).
#
# Exercised with a fake `ee` so this stays offline like the rest of this file.
# ---------------------------------------------------------------------------


class _FakeNode:
    """Records the expression tree instead of talking to Earth Engine."""

    def __init__(self, label, children=()):
        self.label = label
        self.children = list(children)

    def _derive(self, name, *args):
        return _FakeNode(f"{self.label}.{name}", [self, *args])

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *args, **kwargs: self._derive(name, *args)


class _FakeEE:
    def __init__(self, size):
        self._size = size
        self.if_branches = None

    def ImageCollection(self, arg):
        if isinstance(arg, _FakeNode):
            return arg
        return _FakeNode("ImageCollection", list(arg) if isinstance(arg, list) else [arg])

    def Image(self, arg):
        node = _FakeNode("Image", [arg])
        node.constant = lambda v: _FakeNode(f"Image.constant({v})")
        return node

    def Algorithms_If(self, cond, a, b):  # pragma: no cover - not used directly
        raise NotImplementedError

    @property
    def Algorithms(self):
        outer = self

        class _Algorithms:
            @staticmethod
            def If(cond, true_branch, false_branch):
                outer.if_branches = (true_branch, false_branch)
                # Mirror Earth Engine: pick by the recorded collection size.
                return true_branch if outer._size > 0 else false_branch

        return _Algorithms


def _fake_ee_with(size):
    ee = _FakeEE(size)
    # ee.Image is used both as a cast and as a namespace (ee.Image.constant).
    image_ns = _FakeNode("Image")
    image_ns.constant = lambda v: _FakeNode(f"Image.constant({v})")

    def image(arg=None):
        if arg is None:
            return image_ns
        return _FakeNode("Image", [arg])

    image.constant = image_ns.constant
    ee.Image = image
    return ee


class _FakeCollection(_FakeNode):
    def __init__(self, size):
        super().__init__("col")
        self._size = size

    def size(self):
        node = _FakeNode("size")
        node.gt = lambda n: self._size > n
        return node

    def map(self, fn):
        return _FakeNode("mapped", [self])


def test_safe_ndvi_composite_uses_real_collection_when_images_exist():
    from gee_pipeline.export_site_daily_climate import build_safe_ndvi_composite

    ee = _fake_ee_with(size=3)
    col = _FakeCollection(size=3)
    build_safe_ndvi_composite(ee, col, lambda img: img)

    chosen, placeholder_branch = ee.if_branches
    assert chosen.label == "mapped", (
        "a window WITH images must composite the real mapped collection"
    )
    assert placeholder_branch is not chosen


def test_safe_ndvi_composite_falls_back_to_masked_placeholder_when_empty():
    from gee_pipeline.export_site_daily_climate import build_safe_ndvi_composite

    ee = _fake_ee_with(size=0)
    col = _FakeCollection(size=0)
    build_safe_ndvi_composite(ee, col, lambda img: img)

    real_branch, placeholder_branch = ee.if_branches
    assert real_branch.label == "mapped"
    # The placeholder must be a fully-masked constant carrying an "ndvi" band,
    # so reduceRegion still returns the key (with a null value).
    rendered = placeholder_branch.children[0]
    labels = []
    node = rendered
    while isinstance(node, _FakeNode) and node.children:
        labels.append(node.label)
        node = node.children[0]
    labels.append(getattr(node, "label", ""))
    joined = " ".join(labels)
    assert "rename" in joined and "updateMask" in joined, (
        f"placeholder must be a masked, named ndvi band; got {joined}"
    )
