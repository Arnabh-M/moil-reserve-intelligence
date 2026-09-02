"""Scenario B for the demo: equipment-down "redeploy" story at Nagpur, and a
repair for a dangling risk_events FK.

WHY THIS SCRIPT EXISTS
----------------------
On 2026-09-02 the demo narrative was realigned by hand (raw SQL against the
live Docker DB) so that Postgres and Neo4j tell the *same* equipment-down
story. That change only lived in the running database — a `docker compose
down -v` or a fresh rebuild silently reverted it and broke the redeploy
recommendation. This script makes that realignment reproducible, in the same
idempotent style as scripts/seed_scenario_a.py and scripts/enrich_risk_event_5.py.

WHAT IT DOES (all Postgres-only; Neo4j already tells the Drill-down story in
seed_graph.cypher — eq_nag_02 Drill NAG-1 is `status: 'down'`, eq_bhd_02 Drill
BHD-1 is idle with no DEPENDS_ON edge, so it is a clean redeploy candidate):

1. Drill NAG-1 @ Nagpur  -> status='down', reason 'Hydraulic fault - demo seed'
   (mirrors Neo4j eq_nag_02). This is the failed unit the redeploy is *for*.
2. Excavator NAG-1 @ Nagpur -> status='up'. It used to be the (Excavator-down)
   demo subject; Neo4j never had an Excavator down at Nagpur, so it is reset
   here to keep the two stores consistent.
3. The Nagpur "… NAG-1 at Nagpur is down …" equipment_failure risk event is
   pointed at Drill NAG-1 (source_entity_id) and its description rewritten to
   the Drill-down text. Found-or-created: on the live DB this UPDATES the
   existing row (was "Excavator NAG-1 …"); on a fresh DB it CREATES it, since
   no script in the rebuild chain seeds this particular risk event.
   PlannerAgent keys the redeploy search off source_entity_id, so this is the
   line that actually makes GET /recommendations return a redeploy option.
4. Repair for risk_events "Haul Truck HT-302 …" (seed_dev.py seeds it, then
   scripts/import_p2_data.py deletes every equipment row for the 3 sites and
   reinserts only seed_graph.cypher's 15-unit roster — orphaning this risk
   event's source_entity_id). If a "Haul Truck HT-302" equipment row exists
   (i.e. seed_dev.py was re-run after import_p2_data), its id is written back
   onto the risk event so GET /recommendations?risk_event_id=<that> can find
   the failed unit and offer a redeploy (Haul Truck HT-303 @ Bhandara).
   If no such equipment row exists, this step logs a warning and skips — it
   never raises.

Nothing here is hardcoded to a specific id: every entity is looked up by
(name, site) or (site, risk_type, description substring), so it survives a
rebuild where ids differ.

Run from oresight-backend/ (after the stack is up and the DB is seeded):
    python -m scripts.seed_scenario_b
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Equipment, EquipmentStatus, RiskEvent, RiskSeverity, Site  # noqa: E402

NAGPUR_DISTRICT = "nagpur"

DOWN_EQUIPMENT_NAME = "Drill NAG-1"
RECOVERED_EQUIPMENT_NAME = "Excavator NAG-1"
DOWN_REASON = "Hydraulic fault - demo seed"
RECOVERED_REASON = "Recovered - demo narrative realignment (Excavator-down -> Drill-down)"

DRILL_RISK_DESCRIPTION = f"{DOWN_EQUIPMENT_NAME} at Nagpur is down: {DOWN_REASON}"
DRILL_RISK_SCORE = 0.7
DRILL_RISK_SEVERITY = RiskSeverity.HIGH

# Substring shared by the legacy "Excavator NAG-1 at Nagpur is down …" row and
# the realigned "Drill NAG-1 at Nagpur is down …" row, so a re-run matches the
# row it wrote last time instead of inserting a duplicate.
NAG_DOWN_DESC_LIKE = "%NAG-1 at Nagpur is down%"

HAUL_TRUCK_NAME = "Haul Truck HT-302"
HAUL_TRUCK_DESC_LIKE = "%Haul Truck HT-302%"


def _get_site(db, district: str) -> Site:
    site = db.scalar(select(Site).where(Site.district.ilike(district)))
    if site is None:
        raise SystemExit(f"No Postgres site with district ~ {district!r} found.")
    return site


def _get_equipment(db, site_id: int, name: str) -> Equipment | None:
    return db.scalar(
        select(Equipment).where(Equipment.site_id == site_id, Equipment.name == name)
    )


def _realign_equipment(db, nagpur: Site) -> Equipment:
    """Step 1 + 2. Returns the now-down Drill row."""
    now = datetime.now(timezone.utc)

    drill = _get_equipment(db, nagpur.id, DOWN_EQUIPMENT_NAME)
    if drill is None:
        raise SystemExit(
            f"No {DOWN_EQUIPMENT_NAME!r} at {nagpur.name} — is the equipment roster seeded "
            "(app.seed_dev / scripts.import_p2_data)?"
        )
    if drill.status != EquipmentStatus.DOWN or drill.status_reason != DOWN_REASON:
        drill.status = EquipmentStatus.DOWN
        drill.status_reason = DOWN_REASON
        drill.last_status_change = now
        print(f"  {DOWN_EQUIPMENT_NAME}: set status=down")
    else:
        print(f"  {DOWN_EQUIPMENT_NAME}: already down (no change)")

    excavator = _get_equipment(db, nagpur.id, RECOVERED_EQUIPMENT_NAME)
    if excavator is None:
        print(f"  {RECOVERED_EQUIPMENT_NAME}: not found — skipping (nothing to reset)")
    elif excavator.status != EquipmentStatus.UP:
        excavator.status = EquipmentStatus.UP
        excavator.status_reason = RECOVERED_REASON
        excavator.last_status_change = now
        print(f"  {RECOVERED_EQUIPMENT_NAME}: set status=up")
    else:
        print(f"  {RECOVERED_EQUIPMENT_NAME}: already up (no change)")

    db.flush()
    return drill


def _realign_risk_event(db, nagpur: Site, drill: Equipment) -> RiskEvent:
    """Step 3. Found-or-created Drill-down risk event, pointed at the Drill."""
    row = db.scalar(
        select(RiskEvent)
        .where(
            RiskEvent.site_id == nagpur.id,
            RiskEvent.risk_type == "equipment_failure",
            RiskEvent.resolved.is_(False),
            RiskEvent.description.ilike(NAG_DOWN_DESC_LIKE),
        )
        .order_by(RiskEvent.id.asc())
    )
    if row is None:
        row = RiskEvent(
            site_id=nagpur.id,
            risk_type="equipment_failure",
            severity=DRILL_RISK_SEVERITY,
            score=DRILL_RISK_SCORE,
            description=DRILL_RISK_DESCRIPTION,
            source_entity_type="equipment",
            source_entity_id=drill.id,
            resolved=False,
        )
        db.add(row)
        db.flush()
        print(f"  risk_events: created id={row.id} -> {DOWN_EQUIPMENT_NAME} (id={drill.id})")
        return row

    changed = []
    if row.source_entity_id != drill.id:
        changed.append(f"source_entity_id {row.source_entity_id} -> {drill.id}")
        row.source_entity_id = drill.id
    if row.source_entity_type != "equipment":
        row.source_entity_type = "equipment"
    if row.description != DRILL_RISK_DESCRIPTION:
        changed.append("description rewritten")
        row.description = DRILL_RISK_DESCRIPTION
    db.flush()
    if changed:
        print(f"  risk_events: updated id={row.id} ({'; '.join(changed)})")
    else:
        print(f"  risk_events: id={row.id} already realigned (no change)")
    return row


def _repair_haul_truck_fk(db, nagpur: Site) -> None:
    """Step 4. Best-effort repair of the orphaned Haul Truck HT-302 risk-event FK."""
    risk = db.scalar(
        select(RiskEvent)
        .where(RiskEvent.description.ilike(HAUL_TRUCK_DESC_LIKE))
        .order_by(RiskEvent.id.asc())
    )
    if risk is None:
        print("  haul-truck FK: no 'Haul Truck HT-302 …' risk event present — skipping")
        return

    truck = _get_equipment(db, nagpur.id, HAUL_TRUCK_NAME)
    if truck is None:
        print(
            f"  haul-truck FK: risk_events id={risk.id} references a {HAUL_TRUCK_NAME!r} that "
            "does not exist (seed_dev's second fleet was dropped by import_p2_data and not "
            "re-seeded) — leaving source_entity_id as-is"
        )
        return

    if risk.source_entity_id == truck.id and risk.source_entity_type == "equipment":
        print(f"  haul-truck FK: risk_events id={risk.id} already points at id={truck.id} (no change)")
        return

    old = risk.source_entity_id
    risk.source_entity_type = "equipment"
    risk.source_entity_id = truck.id
    db.flush()
    print(f"  haul-truck FK: risk_events id={risk.id} source_entity_id {old} -> {truck.id}")


def main() -> None:
    db = SessionLocal()
    try:
        nagpur = _get_site(db, NAGPUR_DISTRICT)
        print(f"Scenario B realignment @ {nagpur.name} (site_id={nagpur.id})")

        print("\n[1/3] equipment status")
        drill = _realign_equipment(db, nagpur)

        print("\n[2/3] Drill-down risk event")
        risk = _realign_risk_event(db, nagpur, drill)

        print("\n[3/3] Haul Truck HT-302 FK repair")
        _repair_haul_truck_fk(db, nagpur)

        db.commit()

        print("\nDone. Verify with:")
        print(f"  GET /recommendations?risk_event_id={risk.id}   (expect a 'redeploy' -> Drill BHD-1 from Bhandara)")
        haul = db.scalar(
            select(RiskEvent).where(RiskEvent.description.ilike(HAUL_TRUCK_DESC_LIKE)).order_by(RiskEvent.id.asc())
        )
        if haul is not None:
            print(f"  GET /recommendations?risk_event_id={haul.id}   (Haul Truck HT-302 -> expect 'redeploy' -> Haul Truck HT-303)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
