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
  Unchanged by the equipment fix below.

- Equipment: RESOLVED as of scripts/import_p2_data.py. Postgres equipment
  used to be an independently-invented fleet (app/seed_dev.py) with
  different names ("Excavator EX-201") and a different type vocabulary
  (excavator/drill/haul_truck/crusher/loader) than Neo4j's Day 1 seed
  (excavator/drill/conveyor/loader/compressor). `find_neo4j_equipment_id`
  below returned None for haul_truck/crusher because there was genuinely no
  match — not a bug, just an unreconciled dataset.

  `scripts/import_p2_data.py` now sources Postgres equipment directly from
  seed_graph.cypher's 15-unit roster (same ids, names, and Title-Case types
  as Neo4j), so both sides describe the *same* fleet. haul_truck/crusher no
  longer exist in Postgres at all — they never existed in Neo4j either.
  `find_neo4j_equipment_id`'s (site, normalized-type) match below is now
  exact for every equipment row by construction: each site has exactly one
  of each of the 5 shared types on both sides. The function's logic didn't
  need to change, only this docstring's claim that some types can't match —
  if it ever returns None again after a fresh import, that indicates real
  drift (e.g. someone re-seeding one side but not the other), not an
  expected gap, and is worth investigating rather than shrugging off.
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
    """Match a Postgres equipment row to its Neo4j Equipment node by (site, type).

    Returns the node's `id` property, or None if no Neo4j equipment of that
    (normalized) type exists at the site. Since scripts/import_p2_data.py
    sources both fleets from the same seed_graph.cypher roster (see module
    docstring), this now succeeds for every equipment row — a None here is a
    signal of real drift between the two databases, not an expected gap.
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
