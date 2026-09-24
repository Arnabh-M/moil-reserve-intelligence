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

HOW A SCENARIO BECOMES A FORECAST
  "Before" is the model run on the site's real feature row (app.services.live_features:
  satellite rain, equipment_status_log downtime, production backlog, blast_events).
  "After" is the SAME row with only the features the scenario physically touches
  changed, then the same model. Nothing else moves, so the difference is the model's
  own response to exactly those features.

SCENARIO -> FEATURE MAPPING (approved; do not widen without re-checking the model)
  equipment_down  -> equipment_down_today_pct    (+1 machine, i.e. +1/n_machines of the fleet)
  delay_blasting  -> blast_delay_days_lag        (the delay days added to the trailing 7-day window)
  rainfall_event  -> rain_3d_mm, rain_7d_mm, heavy_rain_lag1

  WHY equipment_down does NOT perturb rolling_7d_downtime_pct. The Stage 3 partial-dependence
  grading (train_shortfall_model.py, model_metrics.json) found the model's response to
  rolling_7d_downtime_pct still non-monotone (7 of 18 steps decrease; +1pp net rise), while
  equipment_down_today_pct is monotone (Spearman +0.96; slope 0.339 vs true 0.393). Perturbing
  the non-monotone feature reproduces exactly the incoherent before/after behaviour that
  tests/test_smoke.py's old xfail documented. The trade-off: rolling_7d_downtime_pct is left at its
  live value, so the scenario is "a machine is down TODAY", not "it has been down all week".

  WHY rainfall_event does NOT perturb rain_today_mm -- the answer to "why doesn't today's rain move
  the forecast?". The synthetic world the model learned from has NO same-day rain effect: the
  generator's rain loss uses rain on t-1 and t-2 (plus a wet-pit term on 3-day rain), so
  rain_today_mm has no causal term and the model's slope on it is a dataset artifact. Moving it
  would make the demo respond to an input that is not part of the mechanism being simulated. A
  rainfall event is therefore a storm that fell over the preceding days and ended yesterday: it
  raises the trailing rain windows and, if intense enough, yesterday's heavy-rain flag.

  Rainfall event arithmetic. `severity` is mm of rain over 3 days. A storm of S mm lasting d days
  falls at rate = S / min(d, 3) mm/day for d days ending yesterday, so
      rain_3d_mm      += S                   (by definition of the severity)
      rain_7d_mm      += rate * min(d, 7)    (the 7-day window holds at most 7 days of it)
      heavy_rain_lag1  = 1 if yesterday's real rain + rate >= the model's heavy-rain threshold
  A 60 mm storm in one day is a heavy-rain day; the same 60 mm spread over 3 days is not.
  If no severity is sent, the Medium level of the training distribution is used (the same
  value the UI preselects); that is a scenario default, not an observation.

  What `duration_days` does. It sets the shape of the rain event above and of a blast delay;
  for equipment_down it does not change the model input (the feature is "today's" fleet-hours
  down, and any outage of a day or more fills the day), it only scales the reserve-confidence
  heuristic and the uncertainty band.

  `severity` for equipment_down and delay_blasting is NOT a model input: it is only compared with
  the training range for the out-of-distribution flag (routers/simulate.py). Only rainfall's
  severity drives the projection.

LIMITATIONS (also in the final write-up)
  * Only the FIRST condition of a multi-condition request is projected (pre-existing).
  * ~63% of the model's edge over persistence rides on blast_delay_days_lag, whose live source
    (blast_events) is synthetic seeded data; the rain/soil/downtime/backlog features come from real
    or backfilled sources but the shortfall the model predicts is itself synthetic.
  * Soil moisture is NaN in the live row (SMAP lags ~3 days behind the satellite rain record).
    The model saw no NaN there in training; it is a low-importance feature (0.017).
  * days_since_last_maintenance, soil_moisture, rain_today_mm, dow/month have NO causal term in
    the synthetic generator: their learned effects are dataset artifacts, never findings.
  * backlog_t's true effect is too weak (~1.8pp) for the model to learn reliably.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from neo4j import Driver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents._bridge import find_neo4j_equipment_id, logger, pg_site_to_neo4j_id
from app.models import Equipment, ProductionRecord, ReserveZone, RiskEvent, Site
from app.services.forecast_model import load_shortfall_model
from app.services.live_features import FeatureConstants, LiveFeatures, build_live_features
from app.services.lookups import get_site_or_404
from app.services.shortfall_features import BLAST_LAG_WINDOW_DAYS, blast_delay_days_lag

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

SCENARIO_TYPES = ("equipment_down", "delay_blasting", "rainfall_event")
_RESERVE_CONFIDENCE_DECAY_PER_DAY = {
    "equipment_down": 0.002,
    "delay_blasting": 0.0015,
    "rainfall_event": 0.003,
}
RAIN_3D_WINDOW_DAYS = 3
RAIN_7D_WINDOW_DAYS = 7


class SimulatorAgent:
    """Runs read-only what-if scenarios against the twin state + graph."""

    def __init__(self, db: Session, neo4j_driver: Driver) -> None:
        """Store the injected SQLAlchemy session and Neo4j driver, and load
        the trained shortfall model + its exact feature column order.

        Both db/driver are dependency-injected (not constructed here) so
        this is testable with mocks. Never writes to either store — every
        method here is read-only by design.

        The model is loaded through app.services.forecast_model, which refuses an artifact
        trained under a different xgboost major.minor (or with no recorded version): a silent
        mispredict is worse than a 503.
        """
        self.db = db
        self.neo4j_driver = neo4j_driver
        self.model = load_shortfall_model(MODELS_DIR / "shortfall_forecaster.pkl")
        with open(MODELS_DIR / "feature_columns.json", encoding="utf-8") as f:
            self.feature_columns: list[str] = json.load(f)
        with open(MODELS_DIR / "model_metrics.json", encoding="utf-8") as f:
            self.metrics: dict = json.load(f)
        self.constants = FeatureConstants.from_metrics(self.metrics)

    def run_scenario(
        self,
        scenario_type: Literal["equipment_down", "delay_blasting", "rainfall_event"],
        site_id: int,
        duration_days: int,
        equipment_id: int | None = None,
        severity: float | None = None,
        as_of: date | None = None,
    ) -> dict:
        """Project a hypothetical disruption's before/after impact.

        Builds the site's CURRENT feature vector from live data (see
        app.services.live_features), perturbs it for the given scenario, runs the real
        trained model on both, and traverses up to 3 hops in Neo4j from the relevant
        node to find the affected BlastPlan/OreZone/RiskEvent chain. Read-only: never
        mutates Postgres or Neo4j.

        `as_of` replays the state as of a past date (used by the sweep and the parity
        test); leave it None for the live state, which is anchored at the latest finished
        day whose rain record is complete and reported back as `model_state_as_of`.
        """
        if scenario_type not in SCENARIO_TYPES:
            raise ValueError(f"Unknown scenario_type {scenario_type!r}; must be one of {SCENARIO_TYPES}")

        site = get_site_or_404(self.db, site_id)
        neo4j_site_id = pg_site_to_neo4j_id(site)

        live = self._current_features(site, as_of)
        after_features = self._perturb_features(live, scenario_type, duration_days, severity)

        shortfall_before = float(self.model.predict(self._as_frame(live.values))[0])
        shortfall_after = float(self.model.predict(self._as_frame(after_features))[0])

        target_avg = self._recent_target_output(site, live.as_of) or 900.0
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

        residual_std = float(self.metrics["residual_std"])
        model_rmse = float(self.metrics["rmse"])
        model_mae = float(self.metrics["mae"])

        prod_impact_delta = abs(after["production_forecast"] - before["production_forecast"])
        risk_delta = abs(after["risk_score"] - before["risk_score"])
        conf_delta = abs(before["reserve_confidence"] - after["reserve_confidence"])

        # Unified scenario-conditioned uncertainty methodology:
        # Instead of multiplying total daily production by unconditional residual_std and summing
        # across horizon days (which produced a nonsensical ±1,247t band on a 35t point estimate),
        # uncertainty is scaled to the scenario's predicted perturbation response using the model's
        # holdout relative error: RMSE / mean shortfall, both read from the artifact
        # (model_metrics.json), so it follows the model in use rather than a constant.
        rel_error = model_rmse / float(self.metrics["target_shortfall_mean"])

        prod_impact_uncertainty = round(max(5.0, prod_impact_delta * rel_error), 1)
        risk_uncertainty = round(max(0.02, min(0.08, risk_delta * rel_error + 0.015)), 3)
        reserve_confidence_uncertainty = round(max(0.005, min(0.03, conf_delta * rel_error + 0.003)), 3)
        downtime_uncertainty_days = round(max(0.2, min(2.0, duration_days * 0.12)), 1)

        uncertainty = {
            "model_rmse": model_rmse,
            "model_mae": model_mae,
            "residual_std": residual_std,
            "production_impact_uncertainty_tonnes": prod_impact_uncertainty,
            "risk_uncertainty": risk_uncertainty,
            "reserve_confidence_uncertainty": reserve_confidence_uncertainty,
            "downtime_uncertainty_days": downtime_uncertainty_days,
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
            "uncertainty": uncertainty,
            "model_state_as_of": live.as_of,
            "model_inputs_missing": live.missing,
        }

    # -- feature vector construction -----------------------------------------------------

    def _current_features(self, site: Site, as_of: date | None = None) -> LiveFeatures:
        """The model's real feature row for `site` (see app.services.live_features)."""
        return build_live_features(self.db, site, self.constants, as_of=as_of)

    def default_rain_severity_mm(self) -> float:
        """Medium level of the training distribution of 3-day rain (the UI's default), used when a
        rainfall_event request carries no severity."""
        with open(MODELS_DIR / "training_data_ranges.json", encoding="utf-8") as f:
            return float(json.load(f)["rainfall_event"]["severity_levels"]["medium"])

    def _perturb_features(
        self, live: LiveFeatures, scenario_type: str, duration_days: int, severity: float | None = None
    ) -> dict:
        """The live row with ONLY the scenario's features changed (mapping in the module docstring)."""
        after = dict(live.values)
        if scenario_type == "equipment_down":
            # one more machine down for (at least) the whole of today
            after["equipment_down_today_pct"] = min(1.0, live.values["equipment_down_today_pct"] + 1.0 / live.n_machines)
        elif scenario_type == "delay_blasting":
            # `duration_days` more blast-delay days ending yesterday, unioned with the real delay days already in
            # the window by the SAME function training uses (a delay day already counted is not counted twice)
            days = min(int(duration_days), BLAST_LAG_WINDOW_DAYS)
            scenario_delay = (live.as_of - timedelta(days=days), days)
            after["blast_delay_days_lag"] = blast_delay_days_lag([*live.blast_events, scenario_delay], live.as_of)
        elif scenario_type == "rainfall_event":
            mm = float(severity) if severity is not None else self.default_rain_severity_mm()
            rate = mm / min(duration_days, RAIN_3D_WINDOW_DAYS)  # mm/day, the storm ending yesterday
            after["rain_3d_mm"] = live.values["rain_3d_mm"] + mm
            after["rain_7d_mm"] = live.values["rain_7d_mm"] + rate * min(duration_days, RAIN_7D_WINDOW_DAYS)
            after["heavy_rain_lag1"] = (
                float(live.rain_lag1_mm + rate >= live.constants.heavy_rain_mm)
                if not np.isnan(live.rain_lag1_mm)
                else float("nan")
            )
        return after

    def _as_frame(self, features: dict) -> pd.DataFrame:
        missing = [c for c in self.feature_columns if c not in features]
        if missing:
            raise RuntimeError(f"live feature row lacks model columns {missing}: feature_columns.json and live_features disagree")
        return pd.DataFrame([[features[c] for c in self.feature_columns]], columns=self.feature_columns, dtype=float)

    def _recent_target_output(self, site: Site, as_of: date) -> float | None:
        recent_subq = (
            select(ProductionRecord.target_output)
            .where(ProductionRecord.site_id == site.id, ProductionRecord.date < as_of)
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
                    # Mirror the node-collection guard above: some node types
                    # reached by this generic multi-hop traversal (e.g.
                    # CalendarDate, keyed by `date` rather than `id` — a pure
                    # scheduling join point, never meant to be a visualization
                    # node) have no `id` property, which is required and
                    # non-nullable on GraphEdge. Filter those edges out here,
                    # at the read layer, the same way id-less nodes are
                    # already filtered out just above, rather than letting a
                    # None reach CausalGraphOut's validation.
                    source_id = r.start_node["id"]
                    target_id = r.end_node["id"]
                    if source_id is None or target_id is None:
                        continue
                    edge = {"source": source_id, "target": target_id, "relationship": r.type}
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
