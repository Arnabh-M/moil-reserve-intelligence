"""Cascade / ripple-impact computation for a single recommendation option.

Deterministic graph traversal + rule evaluation — no model, no embedding, no
LLM call. The point of this feature is explainability: every number it
produces must be traceable to a specific graph path and a specific rule.

FAILURE CONTRACT (non-negotiable): `compute_cascade` NEVER raises. Any
problem — the target entity not existing in the graph, Neo4j being
unreachable, a query taking too long, an unrecognized action type — results
in `None`, logged with context. A cascade failure must never fail (or even
change the numbers on) the recommendation it was computed for.

EDGE TYPES REUSED, NOT REDEFINED — see app/services/dependency_derivation.py's
module docstring for the full reasoning. In short: `DEPENDS_ON` already means
(Equipment)-[:DEPENDS_ON]->(BlastPlan) in this graph (seed_graph.cypher), and
`AFFECTS` already means (BlastPlan)-[:AFFECTS]->(OreZone) — both are read
here as-is. The only edge this feature adds is `SCHEDULED_ON`
((BlastPlan)->(CalendarDate)); the date-collision check below queries
BlastPlan.scheduled_date directly instead of requiring that edge to exist,
so blocking detection works even before the derivation routine has been run.

INTERFACE NOTE: the task spec's signature for `compute_cascade` has no way
to receive the recommendation's own `projected_impact` (needed to produce
`cascade_adjusted_impact`) or a driver to query (needed for testability and
because this module must not import a live singleton at call time in
tests). Both are added here as optional keyword-only parameters that default
to sensible values, which is additive to the documented interface rather
than a breaking change to it.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any

from neo4j import Driver

from app.graph_db import get_graph_driver
from app.schemas.recommendation import CascadeResult, ImpactedEntity

logger = logging.getLogger("oresight.cascade")

# Measured, not guessed. The traversal itself is 14-57ms warm (target lookup
# 4-8ms, 2-hop BFS 13-19ms, conflict check 4-8ms). What dominates is the FIRST
# Cypher call in a fresh process: establishing the bolt connection measured
# 1776ms, with a second new-shape query at 1150ms. At the originally-suggested
# 2.0s that cold path intermittently tripped the timeout and returned a null
# cascade on the first request after a server restart — i.e. exactly the first
# click of a demo. 5s keeps a hard bound on the request while clearing cold
# start with margin.
HARD_TIMEOUT_SECONDS = 5.0
MAX_HOP_CAP = 3

# Structural edges walked to find what else is connected to the target
# entity. DEPENDS_ON/AFFECTS/CAUSES/CORRELATES_WITH/DELAYS are the EXISTING
# edge types this graph already writes (see seed_graph.cypher) — traversed
# read-only here, never redefined. SCHEDULED_ON is deliberately excluded:
# it only ever points at the entity's CURRENT date, so traversing it looks
# backward at what shares today's schedule, not forward at what would
# collide with a *proposed* one — the actual date-collision check below
# queries BlastPlan.scheduled_date directly instead.
_TRAVERSAL_EDGE_TYPES = ["DEPENDS_ON", "AFFECTS", "CAUSES", "CORRELATES_WITH", "DELAYS"]

_KNOWN_ACTION_TYPES = {"reschedule_plan", "redeploy_equipment", "adjust_plan"}

# Cascade severity is a simple, readable rule table — first match wins.
# Each rule takes (blocking_count, entities_affected).
_SEVERITY_RULES: tuple[tuple[str, Any], ...] = (
    ("high", lambda blocking, affected: blocking >= 1),
    ("moderate", lambda blocking, affected: blocking == 0 and affected >= 3),
    ("low", lambda blocking, affected: blocking == 0 and 1 <= affected <= 2),
    ("none", lambda blocking, affected: affected == 0),
)

# Heuristic prioritisation adjustment ONLY — not a calibrated probability.
# Scales the recommendation's existing `projected_impact` down as cascade
# severity rises, into a SEPARATE `cascade_adjusted_impact` field. The
# original `projected_impact` is never touched.
_SEVERITY_IMPACT_MULTIPLIER = {
    "none": 1.00,
    "low": 0.95,
    "moderate": 0.85,
    "high": 0.60,
}


def _cascade_severity(blocking_count: int, entities_affected: int) -> str:
    for severity, predicate in _SEVERITY_RULES:
        if predicate(blocking_count, entities_affected):
            return severity
    return "none"  # unreachable — the rules above are exhaustive


def compute_cascade(
    action_type: str,
    target_entity_id: str,
    proposed_change: dict,
    site_id: int,
    max_hops: int = 2,
    *,
    projected_impact: float | None = None,
    driver: Driver | None = None,
) -> CascadeResult | None:
    """Compute the downstream ripple of a proposed recommendation action.

    Read-only, side-effect free, and hard-capped at `HARD_TIMEOUT_SECONDS`
    wall-clock and `MAX_HOP_CAP` hops (`max_hops` is clamped to that, never
    extended). Returns `None` on any failure — see module docstring.
    """
    hop_limit = max(1, min(max_hops, MAX_HOP_CAP))
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(
            _compute_cascade_inner,
            action_type,
            target_entity_id,
            proposed_change or {},
            site_id,
            hop_limit,
            projected_impact,
            driver,
        )
        try:
            return future.result(timeout=HARD_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            # Logged at ERROR, not WARNING: this path silently produces a null
            # cascade (the card then renders no cascade section at all), which
            # is indistinguishable from "no ripple found" unless it is loud.
            logger.error(
                "compute_cascade TIMED OUT after %ss — returning null cascade (action_type=%s, target=%s)",
                HARD_TIMEOUT_SECONDS, action_type, target_entity_id,
            )
            return None
    except Exception:  # noqa: BLE001 - cascade must never break a recommendation
        logger.error(
            "compute_cascade FAILED — returning null cascade (action_type=%s, target=%s)",
            action_type, target_entity_id, exc_info=True,
        )
        return None
    finally:
        executor.shutdown(wait=False)


def _compute_cascade_inner(
    action_type: str,
    target_entity_id: str,
    proposed_change: dict,
    site_id: int,
    max_hops: int,
    projected_impact: float | None,
    driver: Driver | None,
) -> CascadeResult | None:
    if action_type not in _KNOWN_ACTION_TYPES:
        logger.info("compute_cascade: unrecognized action_type %r", action_type)
        return None

    driver = driver or get_graph_driver()

    with driver.session() as session:
        target_row = session.run(
            "MATCH (n {id: $id}) RETURN n.id AS id, labels(n)[0] AS label, "
            "coalesce(n.name, n.id) AS name, n.site_id AS site_id, "
            "n.scheduled_date AS scheduled_date, n.status AS status LIMIT 1",
            id=target_entity_id,
        ).single()

        if target_row is None:
            logger.info("compute_cascade: target entity %r not found in graph", target_entity_id)
            return None

        neo4j_site_id = target_row["site_id"]

        raw_impacted = _bfs_impacted_set(session, target_entity_id, max_hops)
        date_conflicts = _date_conflict_check(
            session, action_type, proposed_change, neo4j_site_id, target_entity_id
        )

    shift_days = _compute_shift_days(action_type, proposed_change, target_row["scheduled_date"])

    conflict_ids = {c.entity_id for c in date_conflicts}
    classified = [
        e for e in _classify_impacted(raw_impacted) if e.entity_id not in conflict_ids
    ]
    classified.extend(date_conflicts)

    blocking_count = sum(1 for e in classified if e.classification == "blocking")
    entities_affected = len(classified)
    severity = _cascade_severity(blocking_count, entities_affected)
    cascade_adjusted_impact = (
        round(projected_impact * _SEVERITY_IMPACT_MULTIPLIER[severity], 1)
        if projected_impact is not None
        else None
    )
    explanation = _build_explanation(action_type, target_entity_id, shift_days, classified, severity)

    return CascadeResult(
        shift_days=shift_days,
        entities_affected=entities_affected,
        blocking_count=blocking_count,
        cascade_severity=severity,
        cascade_adjusted_impact=cascade_adjusted_impact,
        explanation=explanation,
        impacted=classified,
    )


def _bfs_impacted_set(session, target_id: str, max_hops: int) -> list[dict]:
    """Breadth-first traversal outward from `target_id`, capped at
    `max_hops`, over `_TRAVERSAL_EDGE_TYPES`. Each node is visited once (at
    its shortest hop distance), and the exact sequence of edge types used to
    reach it is recorded for the UI's "why is this here" explanation.
    """
    visited = {target_id}
    paths: dict[str, list[str]] = {target_id: []}
    frontier = [target_id]
    results: list[dict] = []

    for hop in range(1, max_hops + 1):
        if not frontier:
            break
        rows = session.run(
            """
            UNWIND $ids AS start_id
            MATCH (a {id: start_id})-[r]-(b)
            WHERE type(r) IN $rel_types AND b.id IS NOT NULL
            RETURN start_id, b.id AS id, labels(b)[0] AS label,
                   coalesce(b.name, b.id) AS name, type(r) AS edge_type,
                   b.status AS status
            """,
            ids=frontier, rel_types=_TRAVERSAL_EDGE_TYPES,
        ).data()

        next_frontier: list[str] = []
        for record in rows:
            entity_id = record["id"]
            if entity_id in visited:
                continue
            visited.add(entity_id)
            path = paths[record["start_id"]] + [record["edge_type"]]
            paths[entity_id] = path
            results.append(
                {
                    "id": entity_id,
                    "label": record["label"],
                    "name": record["name"],
                    "status": record["status"],
                    "hops": hop,
                    "path": path,
                }
            )
            next_frontier.append(entity_id)
        frontier = next_frontier

    return results


# Classification rules, evaluated top to bottom — first match wins.
def _classify_impacted(records: list[dict]) -> list[ImpactedEntity]:
    classified = []
    for r in records:
        if r["hops"] == 1 and r["path"] == ["DEPENDS_ON"] and r["label"] == "Equipment" and r["status"] == "down":
            # Phrased as a fragment (no leading name) because _build_explanation
            # prefixes the entity name itself — including it here produced
            # "Drill NAG-1 Drill NAG-1 is down and committed to this plan".
            classification, detail = "blocking", "is down and committed to this plan"
        elif r["hops"] == 1 and r["path"] == ["AFFECTS"] and r["label"] == "OreZone":
            classification, detail = "shifted", None
        elif r["hops"] >= 2:
            classification, detail = "downstream", None
        else:
            classification, detail = "informational", None
        classified.append(
            ImpactedEntity(
                entity_id=r["id"], entity_type=r["label"], name=r["name"],
                hops=r["hops"], classification=classification, path=r["path"], detail=detail,
            )
        )
    return classified


def _date_conflict_check(
    session, action_type: str, proposed_change: dict, neo4j_site_id: str | None, target_id: str
) -> list[ImpactedEntity]:
    """Is another BlastPlan at the same site already scheduled on the
    proposed new date? Queries BlastPlan.scheduled_date directly (not the
    derived SCHEDULED_ON edge), so this works even if the dependency
    derivation routine has never been run.
    """
    if action_type != "reschedule_plan":
        return []
    new_date = proposed_change.get("new_date")
    if not new_date or not neo4j_site_id:
        return []

    rows = session.run(
        """
        MATCH (b:BlastPlan)
        WHERE b.site_id = $site_id AND b.id <> $target_id
          AND toString(b.scheduled_date) = $new_date
        RETURN b.id AS id
        """,
        site_id=neo4j_site_id, target_id=target_id, new_date=new_date,
    ).data()

    return [
        ImpactedEntity(
            entity_id=row["id"], entity_type="BlastPlan", name=row["id"],
            hops=1, classification="blocking", path=["SCHEDULED_ON"],
            detail=f"already scheduled on {new_date}",
        )
        for row in rows
    ]


def _compute_shift_days(action_type: str, proposed_change: dict, original_date) -> int | None:
    if action_type != "reschedule_plan":
        return None
    new_date = proposed_change.get("new_date")
    if not new_date or original_date is None:
        return None
    try:
        from datetime import date as date_cls

        original = original_date if isinstance(original_date, date_cls) else date_cls.fromisoformat(str(original_date))
        new = date_cls.fromisoformat(str(new_date))
        return (new - original).days
    except (TypeError, ValueError):
        return None


def _build_explanation(
    action_type: str, target_id: str, shift_days: int | None, classified: list[ImpactedEntity], severity: str
) -> str:
    if severity == "none":
        return f"No dependent entities were found for this change — {target_id} appears isolated in the current graph."

    shifted = [e for e in classified if e.classification == "shifted"]
    downstream = [e for e in classified if e.classification == "downstream"]
    blocking = [e for e in classified if e.classification == "blocking"]

    if shift_days is not None and shifted:
        names = " and ".join(e.name for e in shifted[:2])
        sentence = f"Rescheduling this plan by {abs(shift_days)} days also shifts extraction at {names}"
        if downstream:
            sentence += f" and its {len(downstream)} downstream dependenc{'y' if len(downstream) == 1 else 'ies'}"
    elif shifted:
        names = " and ".join(e.name for e in shifted[:2])
        sentence = f"This change also shifts extraction at {names}"
    else:
        sentence = f"This change ripples to {len(classified)} connected entit{'y' if len(classified) == 1 else 'ies'} in the graph"

    if blocking:
        bits = "; ".join(f"{e.name} {e.detail}" if e.detail else e.name for e in blocking[:2])
        sentence += f"; {len(blocking)} conflict{'s' if len(blocking) != 1 else ''} found — {bits}"

    return sentence + "."
