# MOIL Reserve Intelligence — Methodology (SIH26009)

## Data sources

- **Production & equipment data (Day 1):** synthetic `production_history.csv`
  (549 daily site-level actual/target output rows) and
  `equipment_downtime_log.csv` (36 logged downtime events, reasons including
  scheduled maintenance and weather delay) across the three sites.
- **Reserve ground truth (Day 1/2):** synthetic, GSI-style
  `deposit_ground_truth.csv` (40 labeled point deposits: lat/lon, depth,
  grade, confirmed/not-confirmed) and a derived `training_features.csv`
  built from it. `is_confirmed_deposit` is not a free coin flip: each
  point's confirmation probability is a logistic function of its own
  structural/NDVI/elevation features (dominated by proximity to mapped
  structures and local structural density), with Gaussian noise, and the
  label is a Bernoulli draw from that probability — so the label carries a
  real, moderate, deliberately-noisy relationship to the features the
  classifier trains on. The confirmed/unconfirmed ratio is left to fall out
  of the scores (≈48% confirmed on the current seed), not fixed by
  construction.
- **Satellite proxies (Day 2):** synthetic NDVI and elevation surfaces
  (`synthetic_ndvi`, `synthetic_elevation`) standing in for real
  Sentinel/Landsat-derived vegetation and terrain signals, plus structural
  geology features (`dist_to_nearest_structure`, `structural_density`)
  derived from the site's fault/fold data.

None of this is real MOIL production or exploration data — see Limitations.

## Models used

### Reserve prospectivity and zone confidence — ONE source

`reserve_zones.confidence_score` (served by `GET /reserve-zones`, shown in the zone
detail panel, averaged into `/sites` and `/kpi/summary`) and the map heatmap now come
from the **same** model output:

1. `prospectivity.train_models` trains per-site Random Forest, XGBoost and Naive Bayes
   classifiers on 9 Sentinel-2 / DEM features plus 2 structural features, with 5-fold
   spatial cross-validation (results and honesty statement: `prospectivity/RESULTS.md`).
2. `prospectivity.classify_export` scores every 100 m grid cell and writes the per-site
   map layers `oresight-frontend/public/prospectivity/{site}.geojson`
   (`ensemble_confidence_score` per cell).
3. `oresight-backend/scripts/import_prospectivity_scores.py` sets each zone's
   `confidence_score` to the **mean** `ensemble_confidence_score` of the map cells whose
   centroid is inside the zone polygon (3 dp). A zone with no cells gets NULL (logged), not
   a made-up value.

**The scores dropped when this was unified (e.g. Nagpur North 0.947 → 0.211), and that is
correct.** The earlier zone numbers came from a separate kriged surface, built from a
4-feature classifier that used synthetic NDVI/elevation fields and none of the real
satellite features, so it disagreed with the heatmap by an order of magnitude. That
pipeline (`build_confidence_surface.py`, `export_reserve_zones.py`,
`train_reserve_classifier.py`, `models/reserve_classifier.pkl`, `data/reserve_zones.geojson`,
`data/confidence_surface.npz`) has been retired and removed; git history has it. The lower
numbers are not a regression.

The caveats still apply: the deposit labels are **synthetic**, cross-validated AUCs are
chance-level, and the score is an **ensemble agreement index, not a probability of ore**.
It is a relative prioritisation signal for where to ground-truth next.

Before the kriging chain, `confidence_score` was `confirmed / total` over the handful of
ground-truth points nearest each zone (only ever 0.0, 0.5, 0.67 or 1.0).
`estimated_grade_pct` / `estimated_depth_m` are unaffected: they still come from
`deposit_ground_truth.csv` via `import_p2_data`.

### Shortfall Forecaster — XGBoost Regressor

Everything about this model is trained on **synthetic production data**, so the
first thing to be clear about is what is real and what is not.

**Real inputs.** Daily rainfall per site comes from satellite records (CHIRPS /
IMERG) and soil moisture from SMAP, both in `data/satellite_daily_features.csv`
(2025-01-01 onward). `app/services/weather_history.py` loads rainfall through a
fallback chain: the satellite CSV first; the Open-Meteo archive for any date the
CSV lacks (cached to disk, finished days only); and if neither has a value, NaN
with `rain_source="missing"`. It never fills a gap with an estimate.

**Synthetic outcome.** `scripts/synthetic_operations.py` generates the equipment
downtime log (19 machines, 80-92% availability) and the daily production history
from an explicit *causal* model, so that we know the true effect of each driver
and can grade what the forecaster learned. The constants are **documented
assumptions, not measured MOIL figures**:

| Driver | Assumed effect on a day's loss |
|---|---|
| Rain | 0.004 per mm of rain on t-1 and 0.002 per mm on t-2 (each day capped at 50 mm), plus a flat 0.08 when 3-day rain exceeds 60 mm |
| Equipment down | Class weights per machine-day of downtime: Excavator 0.100, Conveyor 0.083, Loader 0.067, Drill 0.050, Compressor 0.033 |
| Backlog | 0.02 x decayed unmet output (decay 0.85 per day), a secondary compounding term |
| Blast delay | 0.06 per delay-day on each of the following 5 days (delays 1-4 days; 3-8% daily probability, higher after heavy rain) |
| Noise | 3% day-to-day jitter; total loss capped at 0.9 |

Two of these constants were changed after a first pass and both changes were
reported at the time rather than tuned silently. The first-pass downtime weights
(0.30/0.20/0.15/0.25/0.10) summed to about 1.0 against a fleet that is ~14% down,
giving 16.85 percentage points of loss from downtime alone, and the backlog loop
(coefficient 0.10, gain 0.667) amplified everything about 3x, together a 60.6%
mean loss. Downtime weights were scaled by 1/3 and the backlog coefficient set to
0.02, giving a 13.4% mean loss (rain 3.1pp, downtime 5.7pp, backlog 1.8pp, blast
delays 2.9pp). These are plausibility choices, not calibration to real data.

**Features (14).** `rain_today_mm`, `rain_3d_mm`, `rain_7d_mm`,
`heavy_rain_lag1` (rain on t-1 at or above 35 mm), `soil_moisture_m3m3`,
`rolling_7d_downtime_pct`, `equipment_down_today_pct`,
`days_since_last_maintenance`, `backlog_t`, `blast_delay_days_lag`, and cyclical
day-of-week and month encodings. Every feature except `rain_today_mm` and the
calendar encodings is computed from data strictly before the day being predicted,
and a machine-checked test re-derives each one with an independent loop and
rejects deliberately leaky variants. `rain_today_mm` is the one exception: in
training it is the observed value (a perfect same-day forecast), so reported
accuracy is an optimistic ceiling relative to live use. The rainfall proxy and
14-day schedule pressure of the earlier model no longer exist.

**Evaluation.** `XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
subsample=0.8, colsample_bytree=0.8)`, one run, no tuning. Time-ordered split:
the last 20% of dates (2026-05-22 to 2026-09-22, 372 site-days) are held out,
and the model must beat **both** a train-mean baseline and a persistence baseline
(yesterday's shortfall) pooled and at each site.

| Holdout slice | Model RMSE / MAE | Train-mean RMSE | Persistence RMSE | R² gain over persistence |
|---|---|---|---|---|
| Pooled | 0.0566 / 0.0448 | 0.1168 | 0.0844 | +0.302 |
| Balaghat | 0.0575 / 0.0450 | 0.1145 | 0.0835 | +0.287 |
| Nagpur | 0.0566 / 0.0453 | 0.1105 | 0.0797 | +0.259 |
| Bhandara | 0.0557 / 0.0441 | 0.1250 | 0.0898 | +0.377 |

The target's standard deviation on the holdout is 0.114, so the model roughly
halves the error of predicting the mean. A rolling-origin check (three expanding
windows) is a stability check, not the gate; it found one slice where the model
loses to persistence (Bhandara, 2026-03-22 to 06-21). The model was also graded
against the generator's known effects: rain and blast-delay responses are
recovered and monotone, equipment downtime today is monotone, and backlog is too
weak to learn. The full account, including what should not be claimed, is in
`docs/MODEL_LIMITATIONS.md`.

**The Planner** does not rely on this model's absolute magnitude for its ranking
(see Agent architecture): it blends a fixed prior per option type with a bounded
model-derived signal.

## Agent architecture

**Watcher → Simulator → Planner**, each a plain deterministic Python class
(no LangGraph — every step here is a single straight-line
detect/query/predict/rank pipeline with no branching agent decisions to
orchestrate, so a graph-orchestration framework would add dependency weight
without buying anything):

- **Watcher** polls Postgres for new equipment-down or production-shortfall
  signals and, every 5 minutes, the Open-Meteo 72-hour forecast for each site:
  a worst rolling 24 hours of 35 mm or more raises `weather_advisory_rain`
  (score 0.4) and 64.5 mm (IMD heavy rain) raises `weather_heavy_rain` (score
  0.6 rising to 1.0 at 115.5 mm), each auto-resolving when the forecast clears;
  if the forecast cannot be fetched it logs a warning and creates nothing. It
  dedupes against already-open risk events, and — when it finds a
  genuinely new one — writes it to both Postgres (`risk_events`) and Neo4j
  (a linked `RiskEvent` node with a causal edge from the triggering entity),
  keeping the relational "current state" store and the graph "causal
  history" store in sync.
- **Simulator** runs read-only what-if projections: given a scenario type
  (equipment down / blast delayed / rainfall event), a site, and a duration,
  it builds the site's real feature vector from live data (satellite rain,
  equipment status history, production backlog, blast events), perturbs only
  the features the scenario physically touches (equipment down changes
  `equipment_down_today_pct`, a blast delay changes `blast_delay_days_lag`,
  a rainfall event of S mm over 3 days changes `rain_3d_mm`, `rain_7d_mm` and
  `heavy_rain_lag1`), and gets real before/after predictions
  from the trained Shortfall Forecaster. The starting state is the latest
  finished day with a complete rain record (reported in the response), and any
  input no source has is passed as missing rather than filled in — then separately traverses the
  Neo4j causal graph outward from the relevant node to show which
  BlastPlan/OreZone/RiskEvent chain is actually affected.
- **Planner** finds mitigation candidates (redeploy idle equipment /
  reschedule a blast plan / reallocate output to a surplus site) via direct
  Cypher/SQL lookups against the graph and Postgres, scores each by running
  it through the Simulator, and ranks them for the risk event's
  recommendation list.

## Explicit limitations

- All models are trained on **synthetic data and public-style proxies**
  (NDVI/elevation stand-ins, a hand-generated deposit ground truth, and a
  synthetic production outcome whose causal constants are documented assumptions;
  rainfall itself is real satellite data) — **none of this has been validated
  against real MOIL production, equipment, or exploration data.**
- Honestly reported above rather than glossed over: the shortfall forecaster
  beats both baselines on the holdout, but on data whose causal structure we
  wrote ourselves, and about 63% of its edge over persistence rides on one
  feature (`blast_delay_days_lag`) whose live source is also synthetic; see
  `docs/MODEL_LIMITATIONS.md`. The reserve classifier reaches
  CV AUC ≈ 0.77 (permutation p = 0.005), but only because its training
  labels are *synthetically generated from the same features it then learns*
  — it demonstrates the pipeline works end to end, not that these
  particular features predict real manganese; and n = 40 keeps every
  estimate wide (CV folds span ~0.56–1.0).
- This system is designed to be **retrained on MOIL's own proprietary
  production, downtime, and exploration data post-hackathon** — the feature
  engineering and agent architecture are built to accept that swap without
  structural changes, but the specific learned weights today should not be
  read as production-ready forecasts.
- **Reserve confidence scores are a probabilistic prioritization signal for
  where to look next, not a confirmed-deposit certainty.** A high score
  means "worth prioritizing for ground-truthing," not "manganese is
  definitely here."

## "Isn't this just running the model again?"

No — the Simulator doesn't just re-run inference with different input
numbers and hand back a fresh number. It projects the hypothetical through
the **actual causal graph structure** already built for that site: which
specific BlastPlan a WeatherEvent really delays, which OreZone that
BlastPlan really affects, which RiskEvent that really correlates with. A
model re-run in isolation can tell you "the number would change to X"; it
can't tell you *what that number is connected to* — which blast plan, which
zone, which existing risk, which idle piece of equipment elsewhere in the
graph that happens to be the right type and free at the right time. The
Planner's redeploy recommendation isn't "the model output a redeploy
score" — it's a real Cypher traversal that found a specific, named,
currently-idle unit at a specific other site with no conflicting schedule,
and *then* used the model to gauge how much that specific option would
matter. That graph-shaped reasoning is the thing a bare model re-run
doesn't have.
