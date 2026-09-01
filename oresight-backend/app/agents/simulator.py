"""Simulator Agent — read-only what-if projections using the trained
shortfall forecaster + a real Neo4j causal-chain traversal.

ORCHESTRATION CHOICE: plain Python class, not LangGraph. Same reasoning as
watcher.py — this is one deterministic load -> query -> perturb -> predict
-> traverse pipeline, no branching agent decisions to orchestrate.

INTEGRATION NOTE — this deliberately does NOT return the exact shape given
in the task prompt. I found the real stub this replaces at
app/routers/simulate.py + app/schemas/simulation.py (already committed by
your teammate) and matched THAT contract instead, because it's the actual
FastAPI response_model:
  - the production field is `production_forecast_tonnes`, not
    `production_forecast`
  - the response also requires `affected_graph_path: list[str]`, which the
    prompt's shape omitted
Building to the prompt's shape instead would have produced a dict that
fails Pydantic validation the moment your teammate wires this in.

MODELING NOTE on `reserve_confidence` — this number isn't produced by the
shortfall model at all (nothing here trains against ReserveZone.confidence
_score). Both before/after start from the same real Postgres average, and
`after` applies a small explicit decay heuristic scaled by duration_days
(same spirit as the stub's own _SCENARIO_RATES table). It's honestly a
placeholder pending a real reserve-confidence model, not a learned effect.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from neo4j import Driver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents._bridge import find_neo4j_equipment_id, logger, pg_site_to_neo4j_id
from app.models import Equipment, EquipmentStatus, ProductionRecord, ReserveZone, RiskEvent, Site
from app.services.lookups import get_site_or_404

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

SCENARIO_TYPES = ("equipment_down", "delay_blasting", "rainfall_event")
_RESERVE_CONFIDENCE_DECAY_PER_DAY = {
    "equipment_down": 0.002,
    "delay_blasting": 0.0015,
    "rainfall_event": 0.003,
}


class SimulatorAgent:
    """Runs read-only what-if scenarios against the twin state + graph."""

    def __init__(self, db: Session, neo4j_driver: Driver) -> None:
        """Store the injected SQLAlchemy session and Neo4j driver, and load
        the trained shortfall model + its exact feature column order.

        Both db/driver are dependency-injected (not constructed here) so
        this is testable with mocks. Never writes to either store — every
        method here is read-only by design.
        """
        self.db = db
        self.neo4j_driver = neo4j_driver
        self.model = joblib.load(MODELS_DIR / "shortfall_forecaster.pkl")
        with open(MODELS_DIR / "feature_columns.json", encoding="utf-8") as f:
            self.feature_columns: list[str] = json.load(f)

    def run_scenario(
        self,
        scenario_type: Literal["equipment_down", "delay_blasting", "rainfall_event"],
        site_id: int,
        duration_days: int,
        equipment_id: int | None = None,
    ) -> dict:
        """Project a hypothetical disruption's before/after impact.

        Builds the site's CURRENT feature vector from live Postgres data,
        perturbs it for the given scenario, runs the real trained model on
        both, and traverses up to 3 hops in Neo4j from the relevant node to
        find the affected BlastPlan/OreZone/RiskEvent chain. Read-only:
        never mutates Postgres or Neo4j.
        """
        if scenario_type not in SCENARIO_TYPES:
            raise ValueError(f"Unknown scenario_type {scenario_type!r}; must be one of {SCENARIO_TYPES}")

        site = get_site_or_404(self.db, site_id)
        neo4j_site_id = pg_site_to_neo4j_id(site)

        base_features = self._current_features(site)
        after_features = self._perturb_features(base_features, scenario_type, duration_days)

        shortfall_before = float(self.model.predict(self._as_frame(base_features))[0])
        shortfall_after = float(self.model.predict(self._as_frame(after_features))[0])

        target_avg = self._recent_target_output(site) or 900.0
        reserve_confidence_before = self._avg_reserve_confidence(site)
        risk_before = self._baseline_risk_score(site)

        decay = _RESERVE_CONFIDENCE_DECAY_PER_DAY[scenario_type] * duration_days
        reserve_confidence_after = max(0.05, reserve_confidence_before * (1 - min(decay, 0.3)))

        # The model's own predicted worsening drives the risk delta,
        # instead of an arbitrary rate table.
        risk_after = min(0.97, risk_before + max(0.0, shortfall_after - shortfall_before) * 2.0)

        before = {
            "reserve_confidence": round(reserve_confidence_before, 3),
            "production_forecast": round(target_avg * (1 - shortfall_before), 1),
            "risk_score": round(risk_before, 3),
        }
        after = {
            "reserve_confidence": round(reserve_confidence_after, 3),
            "production_forecast": round(target_avg * (1 - shortfall_after), 1),
            "risk_score": round(risk_after, 3),
        }

        affected_graph_path, updated_graph = self._traverse_graph(
            scenario_type, site, neo4j_site_id, equipment_id
        )

        return {
            "before": {
                "reserve_confidence": before["reserve_confidence"],
                "production_forecast_tonnes": before["production_forecast"],
                "risk_score": before["risk_score"],
            },
            "after": {
                "reserve_confidence": after["reserve_confidence"],
                "production_forecast_tonnes": after["production_forecast"],
                "risk_score": after["risk_score"],
            },
            "affected_graph_path": affected_graph_path,
            "updated_graph": updated_graph,
        }

    # -- feature vector construction -----------------------------------------------------

    def _current_features(self, site: Site) -> dict:
        now = datetime.now(timezone.utc)

        # Postgres has no downtime-HISTORY table (unlike Day 1's CSV-based
        # training data) — only current Equipment.status/last_status_change.
        # This proxies rolling_7day_downtime_pct from current status only:
        # hours each currently-down unit has been down within the trailing
        # 7-day window, over total equipment-hours in that window.
        equipment = self.db.scalars(select(Equipment).where(Equipment.site_id == site.id)).all()
        window_start = now - timedelta(days=7)
        down_hours = 0.0
        for eq in equipment:
            if eq.status == EquipmentStatus.DOWN and eq.last_status_change:
                down_since = max(eq.last_status_change, window_start)
                down_hours += (now - down_since).total_seconds() / 3600
        available_hours = max(len(equipment), 1) * 7 * 24
        rolling_downtime_pct = min(1.0, down_hours / available_hours)

        # Postgres has no maintenance-event log at all — honestly reported
        # as missing (NaN) rather than guessed; XGBoost handles this natively.
        days_since_maintenance = np.nan

        rainfall_proxy = self._rainfall_proxy(now.date())
        schedule_pressure = self._schedule_pressure(site)

        return {
            "rolling_7day_downtime_pct": rolling_downtime_pct,
            "days_since_last_maintenance": days_since_maintenance,
            "rainfall_proxy": rainfall_proxy,
            "schedule_pressure": schedule_pressure,
            "dow_sin": np.sin(2 * np.pi * now.weekday() / 7),
            "dow_cos": np.cos(2 * np.pi * now.weekday() / 7),
            "month_sin": np.sin(2 * np.pi * now.month / 12),
            "month_cos": np.cos(2 * np.pi * now.month / 12),
        }

    def _perturb_features(self, base: dict, scenario_type: str, duration_days: int) -> dict:
        after = dict(base)
        if scenario_type == "equipment_down":
            # Recompute downtime% as if `duration_days` (capped at the
            # 7-day window) of additional downtime is added on top of
            # whatever's already down.
            added_pct = min(1.0, duration_days / 7.0) * 0.2  # one more unit out of ~5 typical
            after["rolling_7day_downtime_pct"] = min(1.0, base["rolling_7day_downtime_pct"] + added_pct)
        elif scenario_type == "delay_blasting":
            # +0.03/day of schedule_pressure: a hand-picked perturbation
            # magnitude (like the 0.2 "one more unit" above), not model- or
            # data-derived — there's no real blast-plan-delay signal in the
            # training CSVs to calibrate this against (see
            # finalize_shortfall_model.py's fit-quality note).
            after["schedule_pressure"] = min(1.0, base["schedule_pressure"] + 0.03 * duration_days)
        elif scenario_type == "rainfall_event":
            # +0.05/day of rainfall_proxy: same status as the two constants
            # above — a hand-picked perturbation magnitude, not derived from
            # the model or training data.
            after["rainfall_proxy"] = min(1.0, base["rainfall_proxy"] + 0.05 * duration_days)
        return after

    def _as_frame(self, features: dict) -> pd.DataFrame:
        return pd.DataFrame([[features[c] for c in self.feature_columns]], columns=self.feature_columns)

    def _rainfall_proxy(self, today: date) -> float:
        days_in_month = pd.Timestamp(today).days_in_month
        fractional_month = today.month + (today.day - 1) / days_in_month
        return float(0.5 * (1 + np.cos(2 * np.pi * (fractional_month - 7.5) / 12)))

    def _schedule_pressure(self, site: Site) -> float:
        rows = self.db.scalars(
            select(ProductionRecord)
            .where(ProductionRecord.site_id == site.id)
            .order_by(ProductionRecord.date.desc())
            .limit(14)
        ).all()
        if not rows:
            return 0.0
        shortfalls = [
            max(0.0, (r.target_output - r.actual_output) / r.target_output)
            for r in rows
            if r.target_output
        ]
        return float(np.clip(np.mean(shortfalls), 0, 1)) if shortfalls else 0.0

    def _recent_target_output(self, site: Site) -> float | None:
        recent_subq = (
            select(ProductionRecord.target_output)
            .where(ProductionRecord.site_id == site.id)
            .order_by(ProductionRecord.date.desc())
            .limit(14)
            .subquery()
        )
        return self.db.scalar(select(func.avg(recent_subq.c.target_output)))

    def _avg_reserve_confidence(self, site: Site) -> float:
        return self.db.scalar(
            select(func.avg(ReserveZone.confidence_score)).where(ReserveZone.site_id == site.id)
        ) or 0.6

    def _baseline_risk_score(self, site: Site) -> float:
        return self.db.scalar(
            select(func.avg(RiskEvent.score)).where(
                RiskEvent.site_id == site.id, RiskEvent.resolved.is_(False)
            )
        ) or 0.3

    # -- graph traversal -----------------------------------------------------

    def _traverse_graph(
        self, scenario_type: str, site: Site, neo4j_site_id: str, equipment_id: int | None
    ) -> tuple[list[str], dict]:
        trigger_id = f"sim_{scenario_type}"
        scenario_label = {
            "equipment_down": "Equipment Down",
            "delay_blasting": "Blast Plan Delay",
            "rainfall_event": "Rainfall Event",
        }[scenario_type]

        nodes = [{"id": trigger_id, "label": f"Simulated: {scenario_label} at {site.name}", "type": "SimulatedEvent"}]
        edges: list[dict] = []
        path = [trigger_id]

        anchor_id = self._find_anchor_node(scenario_type, neo4j_site_id, equipment_id)
        if anchor_id is None:
            logger.warning("SimulatorAgent: no anchor node found in Neo4j for %s at %s", scenario_type, neo4j_site_id)
            return path, {"nodes": nodes, "edges": edges}

        relationship = "TRIGGERS"
        with self.neo4j_driver.session() as session:
            anchor_row = session.run(
                "MATCH (n {id: $id}) RETURN n.id AS id, labels(n)[0] AS type, "
                "coalesce(n.name, n.event_type, n.risk_type, n.id) AS label",
                id=anchor_id,
            ).single()
            if anchor_row is not None:
                nodes.append({"id": anchor_row["id"], "label": str(anchor_row["label"]), "type": anchor_row["type"]})
                edges.append({"source": trigger_id, "target": anchor_id, "relationship": relationship})
                path.append(anchor_id)

            hop_result = session.run(
                """
                MATCH path = (start {id: $id})-[*1..3]->(n)
                WHERE start.id = $id
                RETURN nodes(path) AS ns, relationships(path) AS rs
                """,
                id=anchor_id,
            )
            seen_nodes = {n["id"] for n in nodes}
            for record in hop_result:
                for n in record["ns"]:
                    props = dict(n)
                    node_id = props.get("id")
                    if node_id is None or node_id in seen_nodes:
                        continue
                    seen_nodes.add(node_id)
                    label = props.get("name") or props.get("event_type") or props.get("risk_type") or node_id
                    nodes.append({"id": node_id, "label": str(label), "type": list(n.labels)[0]})
                    if node_id not in path:
                        path.append(node_id)
                for r in record["rs"]:
                    edge = {"source": r.start_node["id"], "target": r.end_node["id"], "relationship": r.type}
                    if edge not in edges:
                        edges.append(edge)

        return path, {"nodes": nodes, "edges": edges}

    def _find_anchor_node(self, scenario_type: str, neo4j_site_id: str, equipment_id: int | None) -> str | None:
        with self.neo4j_driver.session() as session:
            if scenario_type == "equipment_down":
                if equipment_id is not None:
                    equipment = self.db.get(Equipment, equipment_id)
                    if equipment is not None:
                        matched = find_neo4j_equipment_id(self.neo4j_driver, neo4j_site_id, equipment.equipment_type)
                        if matched is not None:
                            return matched
                # no specific equipment given/matched -> any equipment at the site
                row = session.run(
                    "MATCH (e:Equipment {site_id: $site_id}) RETURN e.id AS id LIMIT 1", site_id=neo4j_site_id
                ).single()
                return row["id"] if row else None

            if scenario_type == "delay_blasting":
                row = session.run(
                    "MATCH (b:BlastPlan {site_id: $site_id}) "
                    "RETURN b.id AS id ORDER BY b.scheduled_date ASC LIMIT 1",
                    site_id=neo4j_site_id,
                ).single()
                return row["id"] if row else None

            if scenario_type == "rainfall_event":
                row = session.run(
                    "MATCH (w:WeatherEvent {site_id: $site_id}) "
                    "RETURN w.id AS id ORDER BY w.start_date DESC LIMIT 1",
                    site_id=neo4j_site_id,
                ).single()
                if row is not None:
                    return row["id"]
                # no WeatherEvent recorded at this site -> fall back to the
                # site's nearest BlastPlan as the closest real anchor
                row = session.run(
                    "MATCH (b:BlastPlan {site_id: $site_id}) RETURN b.id AS id LIMIT 1", site_id=neo4j_site_id
                ).single()
                return row["id"] if row else None

        return None


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
        agent = SimulatorAgent(db_session, driver)
        for scenario, site_id, eq_id in [
            ("equipment_down", 1, 1),
            ("delay_blasting", 1, None),
            ("rainfall_event", 2, None),
        ]:
            result = agent.run_scenario(scenario, site_id=site_id, duration_days=5, equipment_id=eq_id)
            print(f"\n=== {scenario} @ site {site_id} ===")
            print("before:", result["before"])
            print("after: ", result["after"])
            print("affected_graph_path:", result["affected_graph_path"])
            print(f"updated_graph: {len(result['updated_graph']['nodes'])} nodes, "
                  f"{len(result['updated_graph']['edges'])} edges")
    finally:
        driver.close()
        db_session.close()
