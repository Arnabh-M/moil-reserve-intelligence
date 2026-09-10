"""Derive additive, idempotent scheduling-dependency edges in Neo4j, for the
cascade/ripple-impact feature (see app/services/cascade_service.py).

WHY THIS DERIVES ONLY ONE NEW EDGE TYPE
-----------------------------------------
The original design called for four new edge types (DEPENDS_ON zone->blast,
COMMITTED_TO, TARGETS, SCHEDULED_ON). Discovery against the real graph and
Postgres schema found:

- `DEPENDS_ON` already exists in this graph as (Equipment)-[:DEPENDS_ON]->
  (BlastPlan) (see seed_graph.cypher). Introducing a second, differently-
  directed DEPENDS_ON (OreZone->BlastPlan) would silently change what the
  edge type means — forbidden by this feature's own scope rules. The fact it
  would have encoded is already captured by the existing
  (BlastPlan)-[:AFFECTS]->(OreZone) edge (reversed); cascade traversal reads
  that instead.
- `COMMITTED_TO` (Equipment->BlastPlan) would be a straight duplicate of the
  existing (Equipment)-[:DEPENDS_ON]->(BlastPlan) edge — there is no
  equipment-assignment table in Postgres to derive it from independently,
  and deriving a second edge for the same fact would just be noise. Cascade
  traversal reads the existing DEPENDS_ON edge instead.
- `TARGETS` (OreZone->ProductionTarget) cannot be derived at all: no
  ProductionTarget entity exists anywhere, and Postgres `production_records`
  has no zone-level foreign key (only site_id) — `target_output` is a
  site-level column, not a per-zone record. Deriving this would fabricate a
  data granularity that does not exist, which this feature's rules
  explicitly forbid. Skipped and reported below.

The one edge that genuinely does not exist and is needed — SCHEDULED_ON
(BlastPlan -> CalendarDate) — is derived here, from each BlastPlan's own
`scheduled_date` property (already present in Neo4j; no Postgres read is
needed since BlastPlan and Postgres's BlastEvent table have no established
id bridge, unlike Site and Equipment).

Every derived edge/node carries `derived: true` and `derived_at` so it is
always distinguishable from edges written at Watcher fact-log time. All
writes use MERGE, so re-running this is a no-op after the first run.

MANUAL TRIGGER ONLY. Do not call this from a request path, app startup, or
the scheduler. Run it via `python -m scripts.derive_dependency_edges` from
oresight-backend/.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from neo4j import Driver

from app.agents._bridge import pg_site_to_neo4j_id
from app.db import SessionLocal
from app.graph_db import get_graph_driver
from app.models import Site

logger = logging.getLogger("oresight.graph.dependency_derivation")


@dataclass
class EdgeTypeReport:
    edge_type: str
    # Total edges of this type matching the derivation rule after the MERGE
    # (i.e. present now, whether created this run or already there from a
    # prior run) — MERGE makes this idempotent, so re-running never inflates it.
    total_edges: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class DerivationReport:
    edge_reports: list[EdgeTypeReport] = field(default_factory=list)

    @property
    def skipped(self) -> list[EdgeTypeReport]:
        return [r for r in self.edge_reports if r.skipped]


_SKIPPED_EDGE_TYPES = (
    (
        "DEPENDS_ON (OreZone->BlastPlan)",
        "Existing DEPENDS_ON already means (Equipment)->(BlastPlan) in this graph "
        "(seed_graph.cypher) — reusing the name for a different meaning would change "
        "an existing edge type's meaning. The equivalent fact is already captured by "
        "the existing (BlastPlan)-[:AFFECTS]->(OreZone) edge; cascade traversal reads "
        "that instead of deriving a new edge.",
    ),
    (
        "COMMITTED_TO",
        "No equipment-assignment table exists in Postgres to derive this from "
        "independently. The same fact is already captured by the existing "
        "(Equipment)-[:DEPENDS_ON]->(BlastPlan) edge written at seed/import time; "
        "deriving a second edge for it would be a duplicate, not new information.",
    ),
    (
        "TARGETS",
        "No ProductionTarget entity exists anywhere, and Postgres production_records "
        "has no zone-level foreign key (only site_id) — target_output is a site-level "
        "column, not a per-zone record. Deriving a zone-level TARGETS edge would "
        "fabricate data granularity that does not exist.",
    ),
)


def derive_dependency_edges(site_id: int | None = None) -> DerivationReport:
    """Derive SCHEDULED_ON (BlastPlan->CalendarDate) edges for every
    BlastPlan with a scheduled_date, scoped to `site_id` (a Postgres
    sites.id) if given, else all sites. Idempotent — safe to re-run.

    Reports the other three originally-proposed edge types as skipped (see
    module docstring for why) rather than silently doing nothing for them.
    """
    report = DerivationReport()
    report.edge_reports.append(_derive_scheduled_on(site_id))
    for edge_type, reason in _SKIPPED_EDGE_TYPES:
        report.edge_reports.append(EdgeTypeReport(edge_type=edge_type, skipped=True, skip_reason=reason))
    return report


def _derive_scheduled_on(site_id: int | None) -> EdgeTypeReport:
    edge_report = EdgeTypeReport(edge_type="SCHEDULED_ON")

    neo4j_site_id = None
    if site_id is not None:
        db = SessionLocal()
        try:
            site = db.get(Site, site_id)
            if site is None:
                edge_report.skipped = True
                edge_report.skip_reason = f"site_id={site_id} not found in Postgres"
                return edge_report
            neo4j_site_id = pg_site_to_neo4j_id(site)
        finally:
            db.close()

    try:
        driver = get_graph_driver()
        with driver.session() as session:
            row = session.run(
                """
                MATCH (b:BlastPlan)
                WHERE b.scheduled_date IS NOT NULL
                  AND ($site_id IS NULL OR b.site_id = $site_id)
                WITH b, toString(b.scheduled_date) AS iso_date
                MERGE (d:CalendarDate {date: iso_date})
                MERGE (b)-[rel:SCHEDULED_ON]->(d)
                ON CREATE SET rel.derived = true, rel.derived_at = datetime()
                RETURN count(rel) AS total
                """,
                site_id=neo4j_site_id,
            ).single()
        edge_report.total_edges = row["total"] if row else 0
    except Exception:  # noqa: BLE001 - a derivation failure must not crash the caller
        edge_report.skipped = True
        edge_report.skip_reason = "Neo4j query failed — see logs"
        logger.exception("SCHEDULED_ON derivation failed")

    return edge_report
