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

### Reserve Prospectivity Classifier — Random Forest

`RandomForestClassifier(n_estimators=200, max_depth=5)` vs.
`XGBClassifier(n_estimators=200, max_depth=3)`, compared on a stratified
80/20 split of `training_features.csv` (40 labeled points total, 8 in the
test fold), 4 features (`dist_to_nearest_structure`, `structural_density`,
`synthetic_ndvi`, `synthetic_elevation`), predicting `is_confirmed_deposit`.

**Actual measured result (this session, `train_reserve_classifier.py`):**

| Model | AUC-ROC | Precision | Recall | F1 |
|---|---|---|---|---|
| RandomForestClassifier (winner) | 0.875 | 0.800 | 1.000 | 0.889 |
| XGBClassifier | 0.875 | 0.750 | 0.750 | 0.750 |

Single 80/20 split, 8-point test fold. Because 8 test points make a single
split coarse, the label was also checked with **5-fold stratified CV across
3 seeds** (RandomForest mean AUC **0.773**, per-seed 0.79 / 0.81 / 0.72;
XGBoost mean 0.715) and a **label-shuffle permutation test** (real 5-fold CV
AUC 0.773 vs. a shuffled-label null of mean 0.49 / p95 0.71; permutation
**p = 0.005**). `dist_to_nearest_structure` dominates RandomForest feature
importance (~0.45), consistent with how the label is generated. Per-feature
point-biserial correlation with the label: `dist_to_nearest_structure`
r = −0.57 (p = 0.0001), `structural_density` r = +0.58 (p = 0.0001),
`synthetic_ndvi` and `synthetic_elevation` near zero and non-significant
(they are weak secondary terms in the label rule by design).

This is a deliberately moderate signal, not a near-perfect separator: CV
folds still swing between ~0.56 and ~1.0, and n = 40 keeps every estimate
wide. It is honest signal, though — an earlier version of the generator
assigned `is_confirmed_deposit` independently of the features, which
permutation-tested at true AUC ≈ 0.5 (chance) regardless of model or sample
size; that is the version this replaced.

### From classifier to `reserve_zones.confidence_score`

The number served by `GET /reserve-zones` and averaged into
`GET /kpi/summary` is **the kriged Random Forest prospectivity probability,
averaged over each zone** — not a count of confirmed deposits. The offline
chain (`generate_datasets.py` → `generate_features.py` →
`train_reserve_classifier.py` → `build_confidence_surface.py` →
`export_reserve_zones.py`) does this:

1. `predict_proba` from the trained Random Forest for every point on a
   50×50 grid over the combined site bounding box.
2. `PyKrige.OrdinaryKriging` smooths those grid probabilities (spherical vs.
   exponential variogram picked by 5-fold CV on a 200-point subsample —
   exponential won this run, ~7.5 km range), then the surface is resampled
   onto a clean 100×100 lon/lat cell grid. This run's kriged surface:
   min 0.006, max 0.982, mean 0.167 — most of the combined bounding box is
   far from any mapped structure and scores low, with prospectivity
   concentrating into hot spots along the structural lines, which is the
   intended behaviour of a classifier that actually keys on
   structural proximity.
3. `export_reserve_zones.py` writes the cells (each with a continuous
   `confidence_score` in [0, 1] and a lowercase `site_id`) to
   `data/reserve_zones.geojson`.
4. `scripts/import_prospectivity_scores.py` (run by `rebuild_demo_db.py`
   immediately after `import_p2_data`) sets each Postgres
   `reserve_zones.confidence_score` to the mean of the grid cells whose
   centroid falls inside that zone's polygon, rounded to 3 dp. Zones with
   no cell inside keep their prior value.

This replaced the earlier `confidence_score = confirmed / total` over the
handful of ground-truth points nearest each zone, which could only ever be
0.0, 0.5, 0.67 or 1.0 — a sample-size artifact, not a confidence gradient.
`estimated_grade_pct` / `estimated_depth_m` are unaffected: those still
come from `deposit_ground_truth.csv` via `import_p2_data`.

The caveats above carry straight through: the surface is a smoothed
projection of a moderate-signal classifier (CV AUC ≈ 0.77) trained on 40
**synthetic** points whose labels were generated from those same features,
so the per-zone score is a **relative prioritisation signal — where to
ground-truth next — not a confirmed-reserve probability.**

### Shortfall Forecaster — XGBoost Regressor

`XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05)` trained on
`production_history.csv` + `equipment_downtime_log.csv`, 8 engineered
features (rolling 7-day downtime %, days since last maintenance, a
monsoon-shaped rainfall proxy, 14-day trailing schedule pressure, and
cyclical day-of-week/month encodings), predicting daily `shortfall_pct`. Time
-based 80/20 split — trained on the first ~8 months, tested on the last
~5 weeks (never a random shuffle, so the test set is genuinely unseen
future).

**Actual measured result (this session, `finalize_shortfall_model.py`):**

| Metric | Value |
|---|---|
| Test RMSE | 0.1571 |
| Test MAE | 0.1175 |
| Test-set target mean / std | 0.1362 / 0.0903 |

**This model is unreliable for demo purposes as a quantitative forecaster**:
RMSE (0.157) is *larger* than the test set's own standard deviation (0.090)
— it performs worse than the trivial baseline of predicting the mean
shortfall for every day. `month_sin`/`month_cos`/`rainfall_proxy` together
account for ~58% of feature importance, meaning the model has effectively
learned "it's monsoon season" and little else; `schedule_pressure` and
`rolling_7day_downtime_pct` carry weak or counter-intuitive learned effects,
confirmed empirically in this session by running the live Simulator against
the demo's real equipment-failure scenario (Nagpur, Haul Truck HT-302): the
model's before/after production forecast and risk score came back
**identical** — the `equipment_down` perturbation doesn't move the
prediction at all, because 6 months of synthetic downtime data has too few
severe events for the trees to have learned a response. The `rainfall_event`
scenario, by contrast, behaves as expected (a real, sensible before/after
delta), since seasonal rainfall is a genuine, strong signal in the
synthetic generator.

**Practical consequence:** the Planner's recommendation ranking does not
rely on this model's absolute output magnitude (see Agent architecture
below) — it uses the model's *direction* as one bounded input to a ranking
score, specifically because the raw magnitude is not trustworthy on its own.

## Agent architecture

**Watcher → Simulator → Planner**, each a plain deterministic Python class
(no LangGraph — every step here is a single straight-line
detect/query/predict/rank pipeline with no branching agent decisions to
orchestrate, so a graph-orchestration framework would add dependency weight
without buying anything):

- **Watcher** polls Postgres for new equipment-down or production-shortfall
  signals, dedupes against already-open risk events, and — when it finds a
  genuinely new one — writes it to both Postgres (`risk_events`) and Neo4j
  (a linked `RiskEvent` node with a causal edge from the triggering entity),
  keeping the relational "current state" store and the graph "causal
  history" store in sync.
- **Simulator** runs read-only what-if projections: given a scenario type
  (equipment down / blast delayed / rainfall event), a site, and a duration,
  it builds the site's real current feature vector from live Postgres data,
  perturbs it for the hypothetical, and gets real before/after predictions
  from the trained Shortfall Forecaster — then separately traverses the
  Neo4j causal graph outward from the relevant node to show which
  BlastPlan/OreZone/RiskEvent chain is actually affected.
- **Planner** finds mitigation candidates (redeploy idle equipment /
  reschedule a blast plan / reallocate output to a surplus site) via direct
  Cypher/SQL lookups against the graph and Postgres, scores each by running
  it through the Simulator, and ranks them for the risk event's
  recommendation list.

## Explicit limitations

- All models are trained on **synthetic data and public-style proxies**
  (NDVI/elevation stand-ins, a hand-shaped seasonal rainfall proxy, a
  hand-generated deposit ground truth) — **none of this has been validated
  against real MOIL production, equipment, or exploration data.**
- Honestly reported above rather than glossed over: the shortfall forecaster
  underperforms a mean-only baseline on RMSE. The reserve classifier reaches
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
