"""Shared helpers for bridging Postgres (twin state) and Neo4j (causal graph).

WHY THIS FILE EXISTS
---------------------
Postgres and Neo4j were seeded independently and use incompatible identity
schemes that don't line up automatically:

- Sites: Neo4j MineSite.id is a lowercase string ("balaghat", "nagpur",
  "bhandara"), set by Day 1's seed_graph.cypher. Postgres sites.id is an
  autoincrement int (see app/models/site.py), set by app/seed_dev.py.
  Fortunately Postgres Site.district happens to equal the Neo4j id when
  lowercased ("Balaghat" -> "balaghat"), so that's the bridge used here.

- Equipment: Neo4j Equipment nodes (Day 1 seed) and Postgres Equipment rows
  (app/seed_dev.py) are TWO DIFFERENT SYNTHETIC FLEETS that were never
  reconciled — different names ("Excavator BAL-1" vs "Excavator EX-201")
  AND different type vocabularies (Neo4j: excavator/drill/conveyor/loader/
  compressor; Postgres: excavator/drill/haul_truck/crusher/loader). There is
  no reliable 1:1 mapping. `find_neo4j_equipment_id` does a best-effort
  match by (site, normalized type) and returns None — not a guess — when no
  Neo4j equipment of that type exists at the site. Callers MUST handle None
  by omitting the graph edge rather than inventing one.

This gap is a real, pre-existing data-modeling issue, not something these
agents can silently paper over. It's called out here (and again wherever it
bites) so it doesn't get discovered the hard way during integration.
"""

from __future__ import annotations

import logging
import re

from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Site

logger = logging.getLogger("oresight.agents")


def pg_site_to_neo4j_id(site: Site) -> str:
    """Map a Postgres Site row to its Neo4j MineSite.id string."""
    basis = site.district or site.name
    return basis.strip().lower()


def neo4j_id_to_pg_site(db: Session, neo4j_site_id: str) -> Site | None:
    """Map a Neo4j MineSite.id string back to its Postgres Site row."""
    stmt = select(Site).where(Site.district.ilike(neo4j_site_id))
    return db.scalar(stmt)


def _normalize_type(equipment_type: str) -> str:
    return re.sub(r"[^a-z]", "", equipment_type.lower())


def find_neo4j_equipment_id(
    neo4j_driver: Driver,
    neo4j_site_id: str,
    equipment_type: str,
    status: str | None = None,
) -> str | None:
    """Best-effort match: find a Neo4j Equipment node at a site by type.

    Returns the node's `id` property, or None if no Neo4j equipment of
    that (normalized) type exists at the site — see module docstring.
    Excavator/Drill/Loader normalize the same way on both sides; Postgres's
    haul_truck/crusher and Neo4j's conveyor/compressor have no counterpart
    on the other side and will always return None here.
    """
    target = _normalize_type(equipment_type)
    query = "MATCH (e:Equipment {site_id: $site_id}) RETURN e.id AS id, e.type AS type, e.status AS status"
    with neo4j_driver.session() as session:
        rows = session.run(query, site_id=neo4j_site_id).data()

    for row in rows:
        if _normalize_type(row["type"]) == target:
            if status is not None and row["status"] != status:
                continue
            return row["id"]
    return None


def severity_from_score(score: float) -> str:
    """Map a 0-1 risk score to Postgres's RiskSeverity enum values."""
    if score >= 0.85:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"
