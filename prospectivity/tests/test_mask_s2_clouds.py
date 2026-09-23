"""mask_s2_clouds must return an ee.Image, not a bare ee.Element.

Earth Engine's `copyProperties()` always returns a generic `ee.Element`
whatever the receiver's type. `mask_s2_clouds()` ended with `.copyProperties()`,
so it handed back an object with no Image methods:

    AttributeError: 'Element' object has no attribute 'normalizedDifference'

Inside `collection.map(...)` Earth Engine re-casts each element back to Image,
which masked the problem at this module's own call sites — but every direct
caller broke. The same bug was already fixed in gee_pipeline/gee_prep.py,
gis/ndvi_pull.py and gee_pipeline/export_site_daily_climate.py; this is the
root function.

These tests use a fake `ee` so they run offline with the rest of the suite.
"""

from __future__ import annotations

import pytest

from prospectivity.gee_features import mask_s2_clouds


class _FakeImage:
    """Has Image methods. What a correct mask_s2_clouds must return."""

    def __init__(self, label="Image"):
        self.label = label

    def select(self, *_):
        return self

    def neq(self, *_):
        return self

    def And(self, *_):
        return self

    def updateMask(self, *_):
        return self

    def divide(self, *_):
        return self

    def normalizedDifference(self, *_):
        return self

    def rename(self, *_):
        return self

    def copyProperties(self, *_args, **_kwargs):
        # Faithful to the real API: downgrades to a property-only Element.
        return _FakeElement()


class _FakeElement:
    """No Image methods — mirrors what copyProperties() really returns."""

    label = "Element"


class _FakeEE:
    Image = staticmethod(lambda arg: arg if isinstance(arg, _FakeImage) else _FakeImage("recast"))

    class _Constant:
        pass


def _fake_ee():
    ee = _FakeEE()
    image_ns = lambda arg: arg if isinstance(arg, _FakeImage) else _FakeImage("recast")
    image_ns.constant = lambda _v: _FakeImage("constant")
    ee.Image = image_ns
    return ee


def test_returns_something_with_image_methods():
    ee = _fake_ee()
    result = mask_s2_clouds(_FakeImage(), ee)

    assert not isinstance(result, _FakeElement), (
        "mask_s2_clouds returned a bare Element — the ee.Image() cast is missing"
    )
    assert hasattr(result, "normalizedDifference"), (
        "the masked image must still expose Image methods; without the cast, "
        "compute_ndvi()/compute_ndri() raise AttributeError on the result"
    )


def test_direct_compute_ndvi_on_the_masked_image_works():
    """The exact call that used to raise AttributeError."""
    from prospectivity.gee_features import compute_ndvi

    ee = _fake_ee()
    masked = mask_s2_clouds(_FakeImage(), ee)
    compute_ndvi(masked)  # must not raise


def test_direct_compute_ndri_on_the_masked_image_works():
    from prospectivity.gee_features import compute_ndri

    ee = _fake_ee()
    masked = mask_s2_clouds(_FakeImage(), ee)
    compute_ndri(masked)  # must not raise
