"""Scenario A for the demo: weather-driven production-shortfall risk at
Balaghat ("reschedule" story).

REVISION HISTORY / WHY THIS ISN'T A SIMPLER SCRIPT
----------------------------------------------------
v1 reused re_bal_01 for the RiskEvent. That pulled in an unrelated
Compressor-failure branch (eq_bal_05 -CAUSES-> re_bal_01, from a different
BlastPlan) via the causal-graph endpoint's 3-hop *undirected* traversal,
producing a 9-node graph instead of the intended 4-6.

v2 (this version) gives Scenario A a fully dedicated RiskEvent, BlastPlan,
and OreZone instead — NOT just a dedicated RiskEvent. That extra step is
necessary, not cosmetic: bp_bal_01 (the existing Balaghat BlastPlan) has
DEPENDS_ON edges from eq_bal_01 (Excavator) and eq_bal_02 (Drill) baked
into the original seed_graph.cypher. Since a WeatherEvent-DELAYS->BlastPlan
edge must keep BlastPlan within 2 hops of the RiskEvent root for
WeatherEvent to stay inside the endpoint's 3-hop budget, ANY RiskEvent
chain that reuses bp_bal_01 -- regardless of which node it's freshly
created around -- will always pull those two equipment nodes back in.
Same problem one hop further out for oz_bal_01, which sits directly next
to bp_bal_01. So this version only reuses two nodes verified safe by
direct query (see the conversation this script came out of):
  - WeatherEvent we_bal_01 -- reused, but sits at the *far* hop (hop 3) of
    the new chain, so its other edges (DELAYS to the old bp_bal_01,
    CORRELATES_WITH to re_bal_01) fall at hop 4+ and never surface.
  - MineSite 'balaghat' -- reused; had zero edges in the original seed, so
    there is nothing else on it to leak in (the earlier version's stray
    oz_bal_01 -LOCATED_IN-> MineSite edge is removed by this script since
    Scenario A no longer touches oz_bal_01 at all).

re_bal_01 is explicitly reverted to its pre-v1 state (external_ref
removed, original score/description restored) -- v1 mutated it, and it was
never supposed to be touched.

Fresh, dedicated nodes created for this scenario:
  - BlastPlan  bp_bal_rain_01
  - OreZone    oz_bal_rain_01 (same confidence_score/grade_estimate as
    oz_bal_01, since narratively it's "the same zone" -- just not the same
    graph node, to keep this subgraph isolated)
  - RiskEvent  risk_event_balaghat_rain_01, external_ref = the Postgres
    risk_events.id created below

Idempotent: re-running finds the existing Postgres row by
(site, risk_type, description) instead of inserting a duplicate, and every
Neo4j write is a MERGE.

Run from oresight-backend/:
    python -m scripts.seed_scenario_a
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.agents._bridge import pg_site_to_neo4j_id, severity_from_score  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.graph_db import init_graph_driver  # noqa: E402
from app.models import RiskEvent, RiskSeverity, Site  # noqa: E402

RISK_SCORE = 0.72
RISK_DESCRIPTION = (
    "Heavy rainfall forecast delays blasting at Balaghat, projected 12% "
    "output reduction over 5 days"
)

WEATHER_EVENT_ID = "we_bal_01"  # reused: verified safe, sits at the far hop
BLAST_PLAN_ID = "bp_bal_rain_01"  # dedicated: bp_bal_01 has unrelated equipment deps
ORE_ZONE_ID = "oz_bal_rain_01"  # dedicated: sits directly next to bp_bal_01
RISK_EVENT_NODE_ID = "risk_event_balaghat_rain_01"  # dedicated (this fix's whole point)

# Nodes this script must leave untouched other than the two explicit,
# verified-safe reuses above.
OLD_RISK_EVENT_ID = "re_bal_01"
OLD_ORE_ZONE_ID = "oz_bal_01"


def main() -> None:
    db = SessionLocal()
    driver = init_graph_driver()
    try:
        balaghat = db.scalar(select(Site).where(Site.district.ilike("balaghat")))
        if balaghat is None:
            raise SystemExit("No Postgres site with district='Balaghat' found.")

        pg_row = db.scalar(
            select(RiskEvent).where(
                RiskEvent.site_id == balaghat.id,
                RiskEvent.risk_type == "production_shortfall",
                RiskEvent.description == RISK_DESCRIPTION,
            )
        )
        if pg_row is None:
            pg_row = RiskEvent(
                site_id=balaghat.id,
                risk_type="production_shortfall",
                severity=RiskSeverity(severity_from_score(RISK_SCORE)),
                score=RISK_SCORE,
                description=RISK_DESCRIPTION,
                source_entity_type="weather",
                resolved=False,
            )
            db.add(pg_row)
            db.commit()
            db.refresh(pg_row)
            print(f"Postgres: created risk_events.id={pg_row.id} at site {balaghat.name}")
        else:
            print(f"Postgres: reusing existing risk_events.id={pg_row.id} (idempotent re-run)")

        neo4j_site_id = pg_site_to_neo4j_id(balaghat)
        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=2)
        end_date = start_date + timedelta(days=5)
        blast_scheduled_date = start_date + timedelta(days=3)

        with driver.session() as session:
            # --- revert v1's mutation of re_bal_01 --------------------------
            session.run(
                """
                MATCH (r:RiskEvent {id: $risk_id})
                SET r.external_ref = null,
                    r.score = 0.78,
                    r.description = 'Heavy rain (severity 5) at Balaghat delayed '
                        + 'BlastPlan bp_bal_01, threatening OreZone oz_bal_01 '
                        + 'extraction schedule.'
                """,
                risk_id=OLD_RISK_EVENT_ID,
            )
            # --- remove v1's stray edge off the OLD OreZone (Scenario A no
            # longer touches oz_bal_01 at all) ------------------------------
            session.run(
                """
                MATCH (z:OreZone {id: $zone_id})-[rel:LOCATED_IN]->(:MineSite)
                DELETE rel
                """,
                zone_id=OLD_ORE_ZONE_ID,
            )

            # --- (re)set the reused WeatherEvent's live-demo dates ----------
            session.run(
                """
                MATCH (w:WeatherEvent {id: $weather_id})
                SET w.start_date = date($start_date), w.end_date = date($end_date), w.severity = 4
                """,
                weather_id=WEATHER_EVENT_ID,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )

            # --- dedicated BlastPlan / OreZone / RiskEvent -------------------
            session.run(
                """
                MERGE (b:BlastPlan {id: $blast_id})
                SET b.site_id = $site_id, b.scheduled_date = date($scheduled_date), b.status = 'delayed'
                """,
                blast_id=BLAST_PLAN_ID,
                site_id=neo4j_site_id,
                scheduled_date=blast_scheduled_date.isoformat(),
            )
            session.run(
                """
                MERGE (z:OreZone {id: $zone_id})
                SET z.site_id = $site_id, z.confidence_score = 0.82, z.grade_estimate = 38.5
                """,
                zone_id=ORE_ZONE_ID,
                site_id=neo4j_site_id,
            )
            session.run(
                """
                MERGE (r:RiskEvent {external_ref: $external_ref})
                ON CREATE SET r.id = $risk_id
                SET r.site_id = $site_id, r.risk_type = 'production_shortfall',
                    r.score = $score, r.description = $description,
                    r.detected_at = datetime($detected_at)
                """,
                external_ref=str(pg_row.id),
                risk_id=RISK_EVENT_NODE_ID,
                site_id=neo4j_site_id,
                score=RISK_SCORE,
                description=RISK_DESCRIPTION,
                detected_at=pg_row.detected_at.isoformat(),
            )

            # --- the isolated chain ------------------------------------------
            session.run(
                """
                MATCH (w:WeatherEvent {id: $weather_id}), (b:BlastPlan {id: $blast_id})
                MERGE (w)-[:DELAYS]->(b)
                """,
                weather_id=WEATHER_EVENT_ID,
                blast_id=BLAST_PLAN_ID,
            )
            session.run(
                """
                MATCH (b:BlastPlan {id: $blast_id}), (z:OreZone {id: $zone_id})
                MERGE (b)-[:AFFECTS]->(z)
                """,
                blast_id=BLAST_PLAN_ID,
                zone_id=ORE_ZONE_ID,
            )
            session.run(
                """
                MATCH (z:OreZone {id: $zone_id}), (r:RiskEvent {external_ref: $external_ref})
                MERGE (z)-[:CAUSES]->(r)
                """,
                zone_id=ORE_ZONE_ID,
                external_ref=str(pg_row.id),
            )
            session.run(
                """
                MATCH (z:OreZone {id: $zone_id}), (s:MineSite {id: $site_id})
                MERGE (z)-[:LOCATED_IN]->(s)
                """,
                zone_id=ORE_ZONE_ID,
                site_id=neo4j_site_id,
            )

        print("Neo4j graph updated. Running the endpoint's own 3-hop traversal...\n")

        with driver.session() as session:
            record = session.run(
                """
                MATCH (r:RiskEvent {external_ref: $external_ref})
                OPTIONAL MATCH path = (r)-[*1..3]-(n)
                RETURN r AS root, collect(path) AS paths
                """,
                external_ref=str(pg_row.id),
            ).single()

            node_ids = set()
            edges = []
            root_props = dict(record["root"])
            node_ids.add(root_props["id"])
            for path in record["paths"]:
                if path is None:
                    continue
                for node in path.nodes:
                    node_ids.add(dict(node).get("id"))
                for rel in path.relationships:
                    edges.append(
                        (dict(rel.start_node).get("id"), rel.type, dict(rel.end_node).get("id"))
                    )
            edges = sorted(set(edges))

            print(f"Node count: {len(node_ids)}  |  Edge count: {len(edges)}")
            print(f"Nodes: {sorted(node_ids)}")
            print("Edges:")
            for e in edges:
                print(f"   {e[0]} -[{e[1]}]-> {e[2]}")

        print(f"\nDone. Postgres risk_events.id = {pg_row.id}, Neo4j RiskEvent id = {RISK_EVENT_NODE_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
