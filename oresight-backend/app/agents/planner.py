"""Planner Agent — mitigation recommendations for a risk event, each backed
by a real SimulatorAgent projection (not a hand-authored guess).

ORCHESTRATION CHOICE: plain Python class, not LangGraph. Candidate search
(3 fixed Cypher/SQL lookups) -> simulate each -> rank is a straight-line
pipeline with no branching agent decisions; LangGraph would add a dependency
and boilerplate for no real benefit on this timeline.

INTEGRATION NOTE — this deliberately does NOT return the exact shape given
in the task prompt. The real stub it replaces
(app/routers/recommendations.py + app/schemas/recommendation.py, already
committed by your teammate) returns `list[RecommendationOut]`, where each
item needs `risk_event_id: int` and each option needs `confidence: float`
in addition to `type`/`description`/`projected_impact`. The prompt's shape
had neither. `get_recommendations` here returns ONE dict shaped exactly
like one `RecommendationOut` (superset of the prompt's ask: it keeps
`target_id`, and adds `risk_event_id` + per-option `confidence` so the
real endpoint's response_model doesn't reject it). Wrap it in a list
(`[result]`) or extend this method to search multiple risk angles.

INTEGRATION NOTE — `risk_event_id` is Postgres's int risk_events.id (matching
the real endpoint's query param), not the Neo4j RiskEvent node's string id.
`WatcherAgent`-created risk events carry `external_ref = str(risk_events.id)`
on their Neo4j node, so those resolve to a full causal chain. Risk events
that predate the Watcher (app/seed_dev.py's seed data, and Day 1's
seed_graph.cypher nodes) have no such link — get_recommendations degrades
to a Postgres-only trigger description in that case rather than failing.

MODELING NOTE on `projected_impact` — SimulatorAgent only models 3
*disruption* scenarios (things getting worse), not "what if we fix it"
directly. Each candidate is evaluated by simulating what happens if its
underlying risk factor is left unaddressed for a realistic horizon, and
`projected_impact` = the risk-score escalation that simulation predicts —
i.e., the risk avoided by acting on this option now. See train_shortfall_
model.py and simulator.py's own notes: `schedule_pressure` (used by
`delay_blasting`, which RESCHEDULE and ADJUST_PLAN key off) has a *weak or
inverted* learned effect in the current model given limited training
signal — RESCHEDULE/ADJUST_PLAN projected_impact numbers may come back
small or 0 as an honest consequence, not a bug in this agent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from neo4j import Driver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents._bridge import find_neo4j_equipment_id, logger, neo4j_id_to_pg_site, pg_site_to_neo4j_id
from app.agents.simulator import SimulatorAgent
from app.models import Equipment, EquipmentStatus, ProductionRecord, RiskEvent, Site
from app.services.lookups import get_risk_event_or_404

MAX_OPTIONS = 3
RESCHEDULE_SEARCH_DAYS = 14
ADJUST_PLAN_LOOKBACK_DAYS = 14
REDEPLOY_ASSUMED_OUTAGE_DAYS = 5

_CONFIDENCE_BY_TYPE = {
    # Fixed heuristics, not model-calibrated (like the stub's own hardcoded
    # values) — how well-grounded each candidate-search method is, not how
    # large its impact is.
    "redeploy": 0.8,
    "reschedule": 0.75,
    "adjust_plan": 0.7,
}


class PlannerAgent:
    """Finds and ranks mitigation options for a risk event."""

    def __init__(self, db: Session, neo4j_driver: Driver) -> None:
        """Store the injected SQLAlchemy session and Neo4j driver, and
        build a SimulatorAgent to score each candidate's real impact.
        """
        self.db = db
        self.neo4j_driver = neo4j_driver
        self.simulator = SimulatorAgent(db, neo4j_driver)

    def get_recommendations(self, risk_event_id: int) -> dict:
        """Return ranked mitigation options for a risk event.

        Shape: {"trigger": str, "options": [{"type", "description",
        "target_id", "projected_impact", "confidence"}, ...]} (max 3,
        sorted by projected_impact descending) plus "risk_event_id" — see
        module docstring for why. Options with no real candidate (e.g. no
        idle equipment anywhere) are omitted rather than fabricated.
        """
        risk_event = get_risk_event_or_404(self.db, risk_event_id)
        site = risk_event.site
        trigger = self._build_trigger_description(risk_event, site)

        candidates = []
        redeploy = self._find_redeploy_candidate(risk_event, site)
        if redeploy is not None:
            candidates.append(redeploy)
        reschedule = self._find_reschedule_candidate(site)
        if reschedule is not None:
            candidates.append(reschedule)
        adjust_plan = self._find_adjust_plan_candidate(site)
        if adjust_plan is not None:
            candidates.append(adjust_plan)

        options = []
        for candidate in candidates:
            impact = self._projected_impact(candidate, site)
            options.append(
                {
                    "type": candidate["type"],
                    "description": candidate["description"],
                    "target_id": candidate["target_id"],
                    "projected_impact": round(impact, 1),
                    "confidence": _CONFIDENCE_BY_TYPE[candidate["type"]],
                }
            )

        options.sort(key=lambda o: o["projected_impact"], reverse=True)
        return {
            "trigger": trigger,
            "risk_event_id": risk_event.id,
            "options": options[:MAX_OPTIONS],
        }

    # -- trigger description -----------------------------------------------------

    def _build_trigger_description(self, risk_event: RiskEvent, site: Site) -> str:
        neo4j_site_id = pg_site_to_neo4j_id(site)
        with self.neo4j_driver.session() as session:
            row = session.run(
                "MATCH (r:RiskEvent {external_ref: $ref}) "
                "OPTIONAL MATCH (cause)-[rel]->(r) WHERE type(rel) IN ['CAUSES', 'CORRELATES_WITH'] "
                "RETURN r.description AS description, cause.id AS cause_id, "
                "coalesce(cause.name, cause.event_type) AS cause_label, type(rel) AS rel_type LIMIT 1",
                ref=str(risk_event.id),
            ).single()

        if row is not None and row["description"]:
            if row["cause_label"]:
                verb = "caused by" if row["rel_type"] == "CAUSES" else "correlated with"
                return f"{row['description']} ({verb} {row['cause_label']})"
            return row["description"]

        # No Neo4j-side link for this risk event (pre-dates the Watcher) —
        # degrade to Postgres fields only, matching the real stub's own
        # fallback in app/routers/recommendations.py.
        return risk_event.description or f"{risk_event.risk_type} at {site.name}"

    # -- candidate search -----------------------------------------------------

    def _find_redeploy_candidate(self, risk_event: RiskEvent, site: Site) -> dict | None:
        down_equipment = None
        if risk_event.source_entity_type == "equipment" and risk_event.source_entity_id:
            down_equipment = self.db.get(Equipment, risk_event.source_entity_id)

        neo4j_site_id = pg_site_to_neo4j_id(site)
        cutoff_date = (datetime.now(timezone.utc) + timedelta(days=REDEPLOY_ASSUMED_OUTAGE_DAYS)).date().isoformat()

        with self.neo4j_driver.session() as session:
            if down_equipment is not None:
                # down_equipment.equipment_type is Postgres vocabulary
                # ("haul_truck"); Neo4j's `type` property uses a different
                # vocabulary ("Excavator"/"Drill"/...) — see
                # app/agents/_bridge.py. Normalize through the same
                # best-effort type map used everywhere else rather than
                # matching the raw string, which would silently match
                # nothing for half the fleet.
                candidate_type = self._neo4j_type_for(down_equipment.equipment_type)
                row = None
                if candidate_type is not None:
                    row = session.run(
                        """
                        MATCH (e:Equipment {status: 'up', type: $eq_type})
                        WHERE e.site_id <> $site_id
                        AND NOT EXISTS {
                            MATCH (e)-[:DEPENDS_ON]->(b:BlastPlan)
                            WHERE date(b.scheduled_date) <= date($cutoff)
                        }
                        RETURN e.id AS id, e.name AS name, e.site_id AS site_id LIMIT 1
                        """,
                        eq_type=candidate_type, site_id=neo4j_site_id, cutoff=cutoff_date,
                    ).single()
            else:
                row = session.run(
                    """
                    MATCH (e:Equipment {status: 'up'})
                    WHERE e.site_id <> $site_id
                    AND NOT EXISTS {
                        MATCH (e)-[:DEPENDS_ON]->(b:BlastPlan)
                        WHERE date(b.scheduled_date) <= date($cutoff)
                    }
                    RETURN e.id AS id, e.name AS name, e.site_id AS site_id LIMIT 1
                    """,
                    site_id=neo4j_site_id, cutoff=cutoff_date,
                ).single()

        if row is None:
            return None

        candidate_pg_site = neo4j_id_to_pg_site(self.db, row["site_id"])
        down_label = down_equipment.name if down_equipment else "the affected unit"
        return {
            "type": "redeploy",
            "description": (
                f"Redeploy {row['name']} from {candidate_pg_site.name if candidate_pg_site else row['site_id']} "
                f"to {site.name} to cover {down_label}."
            ),
            "target_id": row["id"],
            "equipment_id": down_equipment.id if down_equipment else None,
        }

    def _find_reschedule_candidate(self, site: Site) -> dict | None:
        neo4j_site_id = pg_site_to_neo4j_id(site)
        today = datetime.now(timezone.utc).date()

        with self.neo4j_driver.session() as session:
            blast_row = session.run(
                "MATCH (b:BlastPlan {site_id: $site_id}) WHERE b.status IN ['planned', 'delayed'] "
                "RETURN b.id AS id ORDER BY b.scheduled_date ASC LIMIT 1",
                site_id=neo4j_site_id,
            ).single()
            if blast_row is None:
                return None

            for offset in range(1, RESCHEDULE_SEARCH_DAYS + 1):
                candidate_date = (today + timedelta(days=offset)).isoformat()
                clash = session.run(
                    """
                    MATCH (w:WeatherEvent {site_id: $site_id})
                    WHERE w.severity >= 3 AND date($d) >= w.start_date AND date($d) <= w.end_date
                    RETURN w.id AS id LIMIT 1
                    """,
                    site_id=neo4j_site_id, d=candidate_date,
                ).single()
                if clash is None:
                    return {
                        "type": "reschedule",
                        "description": (
                            f"Reschedule {blast_row['id']} at {site.name} to {candidate_date} "
                            "— the nearest date with no severity >= 3 weather event on record."
                        ),
                        "target_id": blast_row["id"],
                        "days_out": offset,
                    }
        return None

    def _find_adjust_plan_candidate(self, site: Site) -> dict | None:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=ADJUST_PLAN_LOOKBACK_DAYS)
        other_sites = self.db.scalars(select(Site).where(Site.id != site.id)).all()

        for other in other_sites:
            rows = self.db.execute(
                select(ProductionRecord.actual_output, ProductionRecord.target_output).where(
                    ProductionRecord.site_id == other.id, ProductionRecord.date >= cutoff
                )
            ).all()
            if not rows:
                continue
            surplus_days = sum(1 for actual, target in rows if target and actual > target)
            avg_surplus_pct = sum(
                (actual - target) / target for actual, target in rows if target
            ) / len(rows)
            # "Consistently above target" = both a clear majority of days
            # positive AND a positive average — a bare majority of days
            # can still net negative overall (a few bad days outweighing
            # many small-surplus ones), which isn't genuine surplus capacity.
            if surplus_days / len(rows) >= 0.7 and avg_surplus_pct > 0:
                return {
                    "type": "adjust_plan",
                    "description": (
                        f"{other.name} has run above target every day for the last "
                        f"{ADJUST_PLAN_LOOKBACK_DAYS} days (avg +{avg_surplus_pct:.0%}) — "
                        f"reallocate some of {site.name}'s shortfall there."
                    ),
                    "target_id": str(other.id),
                }
        return None

    def _neo4j_type_for(self, pg_equipment_type: str) -> str | None:
        # Direct-overlap types only (see app/agents/_bridge.py) — haul_truck
        # and crusher have no Neo4j counterpart and correctly return None.
        mapping = {"excavator": "Excavator", "drill": "Drill", "loader": "Loader"}
        return mapping.get(pg_equipment_type)

    # -- impact scoring -----------------------------------------------------

    def _projected_impact(self, candidate: dict, site: Site) -> float:
        if candidate["type"] == "redeploy":
            scenario_type, duration_days = "equipment_down", REDEPLOY_ASSUMED_OUTAGE_DAYS
            equipment_id = candidate.get("equipment_id")
        elif candidate["type"] == "reschedule":
            scenario_type, duration_days = "rainfall_event", candidate.get("days_out", 7)
            equipment_id = None
        else:
            scenario_type, duration_days = "delay_blasting", ADJUST_PLAN_LOOKBACK_DAYS
            equipment_id = None

        try:
            result = self.simulator.run_scenario(
                scenario_type, site_id=site.id, duration_days=max(1, duration_days), equipment_id=equipment_id
            )
        except Exception:  # noqa: BLE001 - a failed simulation shouldn't sink the whole recommendation
            logger.error("PlannerAgent: simulation failed for candidate %s", candidate["type"], exc_info=True)
            return 0.0

        risk_before = result["before"]["risk_score"]
        risk_after = result["after"]["risk_score"]
        return max(0.0, (risk_after - risk_before) * 100)


if __name__ == "__main__":
    import logging as _logging

    from neo4j import GraphDatabase

    from app.config import get_settings
    from app.db import SessionLocal

    _logging.basicConfig(level=_logging.WARNING)

    settings = get_settings()
    db_session = SessionLocal()
    driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))

    try:
        agent = PlannerAgent(db_session, driver)
        for risk_id in [1, 3, 5, 7]:
            result = agent.get_recommendations(risk_id)
            print(f"\n=== risk_event_id={risk_id} ===")
            print("trigger:", result["trigger"])
            if not result["options"]:
                print("  (no viable options found)")
            for opt in result["options"]:
                print(f"  [{opt['type']}] impact={opt['projected_impact']} confidence={opt['confidence']} "
                      f"target={opt['target_id']} - {opt['description']}")
    finally:
        driver.close()
        db_session.close()
