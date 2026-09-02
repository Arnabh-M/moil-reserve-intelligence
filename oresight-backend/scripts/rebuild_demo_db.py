"""One command to rebuild the entire demo database (Postgres + Neo4j) from
scratch, in the correct order, with no ordering footguns.

Run from oresight-backend/, with the Docker stack up (Postgres :5432,
Neo4j :7687) — a genuinely empty DB is fine, so is an existing one:

    python -m scripts.rebuild_demo_db

THE CHAIN (each step is a separate subprocess so state never leaks between
them — the same way a human would run them one at a time):

  1. alembic upgrade head        schema
  2. app.seed_dev                synthetic sites / equipment / production /
                                 reserve_zones / risk_events. Creates a full
                                 15-unit *synthetic* fleet incl. "Haul Truck
                                 HT-302" and "Excavator EX-201", and the two
                                 hardcoded down-units + their risk_events.
  3. scripts.import_p2_data      replaces equipment + production for the 3
                                 sites with the REAL data. NOTE: this DELETEs
                                 every equipment row for those sites and
                                 reinserts only seed_graph.cypher's 15-unit
                                 roster (Excavator/Drill/Conveyor/Loader/
                                 Compressor per site) — so it wipes step 2's
                                 synthetic fleet, including Haul Truck HT-302.
  4. app.seed_dev  (AGAIN)       << deliberate. seed_dev is skip-if-exists on
                                 (name, site); the roster from step 3 uses
                                 different names, so this second run RESTORES
                                 the synthetic fleet + the 2 down-units that
                                 step 3 deleted, without touching the real
                                 roster. Without this, enrich_risk_event_5
                                 has no Haul Truck HT-302 to build its
                                 redeploy scenario around.
  5. scripts.load_graph --reset  wipe + reload Neo4j from seed_graph.cypher.
  6. scripts.seed_scenario_a     Balaghat rainfall -> dedicated neo4j causal
                                 chain (WeatherEvent->BlastPlan->OreZone->
                                 RiskEvent) with external_ref.
  7. scripts.seed_scenario_b     Nagpur Drill-down realignment: Drill NAG-1
                                 down, Excavator NAG-1 up, the "NAG-1 is
                                 down" risk event pointed at the Drill, and
                                 the Haul Truck HT-302 risk-event FK repaired.
  8. scripts.enrich_risk_event_5 Neo4j nodes/edges around risk_events.id=5
                                 (Haul Truck HT-302) for its redeploy
                                 scenario. Skips gracefully if step 4 was
                                 removed and HT-302 is absent.

After this, both of these return a "redeploy" option:
  GET /recommendations?risk_event_id=<Drill NAG-1 "is down" event>   -> Drill BHD-1
  GET /recommendations?risk_event_id=<Haul Truck HT-302 event>       -> Haul Truck HT-303
and GET /risk-events/<Balaghat rainfall event>/causal-graph returns graph_source="neo4j".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

# (label, argv) — argv is run as `python <argv...>` from BACKEND_ROOT.
STEPS: list[tuple[str, list[str]]] = [
    ("alembic upgrade head", ["-m", "alembic", "upgrade", "head"]),
    ("app.seed_dev  (pass 1 — synthetic fleet + risk events)", ["-m", "app.seed_dev"]),
    ("scripts.import_p2_data  (real roster; DELETES synthetic fleet)", ["-m", "scripts.import_p2_data"]),
    ("app.seed_dev  (pass 2 — RESTORE synthetic fleet dropped by import_p2_data)", ["-m", "app.seed_dev"]),
    ("scripts.load_graph --reset  (wipe + reload Neo4j)", ["-m", "scripts.load_graph", "--reset"]),
    ("scripts.seed_scenario_a  (Balaghat rainfall causal chain)", ["-m", "scripts.seed_scenario_a"]),
    ("scripts.seed_scenario_b  (Nagpur Drill-down realignment + FK repair)", ["-m", "scripts.seed_scenario_b"]),
    ("scripts.enrich_risk_event_5  (Haul Truck HT-302 redeploy graph)", ["-m", "scripts.enrich_risk_event_5"]),
]


def main() -> int:
    print(f"Rebuilding demo DB — {len(STEPS)} steps, from {BACKEND_ROOT}\n")
    for i, (label, argv) in enumerate(STEPS, start=1):
        banner = f"[{i}/{len(STEPS)}] {label}"
        print("=" * len(banner))
        print(banner)
        print("=" * len(banner))
        result = subprocess.run([sys.executable, *argv], cwd=BACKEND_ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at step {i} ({label}) — exit {result.returncode}. Stopping.")
            return result.returncode
        print()

    print("All steps completed. Demo DB rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
