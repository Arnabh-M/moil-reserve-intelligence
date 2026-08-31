"""Watcher Agent — polls Postgres for new equipment/production risk signals
and mirrors genuinely new ones into both Postgres (risk_events) and Neo4j
(RiskEvent nodes + causal edges), idempotently.

ORCHESTRATION CHOICE: plain Python class, not LangGraph. This is a single
deterministic poll -> detect -> dedupe -> write pipeline with no branching
LLM decisions, retries-with-memory, or multi-step planning — the things
LangGraph earns its keep on. A graph wrapper here would just be boilerplate
around one straight-line method. `app/services/scheduler.py`'s `run_watcher`
stub (every 5 min) is exactly where this class's `check_for_changes` plugs
in — call it with `since=` the last run's timestamp.

INTEGRATION NOTE: see app/agents/_bridge.py's module docstring for the real
gap between Neo4j's and Postgres's independently-seeded equipment fleets.
When a down equipment can't be matched to a Neo4j node, this agent still
creates the RiskEvent (in both stores) but logs a warning and omits the
(Equipment)-[:CAUSES]->(RiskEvent) edge rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents._bridge import find_neo4j_equipment_id, logger, pg_site_to_neo4j_id, severity_from_score
from app.models import Equipment, EquipmentStatus, ProductionRecord, RiskEvent, Site

PRODUCTION_SHORTFALL_THRESHOLD = 0.15  # >15% below target
PRODUCTION_SHORTFALL_SCORE_SCALE = 0.5  # a 50% shortfall maps to score 1.0
EQUIPMENT_DOWN_BASELINE_SCORE = 0.65  # placeholder heuristic; not yet risk-calibrated


@dataclass
class DetectedChange:
    site: Site
    risk_type: str
    score: float
    description: str
    source_entity_type: str | None
    source_entity_id: int | None
    detected_at: datetime


class WatcherAgent:
    """Detects new equipment/production risk signals and syncs Postgres + Neo4j."""

    def __init__(self, db: Session, neo4j_driver: Driver) -> None:
        """Store the injected SQLAlchemy session and Neo4j driver.

        Both are dependency-injected (not constructed here) so tests can
        pass mocks/fakes without live infra.
        """
        self.db = db
        self.neo4j_driver = neo4j_driver

    def check_for_changes(self, since: datetime | None = None) -> list[dict]:
        """Detect new equipment/production risk signals since `since`.

        Defaults `since` to 6 hours ago. For every genuinely new risk
        (not already flagged unresolved at the same site), creates a
        Postgres `risk_events` row and a linked Neo4j `RiskEvent` node
        with a causal edge from the triggering entity. Returns
        `[{id, site_id, risk_type, score, description, detected_at}, ...]`
        for every risk event created THIS call — an empty list if Postgres
        is unreachable or nothing new was found.
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=6)

        try:
            changes = self._detect_equipment_down(since) + self._detect_production_shortfalls()
        except SQLAlchemyError:
            logger.error("WatcherAgent: Postgres unreachable during detection", exc_info=True)
            return []

        created: list[dict] = []
        for change in changes:
            try:
                if self._is_duplicate(change):
                    continue
                pg_row = self._write_postgres_risk_event(change)
                self._write_neo4j_risk_event(change, pg_row)
                created.append(
                    {
                        "id": pg_row.id,
                        "site_id": pg_row.site_id,
                        "risk_type": pg_row.risk_type,
                        "score": pg_row.score,
                        "description": pg_row.description,
                        "detected_at": pg_row.detected_at,
                    }
                )
            except SQLAlchemyError:
                logger.error("WatcherAgent: failed to persist risk event, rolling back", exc_info=True)
                self.db.rollback()
            except Exception:  # noqa: BLE001 - Neo4j errors shouldn't crash the poll loop
                logger.error("WatcherAgent: failed to sync Neo4j for a detected change", exc_info=True)

        return created

    # -- detection -----------------------------------------------------

    def _detect_equipment_down(self, since: datetime) -> list[DetectedChange]:
        stmt = select(Equipment).where(
            Equipment.status == EquipmentStatus.DOWN,
            Equipment.last_status_change >= since,
        )
        rows = self.db.scalars(stmt).all()
        changes = []
        for eq in rows:
            changes.append(
                DetectedChange(
                    site=eq.site,
                    risk_type="equipment_failure",
                    score=EQUIPMENT_DOWN_BASELINE_SCORE,
                    description=f"{eq.name} went down at {eq.site.name}"
                    + (f" ({eq.status_reason})" if eq.status_reason else "."),
                    source_entity_type="equipment",
                    source_entity_id=eq.id,
                    detected_at=eq.last_status_change,
                )
            )
        return changes

    def _detect_production_shortfalls(self) -> list[DetectedChange]:
        changes = []
        for site in self.db.scalars(select(Site)).all():
            latest = self.db.scalar(
                select(ProductionRecord)
                .where(ProductionRecord.site_id == site.id)
                .order_by(ProductionRecord.date.desc())
                .limit(1)
            )
            if latest is None or not latest.target_output:
                continue

            deviation = (latest.target_output - latest.actual_output) / latest.target_output
            if deviation <= PRODUCTION_SHORTFALL_THRESHOLD:
                continue

            score = min(1.0, deviation / PRODUCTION_SHORTFALL_SCORE_SCALE)
            changes.append(
                DetectedChange(
                    site=site,
                    risk_type="production_shortfall",
                    score=round(score, 3),
                    description=(
                        f"{site.name} actual output ({latest.actual_output:.0f}t) is "
                        f"{deviation:.0%} below target ({latest.target_output:.0f}t) on {latest.date}."
                    ),
                    source_entity_type="production",
                    source_entity_id=latest.id,
                    detected_at=datetime.now(timezone.utc),
                )
            )
        return changes

    # -- idempotency -----------------------------------------------------

    def _is_duplicate(self, change: DetectedChange) -> bool:
        """An unresolved risk of the same type already flags this issue.

        Equipment-triggered risks are deduped per (site, risk_type,
        equipment) — a second, different piece of equipment failing at the
        same site is a genuinely new issue. Production-shortfall risks are
        deduped per (site, risk_type) — an ongoing shortfall isn't a new
        issue each day it persists, until it's marked resolved.
        """
        stmt = select(RiskEvent).where(
            RiskEvent.site_id == change.site.id,
            RiskEvent.risk_type == change.risk_type,
            RiskEvent.resolved.is_(False),
        )
        if change.source_entity_type == "equipment":
            stmt = stmt.where(
                RiskEvent.source_entity_type == "equipment",
                RiskEvent.source_entity_id == change.source_entity_id,
            )
        return self.db.scalar(stmt) is not None

    # -- writes -----------------------------------------------------

    def _write_postgres_risk_event(self, change: DetectedChange) -> RiskEvent:
        row = RiskEvent(
            site_id=change.site.id,
            risk_type=change.risk_type,
            severity=severity_from_score(change.score),
            score=change.score,
            description=change.description,
            source_entity_type=change.source_entity_type,
            source_entity_id=change.source_entity_id,
            resolved=False,
            detected_at=change.detected_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _write_neo4j_risk_event(self, change: DetectedChange, pg_row: RiskEvent) -> None:
        neo4j_site_id = pg_site_to_neo4j_id(change.site)
        node_id = f"re_{neo4j_site_id}_{pg_row.id}"

        with self.neo4j_driver.session() as session:
            session.run(
                """
                MATCH (s:MineSite {id: $site_id})
                CREATE (r:RiskEvent {
                    id: $node_id, site_id: $site_id, risk_type: $risk_type,
                    score: $score, description: $description,
                    detected_at: $detected_at, external_ref: $external_ref
                })
                """,
                site_id=neo4j_site_id,
                node_id=node_id,
                risk_type=change.risk_type,
                score=change.score,
                description=change.description,
                detected_at=change.detected_at.isoformat(),
                external_ref=str(pg_row.id),
            )

            edge_written = False
            if change.source_entity_type == "equipment":
                equipment = self.db.get(Equipment, change.source_entity_id)
                neo4j_eq_id = find_neo4j_equipment_id(
                    self.neo4j_driver, neo4j_site_id, equipment.equipment_type
                )
                if neo4j_eq_id is not None:
                    session.run(
                        "MATCH (e:Equipment {id: $eq_id}), (r:RiskEvent {id: $node_id}) "
                        "CREATE (e)-[:CAUSES]->(r)",
                        eq_id=neo4j_eq_id,
                        node_id=node_id,
                    )
                    edge_written = True
                else:
                    logger.warning(
                        "WatcherAgent: no Neo4j Equipment of type %r at site %r "
                        "(see app/agents/_bridge.py) — RiskEvent %s created without a CAUSES edge",
                        equipment.equipment_type, neo4j_site_id, node_id,
                    )

            # A weather event overlapping "now" correlates with the risk
            # regardless of trigger type (and is the ONLY causal signal
            # available for production-shortfall risks, which have no
            # Equipment/BlastPlan source node of their own).
            result = session.run(
                """
                MATCH (w:WeatherEvent {site_id: $site_id})
                WHERE date($today) >= w.start_date AND date($today) <= w.end_date
                RETURN w.id AS id LIMIT 1
                """,
                site_id=neo4j_site_id,
                today=change.detected_at.date().isoformat(),
            ).single()
            if result is not None:
                session.run(
                    "MATCH (w:WeatherEvent {id: $w_id}), (r:RiskEvent {id: $node_id}) "
                    "CREATE (w)-[:CORRELATES_WITH]->(r)",
                    w_id=result["id"],
                    node_id=node_id,
                )
                edge_written = True

            if not edge_written:
                logger.warning("WatcherAgent: RiskEvent %s created with no causal edge (no matching cause found)", node_id)


if __name__ == "__main__":
    import logging as _logging

    from neo4j import GraphDatabase

    from app.config import get_settings
    from app.db import SessionLocal

    _logging.basicConfig(level=_logging.INFO)

    settings = get_settings()
    db_session = SessionLocal()
    driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))

    try:
        agent = WatcherAgent(db_session, driver)
        # since=None -> defaults to "last 6 hours"; app/seed_dev.py stamps
        # last_status_change for down equipment at "1 day ago", so pass an
        # explicit wide window here to actually see the seeded down units.
        results = agent.check_for_changes(since=datetime.now(timezone.utc) - timedelta(days=30))
        print(f"\nWatcherAgent.check_for_changes() created {len(results)} new risk event(s):")
        for r in results:
            print(f"  [{r['id']}] site={r['site_id']} type={r['risk_type']} score={r['score']} - {r['description']}")

        print("\nRunning again with the same window to verify idempotency (should create 0)...")
        results_2 = agent.check_for_changes(since=datetime.now(timezone.utc) - timedelta(days=30))
        print(f"  created {len(results_2)} new risk event(s) on second pass")
    finally:
        driver.close()
        db_session.close()
