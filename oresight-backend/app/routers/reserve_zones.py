"""Route for reserve zone boundaries as GeoJSON.

Not a stub: this queries the real seeded reserve_zones table directly.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReserveZone
from app.services.geo import to_geojson_feature_collection
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/reserve-zones", tags=["reserve-zones"])


@router.get(
    "",
    summary="Get reserve zones as GeoJSON",
    response_description="A GeoJSON FeatureCollection of reserve zone polygons",
)
def list_reserve_zones(
    site_id: int | None = Query(None, description="Filter to one site's zones"),
    db: Session = Depends(get_db),
) -> dict:
    """Return reserve zone polygons as a GeoJSON FeatureCollection. Each
    feature's `confidence_score` property drives the frontend's map colour
    ramp.
    """
    if site_id is not None:
        get_site_or_404(db, site_id)

    stmt = select(ReserveZone)
    if site_id is not None:
        stmt = stmt.where(ReserveZone.site_id == site_id)
    zones = db.scalars(stmt).all()

    return to_geojson_feature_collection(
        zones,
        "geom",
        lambda z: {
            "id": z.id,
            "site_id": z.site_id,
            "zone_name": z.zone_name,
            "confidence_score": z.confidence_score,
            "estimated_grade_pct": z.estimated_grade_pct,
            "estimated_depth_m": z.estimated_depth_m,
        },
    )
