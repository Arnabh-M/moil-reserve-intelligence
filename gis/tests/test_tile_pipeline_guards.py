"""Offline guards for the tile pipeline (no Earth Engine calls).

- mask_s2_clouds must return an ee.Image: copyProperties() returns a bare
  ee.Element, so callers hit "'Element' object has no attribute
  'normalizedDifference'" unless the result is re-cast.
- --dry-run must never write the mock tiles into gis/tiles, the directory the
  frontend serves.
"""

from __future__ import annotations

import os

import pytest

from gis.generate_tiles import REPO_ROOT, generate_all_tiles
from gis.ndvi_pull import mask_s2_clouds


class _Element:
    """What copyProperties() really returns: no Image methods."""


class _Image:
    def select(self, *_):
        return self

    def neq(self, *_):
        return self

    def And(self, *_):
        return self

    def updateMask(self, *_):
        return self

    def copyProperties(self, *_a, **_k):
        return _Element()

    def normalizedDifference(self, *_):
        return self


class _FakeEE:
    class Image(_Image):
        # ee.Image(x) casts; ee.Image.constant(1) builds a constant.
        def __new__(cls, obj=None):
            return _Image()

        @staticmethod
        def constant(_v):
            return _Image()


def test_mask_s2_clouds_returns_image_not_element():
    out = mask_s2_clouds(_Image(), _FakeEE)
    assert not isinstance(out, _Element)
    assert hasattr(out, "normalizedDifference")


def test_dry_run_refuses_the_real_tiles_dir():
    with pytest.raises(ValueError, match="dry-run"):
        generate_all_tiles(tiles_dir=os.path.join(REPO_ROOT, "gis", "tiles"), dry_run=True)


def test_dry_run_allowed_in_scratch_dir_and_flagged_simulated(tmp_path):
    manifest = generate_all_tiles(tiles_dir=str(tmp_path), dry_run=True)
    assert all(layer["simulated"] for layer in manifest["layers"].values())
    assert all(item["simulated"] for item in manifest["timeseries_ndvi"])
