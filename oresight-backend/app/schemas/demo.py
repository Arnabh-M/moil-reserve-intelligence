"""Schema for the demo-scenario lookup.

Lets the frontend / demo script address the two seeded demo risk events by a
stable `key` instead of an autoincrement `risk_events.id` that shifts on
every `rebuild_demo_db.py` run.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DemoScenarioOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "key": "equipment-down",
                "scenario_name": "Equipment down -> redeploy (Nagpur)",
                "available": True,
                "risk_event_id": 8,
                "site_id": 2,
                "site_name": "Nagpur",
                "risk_type": "equipment_failure",
                "description": "Drill NAG-1 at Nagpur is down: Hydraulic fault - demo seed",
                "expected_recommendation": "redeploy",
            }
        },
    )

    key: str
    scenario_name: str
    # False when the seed for this scenario hasn't run — every configured
    # scenario is always listed so a missing seed is visible, not silent.
    available: bool
    risk_event_id: int | None
    site_id: int | None
    site_name: str | None
    risk_type: str | None
    description: str | None
    # What GET /recommendations?risk_event_id=<risk_event_id> is expected to
    # lead with, so a wired-up UI can assert it didn't regress.
    expected_recommendation: str
