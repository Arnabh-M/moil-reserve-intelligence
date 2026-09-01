"""Routes for risk events and their causal graph (live Neo4j traversal)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from neo4j import Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.graph_db import get_graph_driver
from app.models import RiskEvent
from app.schemas import CausalGraphOut, GraphEdge, GraphNode, RiskEventOut
from app.services.lookups import get_risk_event_or_404

logger = logging.getLogger("oresight.risk_events")

router = APIRouter(prefix="/risk-events", tags=["risk-events"])

# How many hops out from the RiskEvent node to pull into the causal graph.
CAUSAL_GRAPH_MAX_HOPS = 3

# Node property names to try, in order, when picking a human-readable label
# for a graph node (labels vary by node type in seed_graph.cypher).
_LABEL_PROP_PRIORITY = (
    "name",
    "description",
    "event_type",
    "risk_type",
    "feature_type",
    "id",
)


def _risk_event_to_out(risk_event: RiskEvent) -> RiskEventOut:
    return RiskEventOut(
        id=risk_event.id,
        site_id=risk_event.site_id,
        site_name=risk_event.site.name,
        risk_type=risk_event.risk_type,
        severity=risk_event.severity.value,
        score=risk_event.score,
        description=risk_event.description,
        resolved=risk_event.resolved,
        detected_at=risk_event.detected_at,
    )


@router.get("", response_model=list[RiskEventOut], summary="List risk events")
def list_risk_events(
    site_id: int | None = Query(None, description="Filter to one site"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    db: Session = Depends(get_db),
) -> list[RiskEventOut]:
    """Return risk events, newest first, optionally filtered by site and/or
    resolved status.
    """
    stmt = (
        select(RiskEvent)
        .options(joinedload(RiskEvent.site))
        .order_by(RiskEvent.detected_at.desc())
    )
    if site_id is not None:
        stmt = stmt.where(RiskEvent.site_id == site_id)
    if resolved is not None:
        stmt = stmt.where(RiskEvent.resolved == resolved)
    rows = db.scalars(stmt).all()
    return [_risk_event_to_out(r) for r in rows]


def _node_label(props: dict, node_id: str) -> str:
    for key in _LABEL_PROP_PRIORITY:
        value = props.get(key)
        if value:
            return str(value)
    return node_id


def _postgres_fallback_graph(risk_event: RiskEvent, reason: str) -> CausalGraphOut:
    """Build a one-node graph from the Postgres risk event itself.

    Used when the risk event is real in Postgres but has no matching
    RiskEvent node in Neo4j (it predates the Watcher-driven graph sync, or
    Neo4j is unreachable). Returns the risk event as a single node with an
    explicit `graph_source`/`note` so the frontend shows a banner rather
    than what looks like an empty-graph bug.
    """
    return CausalGraphOut(
        nodes=[
            GraphNode(
                id=f"risk_event_{risk_event.id}",
                label=risk_event.description
                or f"{risk_event.risk_type} at {risk_event.site.name}",
                type="RiskEvent",
            )
        ],
        edges=[],
        graph_source="postgres_fallback",
        note=reason,
    )


@router.get(
    "/{risk_event_id}/causal-graph",
    response_model=CausalGraphOut,
    summary="Get the causal graph behind a risk event",
)
def get_causal_graph(
    risk_event_id: int,
    db: Session = Depends(get_db),
    driver: Driver = Depends(get_graph_driver),
) -> CausalGraphOut:
    """Return the causal chain that led to this risk event, as a React
    Flow-ready `{nodes, edges}` payload.

    Traverses up to 3 hops (in either direction) out from the Neo4j
    `RiskEvent` node whose `external_ref` equals this Postgres id — the link
    the Watcher agent writes when it mirrors a risk into the graph.

    - Risk event not in Postgres -> 404.
    - Risk event in Postgres but no Neo4j node (predates the graph sync, or
      Neo4j is down) -> 200 with a single-node fallback graph and
      `graph_source="postgres_fallback"` plus an explanatory `note`.
    """
    risk_event = get_risk_event_or_404(db, risk_event_id)

    query = (
        "MATCH (r:RiskEvent {external_ref: $ref}) "
        "OPTIONAL MATCH path = (r)-[*1..$max_hops]-(n) "
        "RETURN r AS root, collect(path) AS paths"
    )
    # `$max_hops` can't be a parameter inside a variable-length pattern in
    # Cypher, so it's interpolated from a validated int constant, not input.
    query = query.replace("$max_hops", str(CAUSAL_GRAPH_MAX_HOPS))

    try:
        with driver.session() as session:
            record = session.run(query, ref=str(risk_event_id)).single()
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        logger.warning(
            "Neo4j traversal failed for risk event %s: %s", risk_event_id, exc
        )
        return _postgres_fallback_graph(
            risk_event,
            "The causal graph service (Neo4j) is currently unavailable; "
            "showing the risk event on its own.",
        )

    if record is None or record["root"] is None:
        return _postgres_fallback_graph(
            risk_event,
            "This risk event has no causal graph in Neo4j yet — it predates "
            "the graph sync. Showing the risk event on its own.",
        )

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(neo4j_node) -> str | None:
        props = dict(neo4j_node)
        node_id = props.get("id")
        if node_id is None:
            return None
        if node_id not in nodes:
            node_type = next(iter(neo4j_node.labels), "Node")
            nodes[node_id] = GraphNode(
                id=node_id, label=_node_label(props, node_id), type=node_type
            )
        return node_id

    add_node(record["root"])
    for path in record["paths"]:
        if path is None:
            continue
        for neo4j_node in path.nodes:
            add_node(neo4j_node)
        for rel in path.relationships:
            source = dict(rel.start_node).get("id")
            target = dict(rel.end_node).get("id")
            if source is None or target is None:
                continue
            key = (source, target, rel.type)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                GraphEdge(source=source, target=target, relationship=rel.type)
            )

    return CausalGraphOut(
        nodes=list(nodes.values()), edges=edges, graph_source="neo4j"
    )
