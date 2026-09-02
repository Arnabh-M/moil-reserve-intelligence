"""Retroactively build Neo4j graph structure around existing Postgres
risk_events.id=5 (Haul Truck HT-302 engine overheating, Nagpur) for the
demo's "redeploy" scenario (Scenario B).

Does NOT touch Postgres — risk_event id=5 already exists there and stays
exactly as-is. This script only adds Neo4j nodes/edges and links them back
via `external_ref`, following the same `re_<neo4j_site_id>_<pg_id>` node-id /
`external_ref=str(pg_id)` convention app/agents/watcher.py already uses for
newly-detected risk events, so GET /risk-events/5/causal-graph picks it up
as a real "neo4j" graph instead of the current single-node
"postgres_fallback".

Idempotent: every write is a MERGE keyed on a stable identity (pg_id on
Equipment, external_ref on RiskEvent), so re-running this after the first
successful run changes nothing.

Run from oresight-backend/:
    python -m scripts.enrich_risk_event_5
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.agents._bridge import pg_site_to_neo4j_id  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.graph_db import init_graph_driver  # noqa: E402
from app.models import Equipment, RiskEvent, Site  # noqa: E402

RISK_EVENT_PG_ID = 5
TARGET_EQUIPMENT_NAME = "Haul Truck HT-302"


def main() -> None:
    db = SessionLocal()
    driver = init_graph_driver()
    try:
        risk_event = db.get(RiskEvent, RISK_EVENT_PG_ID)
        if risk_event is None:
            print(
                f"SKIP: Postgres risk_events.id={RISK_EVENT_PG_ID} not found — nothing to enrich. "
                "(Expected only if app.seed_dev wasn't run.)"
            )
            return

        nagpur_site = db.scalar(select(Site).where(Site.id == risk_event.site_id))
        down_equipment = db.scalar(
            select(Equipment).where(
                Equipment.site_id == nagpur_site.id,
                Equipment.name == TARGET_EQUIPMENT_NAME,
            )
        )
        if down_equipment is None:
            # Not fatal: scripts/import_p2_data.py replaces the equipment roster
            # with seed_graph.cypher's 15 units, which has no Haul Truck. If
            # seed_dev.py isn't re-run afterwards this row genuinely doesn't
            # exist — warn and skip rather than abort a full rebuild mid-chain.
            print(
                f"SKIP: no Postgres equipment row named {TARGET_EQUIPMENT_NAME!r} at "
                f"{nagpur_site.name} — the Haul Truck redeploy scenario is unavailable. "
                "(Re-run app.seed_dev after scripts.import_p2_data to restore it.)"
            )
            return

        bhandara_site = db.scalar(select(Site).where(Site.district.ilike("bhandara")))
        idle_candidate = db.scalar(
            select(Equipment)
            .where(Equipment.site_id == bhandara_site.id)
            .where(Equipment.status == "up")
            .where(Equipment.equipment_type.ilike(down_equipment.equipment_type))
        )
        if idle_candidate is None:
            print(
                f"SKIP: no idle (status='up') {down_equipment.equipment_type!r}-type equipment "
                "found at Bhandara — cannot seed a redeploy candidate."
            )
            return

        nagpur_neo4j_id = pg_site_to_neo4j_id(nagpur_site)
        bhandara_neo4j_id = pg_site_to_neo4j_id(bhandara_site)
        risk_node_id = f"re_{nagpur_neo4j_id}_{risk_event.id}"

        print("Postgres source data:")
        print(
            f"  risk_event id={risk_event.id}: {risk_event.description!r} "
            f"(severity={risk_event.severity.value}, score={risk_event.score})"
        )
        print(
            f"  down equipment: id={down_equipment.id} {down_equipment.name!r} "
            f"({down_equipment.equipment_type}) @ {nagpur_site.name}"
        )
        print(
            f"  idle candidate: id={idle_candidate.id} {idle_candidate.name!r} "
            f"({idle_candidate.equipment_type}) @ {bhandara_site.name}"
        )
        print()

        with driver.session() as session:
            # Equipment nodes keyed on pg_id (the Postgres id) rather than name/type
            # matching — a hard, unambiguous link back to the source-of-truth row,
            # same spirit as external_ref on RiskEvent below.
            session.run(
                """
                MERGE (e:Equipment {pg_id: $pg_id})
                ON CREATE SET
                    e.id = $node_id, e.site_id = $site_id, e.name = $name,
                    e.type = $type, e.status = $status
                ON MATCH SET
                    e.status = $status, e.name = $name, e.type = $type
                """,
                pg_id=down_equipment.id,
                node_id=f"eq_{nagpur_neo4j_id}_06",
                site_id=nagpur_neo4j_id,
                name=down_equipment.name,
                # Use Postgres's own equipment_type string verbatim (not a
                # hand-picked "Haul Truck" literal) — planner.py's redeploy
                # search matches case-insensitively but does NOT normalize
                # word separators, so a Neo4j "Haul Truck" (space) vs
                # Postgres "haul_truck" (underscore) silently fails to match.
                # Bit us once already; keeping this verbatim avoids repeating it.
                type=down_equipment.equipment_type,
                status=down_equipment.status.value,
            )

            session.run(
                """
                MERGE (e:Equipment {pg_id: $pg_id})
                ON CREATE SET
                    e.id = $node_id, e.site_id = $site_id, e.name = $name,
                    e.type = $type, e.status = $status
                ON MATCH SET
                    e.status = $status, e.name = $name, e.type = $type
                """,
                pg_id=idle_candidate.id,
                node_id=f"eq_{bhandara_neo4j_id}_06",
                site_id=bhandara_neo4j_id,
                name=idle_candidate.name,
                type=idle_candidate.equipment_type,
                status=idle_candidate.status.value,
            )

            session.run(
                """
                MATCH (s:MineSite {id: $site_id})
                MERGE (r:RiskEvent {external_ref: $external_ref})
                ON CREATE SET
                    r.id = $node_id, r.site_id = $site_id, r.risk_type = $risk_type,
                    r.score = $score, r.description = $description,
                    r.detected_at = datetime($detected_at)
                """,
                site_id=nagpur_neo4j_id,
                external_ref=str(risk_event.id),
                node_id=risk_node_id,
                risk_type=risk_event.risk_type,
                score=risk_event.score,
                description=risk_event.description,
                detected_at=risk_event.detected_at.isoformat(),
            )

            session.run(
                """
                MATCH (e:Equipment {pg_id: $eq_pg_id})
                MATCH (r:RiskEvent {external_ref: $external_ref})
                MERGE (e)-[:CAUSES]->(r)
                """,
                eq_pg_id=down_equipment.id,
                external_ref=str(risk_event.id),
            )

        print("Neo4j graph enriched. Running verification queries...\n")

        with driver.session() as session:
            print("1) RiskEvent {external_ref:'5'} -> causing Equipment:")
            for row in session.run(
                """
                MATCH (e:Equipment)-[:CAUSES]->(r:RiskEvent {external_ref: $external_ref})
                RETURN e.id AS equipment_id, e.name AS equipment_name, e.status AS equipment_status,
                       r.id AS risk_event_id, r.description AS description
                """,
                external_ref=str(risk_event.id),
            ):
                print(f"   {dict(row)}")

            print(
                "\n2) Bhandara idle redeploy candidate "
                "(case-insensitive type match, no DEPENDS_ON in next 7 days):"
            )
            for row in session.run(
                """
                MATCH (down:Equipment {pg_id: $down_pg_id})
                MATCH (idle:Equipment {site_id: $bhandara_id})
                WHERE toLower(idle.type) = toLower(down.type)
                  AND idle.status = 'up'
                  AND NOT EXISTS {
                      MATCH (idle)-[:DEPENDS_ON]->(bp:BlastPlan)
                      WHERE bp.scheduled_date <= date() + duration('P7D')
                  }
                RETURN idle.id AS equipment_id, idle.name AS equipment_name,
                       idle.type AS type, idle.status AS status
                """,
                down_pg_id=down_equipment.id,
                bhandara_id=bhandara_neo4j_id,
            ):
                print(f"   {dict(row)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
