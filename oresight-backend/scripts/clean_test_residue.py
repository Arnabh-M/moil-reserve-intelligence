"""Remove risk events that tests or manual toggling leave behind, so a pre-demo rebuild is clean.

    python -m scripts.clean_test_residue

Deletes (Postgres + the matching Neo4j RiskEvent nodes, and any shift-plan entries pointing at them):
  * equipment_failure events whose description carries the test suite's "Smoke test failure" reason
  * every equipment_flapping event (opened when a machine's status changes more than the flap threshold
    inside the window; nothing in the seed data creates one, so any present came from toggling)
Idempotent. Seeded risk events and real weather/production events are never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, or_, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import RiskEvent, ShiftPlanEntry  # noqa: E402


def clean() -> list[int]:
    db = SessionLocal()
    try:
        ids = list(
            db.scalars(
                select(RiskEvent.id).where(
                    or_(
                        RiskEvent.risk_type == "equipment_flapping",
                        (RiskEvent.risk_type == "equipment_failure") & RiskEvent.description.ilike("%Smoke test failure%"),
                    )
                )
            )
        )
        if ids:
            db.execute(delete(ShiftPlanEntry).where(ShiftPlanEntry.risk_event_id.in_(ids)))
            db.execute(delete(RiskEvent).where(RiskEvent.id.in_(ids)))
            db.commit()
            try:
                from app.graph_db import init_graph_driver

                with init_graph_driver().session() as session:
                    session.run("MATCH (r:RiskEvent) WHERE r.external_ref IN $refs DETACH DELETE r", refs=[str(i) for i in ids])
            except Exception as exc:  # noqa: BLE001 - the graph is rebuilt by load_graph anyway
                print(f"  (Neo4j cleanup skipped: {type(exc).__name__})")
        return ids
    finally:
        db.close()


if __name__ == "__main__":
    removed = clean()
    print(f"clean_test_residue: removed {len(removed)} leftover risk event(s) {removed}")
