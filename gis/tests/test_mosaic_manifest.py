"""Offline tests: mosaic status logic, no_data weeks, and manifest fields.

Earth Engine is faked; build_window_mosaic / export_thumb_png are patched, so
no network is touched.
"""

from __future__ import annotations

import json
import os

import pytest

import gis.generate_tiles as gt
import gis.ndvi_pull as npull
import gis.ndvi_timeseries as nts
from geo_utils import COMBINED_BBOX


class _FakeImage:
    def normalizedDifference(self, *_):
        return self

    def rename(self, *_):
        return self

    def select(self, *_):
        return self

    def divide(self, *_):
        return self


class _FakeEE:
    class Geometry:
        @staticmethod
        def Rectangle(bbox):
            return ("rect", tuple(bbox))


def _mosaic(count, vf, first="2026-09-01", last="2026-09-05"):
    return {
        "image": _FakeImage() if count else None,
        "image_count": count,
        "valid_fraction": vf,
        "acquisition_first": first if count else None,
        "acquisition_last": last if count else None,
    }


@pytest.fixture
def patched(monkeypatch):
    """Patch GEE out; `plan` maps a window-start call index to a mosaic."""
    calls = []
    plan = {"mosaics": []}

    def fake_build(_ee, _roi, start, end):
        calls.append((start, end))
        return plan["mosaics"].pop(0)

    def fake_export(_img, _roi, path, *_a, **_k):
        with open(path, "wb") as fh:
            fh.write(b"png")

    for mod in (npull, nts):
        monkeypatch.setattr(mod, "get_ee", lambda dry_run=False: _FakeEE)
        monkeypatch.setattr(mod, "build_window_mosaic", fake_build)
        monkeypatch.setattr(mod, "export_thumb_png", fake_export)
    return plan, calls


def test_s2_status_thresholds():
    assert npull.s2_status(0, 0.0) == "no_data"
    assert npull.s2_status(5, 0.0) == "no_data"
    assert npull.s2_status(5, 0.0999) == "no_data"
    assert npull.s2_status(5, 0.10) == "ok"
    assert npull.s2_status(5, None) == "no_data"


def test_window_record_fields_and_no_data_has_no_date():
    ok = npull.window_record(_mosaic(7, 0.6), "2026-09-01", "2026-09-08")
    assert ok["status"] == "ok" and ok["date"] == "2026-09-05" and ok["simulated"] is False
    assert ok["image_count"] == 7 and ok["valid_fraction"] == 0.6
    assert ok["window_start"] == "2026-09-01" and ok["window_end"] == "2026-09-08"
    bad = npull.window_record(_mosaic(6, 0.0), "2026-09-01", "2026-09-08")
    assert bad["status"] == "no_data" and bad["date"] is None and bad["image_count"] == 6


def test_empty_week_does_not_raise_writes_no_png_and_removes_stale(patched, tmp_path):
    plan, calls = patched
    # Week 1: empty, then empty again after lookback. Weeks 2-4: fine.
    plan["mosaics"] = [_mosaic(0, 0.0), _mosaic(0, 0.0)] + [_mosaic(4, 0.5)] * 3
    stale = tmp_path / "ndvi_week_1.png"
    stale.write_bytes(b"old image from a previous run")

    weeks = nts.generate_ndvi_timeseries_tiles(tiles_dir=str(tmp_path))

    w1, w2 = weeks[0], weeks[1]
    assert w1["status"] == "no_data" and w1["file"] is None and w1["image_count"] == 0
    assert not stale.exists(), "stale PNG must be deleted, not served as this week"
    assert w1["lookback_applied"] is True
    # The recorded window is the widened one that was actually queried.
    assert (w1["window_start"], w1["window_end"]) == calls[1]
    assert w1["requested_window_start"] == calls[0][0]
    assert w2["status"] == "ok" and w2["file"] == "ndvi_week_2.png"
    assert (tmp_path / "ndvi_week_2.png").exists()
    assert not any(w["simulated"] for w in weeks)


def test_cloudy_week_is_no_data_not_filled_from_another_week(patched, tmp_path):
    plan, _ = patched
    plan["mosaics"] = [_mosaic(6, 0.0)] + [_mosaic(9, 0.6)] * 3  # images exist, all cloud
    weeks = nts.generate_ndvi_timeseries_tiles(tiles_dir=str(tmp_path))
    assert weeks[0]["status"] == "no_data" and weeks[0]["file"] is None
    assert weeks[0]["image_count"] == 6 and weeks[0]["valid_fraction"] == 0.0
    assert weeks[0]["lookback_applied"] is False
    assert not (tmp_path / "ndvi_week_1.png").exists()


def test_manifest_fields_bbox_and_coordinates(patched, tmp_path):
    plan, _ = patched
    plan["mosaics"] = [_mosaic(37, 0.88)] + [_mosaic(0, 0.0), _mosaic(0, 0.0)] + [_mosaic(5, 0.5)] * 3
    manifest = gt.generate_all_tiles(tiles_dir=str(tmp_path))

    raw = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert "SIMULATED_MOCK" not in raw
    assert json.loads(raw) == manifest

    bbox = list(COMBINED_BBOX)
    w, s, e, n = bbox
    corners = [[w, n], [e, n], [e, s], [w, s]]
    entries = list(manifest["layers"].values()) + manifest["timeseries_ndvi"]
    assert manifest["combined_bbox"] == bbox
    for entry in entries:
        assert entry["simulated"] is False
        assert entry["bbox"] == bbox and entry["maplibre_coordinates"] == corners
        for key in ("status", "window_start", "window_end", "image_count", "valid_fraction"):
            assert key in entry
    ndvi = manifest["layers"]["ndvi_latest"]
    assert ndvi["image_count"] == 37 and ndvi["status"] == "ok" and ndvi["file"] == "ndvi_latest.png"
    assert manifest["timeseries_ndvi"][0]["status"] == "no_data"
    assert manifest["timeseries_ndvi"][0]["file"] is None
    assert os.path.exists(tmp_path / "ndvi_latest.png")
