# MOIL Reserve Intelligence — Demo Script (SIH26009)

Two pre-baked scenarios, both backed by real Postgres rows and real Neo4j causal
graphs (confirmed via live `GET /risk-events/{id}/causal-graph` — `graph_source: "neo4j"`,
not the single-node `postgres_fallback`).

| Scenario | Risk event | Postgres id | Story |
|---|---|---|---|
| A | Weather → blast delay → shortfall | 10 | Rainfall currently delaying a scheduled blast at Balaghat |
| B | Equipment failure → redeploy | 5 | A Nagpur haul truck down; an idle twin sits at Bhandara |

---

## Scenario A — Weather-driven production shortfall (Balaghat)

**Setup:** `python -m scripts.seed_scenario_a` (see `oresight-backend/scripts/seed_scenario_a.py`)

**On screen:** Open **Event Timeline**, find the "production shortfall" entry at
Balaghat (score 0.72), click **View causal graph**.

**Narration:**
1. "Heavy rain has been hitting Balaghat for the last two days, forecast to
   continue for five days total."
2. Point at the graph: *WeatherEvent (we_bal_01) → DELAYS → BlastPlan
   (bp_bal_rain_01, `delayed`) → AFFECTS → OreZone (oz_bal_rain_01) →
   CAUSES → RiskEvent, with MineSite (Balaghat) attached* — a clean 5-node
   chain, nothing extraneous.
3. "The system correlates that directly to a production-shortfall risk —
   score 0.72, projected 12% output reduction over the delay window."
4. "This isn't a guess — it's a live traversal of the causal graph, not a
   canned chart. Ask it about any other risk event and it walks the same
   real graph."

**Fallback if asked "what if it clears early":** point to the Simulator page —
`rainfall_event` scenario type reduces the duration and shows the
before/after production forecast recompute live.

---

## Scenario B — Equipment failure with a redeploy candidate (Nagpur → Bhandara)

**Setup:** `python -m scripts.enrich_risk_event_5` (see
`oresight-backend/scripts/enrich_risk_event_5.py`)

**On screen:** Open **Event Timeline**, find the critical "equipment_failure"
entry at Nagpur (score 0.93, Haul Truck HT-302), click **View causal graph**.

**Narration:**
1. "Haul Truck HT-302 at Nagpur overheated and went fully offline — critical
   severity, score 0.93."
2. Point at the graph: *Equipment (HT-302, down) → CAUSES → RiskEvent*.
3. Switch to **Recommendations** (or the Planner agent's output for this risk
   event) and surface the redeploy option: "Haul Truck HT-303 at Bhandara is
   the same equipment type, currently idle, and has no blast-plan dependency
   in the next 7 days — the system found it by graph query, not a hardcoded
   suggestion."
4. "That's the kind of cross-site optimization a human planner would have to
   manually cross-reference two spreadsheets to find."

---

## Talking points if asked "is this real data?"

- Both risk events exist as real rows in Postgres (`/risk-events` — ids 5 and 10).
- Both have real Neo4j causal graphs, confirmed live via
  `curl http://localhost:8002/risk-events/{5,10}/causal-graph` returning
  `"graph_source": "neo4j"`.
- The Event Timeline page fetches `/risk-events` directly — nothing is
  hardcoded in the frontend for these two scenarios.
- Both causal graphs are confirmed clean: Scenario A is exactly 5 nodes / 4
  edges (WeatherEvent, BlastPlan, OreZone, RiskEvent, MineSite), Scenario B
  is exactly 2 nodes / 1 edge (Equipment, RiskEvent) — no unrelated
  equipment or other-scenario nodes leak into either one.
