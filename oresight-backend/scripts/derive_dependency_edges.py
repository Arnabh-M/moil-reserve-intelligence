"""Manually derive scheduling-dependency edges in Neo4j for the cascade /
ripple-impact feature (see app/services/dependency_derivation.py and
app/services/cascade_service.py).

Idempotent (every write is a MERGE) — safe to re-run any time a BlastPlan's
scheduled_date changes. Deliberately NOT wired into app startup, the
scheduler, or any request path — this must never add latency to a
recommendation request. Run it manually after seeding/reseeding data, or
whenever blast schedules change.

Run from oresight-backend/:
    python -m scripts.derive_dependency_edges
    python -m scripts.derive_dependency_edges --site-id 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dependency_derivation import derive_dependency_edges  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-id", type=int, default=None,
        help="Postgres sites.id to scope derivation to (default: all sites)",
    )
    args = parser.parse_args()

    report = derive_dependency_edges(site_id=args.site_id)

    print("Dependency edge derivation report:")
    for edge_report in report.edge_reports:
        if edge_report.skipped:
            print(f"  SKIPPED  {edge_report.edge_type}: {edge_report.skip_reason}")
        else:
            print(f"  OK       {edge_report.edge_type}: {edge_report.total_edges} edge(s)")


if __name__ == "__main__":
    main()
