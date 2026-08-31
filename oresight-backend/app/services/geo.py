"""Convert ORM rows with GeoAlchemy2 geometry columns into GeoJSON.

Geometries are stored (and therefore read back) as (X, Y) = (longitude,
latitude) in WGS84 (SRID 4326), matching MapLibre's expected [lon, lat]
coordinate order with no reprojection needed.
"""

from typing import Any, Callable

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping


def to_geojson_feature(
    row: Any, geom_attr: str, properties: dict[str, Any]
) -> dict[str, Any]:
    """Build a single GeoJSON Feature from one ORM row's geometry column."""
    shape = to_shape(getattr(row, geom_attr))
    return {
        "type": "Feature",
        "geometry": mapping(shape),
        "properties": properties,
    }


def to_geojson_feature_collection(
    rows: list[Any],
    geom_attr: str,
    properties_fn: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Build a GeoJSON FeatureCollection from a list of ORM rows.

    `properties_fn` is called once per row to compute that row's Feature
    properties dict.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            to_geojson_feature(row, geom_attr, properties_fn(row)) for row in rows
        ],
    }
