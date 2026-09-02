"""GET /demo/scenarios — resolve the seeded demo scenarios to their CURRENT
risk_events.id.

`risk_events.id` is an autoincrement and shifts every time
scripts/rebuild_demo_db.py runs (Drill-down has been 49 and 8; the rainfall
scenario 95 and 7). Rather than have every consumer hardcode an id, this
endpoint maps a stable `key` to whatever row the seed scripts produced this
rebuild, matching on the same (site, risk_type, description) heuristic
scripts/seed_scenario_a.py / seed_scenario_b.py use to find-or-create those
rows.

Purely additive: no change to the risk_events table or to
GET /risk-events / GET /risk-events/{id}.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RiskEvent, Site
from app.schemas import DemoScenarioOut

router = APIRouter(prefix="/demo", tags=["demo"])


@dataclass(frozen=True)
class _ScenarioSpec:
    key: str
    scenario_name: str
    site_district: str          # matched case-insensitively against Site.district
    risk_type: str
    description_like: str        # SQL ILIKE pattern against RiskEvent.description
    expected_recommendation: str


# The two scenarios seeded by scripts/seed_scenario_a.py and
# scripts/seed_scenario_b.py. Add a row here to expose another.
_SCENARIOS: tuple[_ScenarioSpec, ...] = (
    _ScenarioSpec(
        key="weather-delay",
        scenario_name="Rainfall delay -> reschedule (Balaghat)",
        site_district="balaghat",
        risk_type="production_shortfall",
        description_like="%rainfall forecast delays blasting%",
        expected_recommendation="reschedule",
    ),
    _ScenarioSpec(
        key="equipment-down",
        scenario_name="Equipment down -> redeploy (Nagpur)",
        site_district="nagpur",
        risk_type="equipment_failure",
        description_like="%NAG-1 at Nagpur is down%",
        expected_recommendation="redeploy",
    ),
)


def _resolve(db: Session, spec: _ScenarioSpec) -> DemoScenarioOut:
    row = db.execute(
        select(RiskEvent, Site)
        .join(Site, RiskEvent.site_id == Site.id)
        .where(
            Site.district.ilike(spec.site_district),
            RiskEvent.risk_type == spec.risk_type,
            RiskEvent.description.ilike(spec.description_like),
            RiskEvent.resolved.is_(False),
        )
        .order_by(RiskEvent.id.asc())
    ).first()

    if row is None:
        return DemoScenarioOut(
            key=spec.key,
            scenario_name=spec.scenario_name,
            available=False,
            risk_event_id=None,
            site_id=None,
            site_name=None,
            risk_type=None,
            description=None,
            expected_recommendation=spec.expected_recommendation,
        )

    risk_event, site = row
    return DemoScenarioOut(
        key=spec.key,
        scenario_name=spec.scenario_name,
        available=True,
        risk_event_id=risk_event.id,
        site_id=site.id,
        site_name=site.name,
        risk_type=risk_event.risk_type,
        description=risk_event.description,
        expected_recommendation=spec.expected_recommendation,
    )


@router.get(
    "/scenarios",
    response_model=list[DemoScenarioOut],
    summary="Resolve seeded demo scenarios to their current risk_event ids",
)
def list_demo_scenarios(db: Session = Depends(get_db)) -> list[DemoScenarioOut]:
    """Return the demo scenarios with their live `risk_event_id`. Every
    configured scenario is always listed; `available: false` means its seed
    script hasn't been run against this database.
    """
    return [_resolve(db, spec) for spec in _SCENARIOS]
