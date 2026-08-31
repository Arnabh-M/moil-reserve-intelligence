"""Routes for mine sites: list, detail, and boundary GeoJSON."""

from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReserveZone, RiskEvent, Site
from app.schemas import SiteOut
from app.services.geo import to_geojson_feature, to_geojson_feature_collection
from app.services.lookups import get_site_or_404

router = APIRouter(prefix="/sites", tags=["sites"])


def _site_to_out(db: Session, site: Site) -> SiteOut:
    point = to_shape(site.centroid)

    active_risk_count = (
        db.scalar(
            select(func.count())
            .select_from(RiskEvent)
            .where(RiskEvent.site_id == site.id, RiskEvent.resolved.is_(False))
        )
        or 0
    )

    avg_confidence = db.scalar(
        select(func.avg(ReserveZone.confidence_score)).where(
            ReserveZone.site_id == site.id
        )
    )

    return SiteOut(
        id=site.id,
        name=site.name,
        belt_name=site.belt_name,
        district=site.district,
        state=site.state,
        centroid_lat=point.y,
        centroid_lon=point.x,
        active_risk_count=active_risk_count,
        avg_reserve_confidence=(
            round(avg_confidence, 3) if avg_confidence is not None else None
        ),
    )


@router.get("", response_model=list[SiteOut], summary="List all mine sites")
def list_sites(db: Session = Depends(get_db)) -> list[SiteOut]:
    """Return every mine site with its live active-risk count and average
    reserve confidence.
    """
    sites = db.scalars(select(Site).order_by(Site.name)).all()
    return [_site_to_out(db, site) for site in sites]


@router.get(
    "/geojson",
    summary="Get all sites' boundaries as GeoJSON",
    response_description="A GeoJSON FeatureCollection with one Feature per site polygon",
)
def list_sites_geojson(db: Session = Depends(get_db)) -> dict:
    """Return every site's boundary polygon as a single GeoJSON
    FeatureCollection, ready for direct use as a MapLibre GeoJSON source.

    Registered ahead of `/{site_id}` so the literal path `geojson` is never
    swallowed by the `site_id: int` path converter.
    """
    sites = db.scalars(select(Site).order_by(Site.name)).all()
    return to_geojson_feature_collection(
        sites,
        "geom",
        lambda s: {"id": s.id, "name": s.name, "belt_name": s.belt_name},
    )


@router.get("/{site_id}", response_model=SiteOut, summary="Get a single mine site")
def get_site(site_id: int, db: Session = Depends(get_db)) -> SiteOut:
    """Return one mine site by id, or 404 if it doesn't exist."""
    site = get_site_or_404(db, site_id)
    return _site_to_out(db, site)


@router.get(
    "/{site_id}/geojson",
    summary="Get a site's boundary as GeoJSON",
    response_description="A GeoJSON FeatureCollection with a single Feature for the site polygon",
)
def get_site_geojson(site_id: int, db: Session = Depends(get_db)) -> dict:
    """Return the site's boundary polygon as a GeoJSON FeatureCollection, ready
    for direct use as a MapLibre GeoJSON source.
    """
    site = get_site_or_404(db, site_id)
    feature = to_geojson_feature(
        site, "geom", {"id": site.id, "name": site.name, "belt_name": site.belt_name}
    )
    return {"type": "FeatureCollection", "features": [feature]}
