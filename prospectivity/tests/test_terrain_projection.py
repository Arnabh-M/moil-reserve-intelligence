"""terrain_features must restore the DEM's native projection.

ImageCollection.mosaic() drops the source projection, so ee.Terrain computed
slope on a 1-degree grid (slope 0, constant aspect at every point). Verified
live on Nagpur: after the fix slope spans 0-13 deg and aspect 0-348 deg.
Offline check: the projection is restored on the mosaic and the result is
pinned to it with reproject().
"""

from unittest.mock import MagicMock

from prospectivity.gee_features import terrain_features


def test_terrain_restores_and_pins_dem_projection():
    ee = MagicMock()
    coll = ee.ImageCollection.return_value.select.return_value
    proj = coll.first.return_value.projection.return_value
    mosaic = coll.mosaic.return_value

    terrain_features(ee, geometry=MagicMock())

    mosaic.setDefaultProjection.assert_called_once_with(proj)
    # every returned band stack is reprojected to the DEM grid before sampling
    ee.Terrain.products.assert_called_once_with(mosaic.setDefaultProjection.return_value)
    stack = ee.Terrain.products.return_value.select.return_value.rename.return_value \
        .addBands.return_value.addBands.return_value
    stack.reproject.assert_called_once_with(proj)
