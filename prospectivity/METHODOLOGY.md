# Reserve Prospectivity Pipeline — Methodology & Known Gaps

MOIL Reserve Intelligence (SIH26009). Aligned with Zhao et al. (2025),
*Predicting Manganese Mineralization Using Multi-Source Remote Sensing and
Machine Learning: A Case Study from the Malkansu Manganese Belt*, Minerals
15(2), 113 — DOI [10.3390/min15020113](https://doi.org/10.3390/min15020113).

This document exists so the gaps stay visible. Read the blockers first.

---

## 1. Blockers — what is NOT real today

### 1.1 No Earth Engine access (blocks all satellite features)

`earthengine-api` is not installed in either interpreter; there is no
`~/.config/earthengine/`, no service-account JSON, and no GCP project
configured. Every GEE code path in this repo has only ever run its mock branch
(`gee_pipeline/output/*.tif` are 39-byte files containing the ASCII string
`TIFF_SIMULATED_MOCK_GEOTIFF_FOR_TESTING`).

Consequence: 9 of the 10 features in `gee_features.py` cannot be computed.
They are left as `NaN` and explicitly marked pending — never imputed, never
replaced with noise.

To unblock: `pip install earthengine-api`, a GCP project with the Earth Engine
API enabled, and either `earthengine authenticate` or `EE_SERVICE_ACCOUNT_JSON`.

### 1.2 No deposit ground truth (blocks all model metrics)

**Credentials do not fix this one.** `is_deposit` labels are assigned by
construction and are statistically independent of every feature. A classifier
trained on them has a true AUC of ~0.5; it can only learn the sampler.

This was measured, not assumed. Running the Part 4 harness under
`--allow-synthetic` produced AUCs of **0.443, 0.350, 0.514, 0.559** across
sites and models — chance, as predicted. Part 4.4's reliability gate flagged
every combination.

`train_models.py` therefore **refuses to emit a metrics table by default**.
Publishing one from these inputs would present a precise measurement of noise
as evidence of model skill.

To unblock: supply MOIL borehole / exploration records with confirmed and
unconfirmed deposit locations, then set `labels_are_synthetic = False`.

---

## 2. Features

| # | Feature | Status |
|---|---------|--------|
| 1.1 | Seasonal NDVI anomaly (3-yr same-ISO-week median baseline) | Implemented, blocked on GEE |
| 1.2 | NDRI `(B11-B3)/(B11+B3)` | Implemented, blocked on GEE |
| 1.3 | NDWI `(B3-B8)/(B3+B8)` — negative indicator | Implemented, blocked on GEE |
| 1.4 | Iron-oxide ratio `B4/B2` | Implemented, blocked on GEE |
| 1.5 | Clay mineral index `B11/B12` | Implemented, blocked on GEE |
| 1.6 | Manganese spectral ratio | Implemented **with caveat — see 2.1** |
| 1.7 | Slope / aspect / terrain ruggedness (COPERNICUS GLO30) | Implemented, blocked on GEE |
| 1.8 | Structural lineament density | **Computable offline** — verified correct |
| 1.9 | Stratigraphic favorability | **SKIPPED — see 2.2** |
| 1.10 | SCL cloud masking (3, 8, 9, 10) | Implemented on current *and* baseline pulls |

Note on 1.4: the iron-oxide ratio previously existed only in the tile-rendering
path and never reached the classifier, despite being the most geologically
relevant band ratio available. It is now part of the feature stack.

### 2.1 The manganese ratio is a weak proxy, not a mineral detection

Verified against the spectroscopy literature rather than assuming the cited
study transfers:

- **Rhodochrosite (MnCO₃)** has its diagnostic carbonate (CO₃²⁻) vibrational
  overtone absorption at **~2.36 µm** — longer than calcite (2.34) and
  magnesite (2.30), because Mn²⁺ does not follow the ionic-radius trend of the
  other carbonates.
- **Sentinel-2 B12** is centered at 2190 nm with a 174–184 nm bandwidth, i.e.
  it covers roughly **2.10–2.28 µm**.

**Sentinel-2 therefore cannot see the diagnostic rhodochrosite band at all.**
The paper's method does not transfer wholesale to this sensor.

**Pyrolusite (MnO₂)** is opaque and spectrally dark/featureless across
VNIR–SWIR; it is better detected as a low-albedo anomaly than by any band
ratio, and is not represented.

What is defensible with Sentinel-2 is the VNIR reflectance-*shape* signature
the study reports (relative peaks near 0.55 and 0.8 µm), mapped to the nearest
bands: **B3 (560 nm)** and **B7 (783 nm)**, expressed as a normalized
difference. Treat it accordingly.

**Highest-value sensor upgrade:** ASTER band 8 covers 2.295–2.365 µm and would
resolve the rhodochrosite feature directly, as would hyperspectral EnMAP /
EMIT / AVIRIS.

### 2.2 Stratigraphic layer — skipped, not fabricated

No open, machine-readable lithology polygon layer was found for the Balaghat /
Nagpur / Bhandara belts. GSI publishes Bhukosh map sheets, but not as an open
programmatic feature service, and no GEE-hosted equivalent covers Indian
lithology at the needed scale.

Per the requirement, this feature is **omitted entirely** rather than filled
with synthetic lithology presented as real.

Future integration: digitize GSI Bhukosh 1:50,000 sheets for the three
districts, or license a commercial geology layer, then join host-rock
favorability (Gondite / Mn-bearing metasediment vs barren) as a categorical
feature.

---

## 3. Deliberate deviations from the brief

### 3.1 A probability floor was added to the majority-agreement gate (Part 6.1)

The brief defines "favorable" as Moderate-or-above per ≥2 of 3 models. Using
Jenks bands alone to decide "Moderate" is not sufficient, and the self-test
caught why: deposits are sparse, so most of a site is a low-value bulk that
Jenks subdivides across several classes. That put the Moderate boundary at
p≈0.153 on a representative distribution — a model leaning firmly negative
would still "endorse" a cell, and the gate would filter nothing.

Endorsement therefore requires the Jenks band to be Moderate+ **and** the raw
probability to clear `MODERATE_PROBABILITY_FLOOR = 0.5`, the standard binary
decision threshold for a calibrated classifier.

Relatedly, the per-model Jenks breaks are computed on the **pooled** values
across all three models. Classifying each model against its own distribution
makes "Moderate" a relative term and breaks cross-model comparison.

### 3.2 Analysis resolution vs render resolution (Parts 5.2 / 7)

Analysis runs at the specified **100 m** cells. That yields 89,071 cells across
the three sites; as individual GeoJSON polygons that is ~40–55 MB, far too heavy
for a browser layer.

Export therefore takes an `aggregate` factor (default 3 → **300 m** render
cells), and each exported cell carries the **mean** of its constituent 100 m
cells, so the click-detail panel still shows real per-cell values. Use
`aggregate=1` for a full 100 m export to GIS software.

---

## 4. What IS real and verified

- Site boundary polygons retrieved from PostGIS (Balaghat 371.0 km², Nagpur
  294.4 km², Bhandara 225.4 km²).
- Per-site grids at a fixed 100 m cell size, dimensions derived from real
  extents: **188×201**, **169×180**, **147×157** — all distinct, confirming the
  grid is not forced to a uniform count. (The previous implementation used a
  fixed 100×100 grid over the *combined* bbox, giving ~1460×1120 m non-square
  cells — ~14× coarser, and the cause of the blurry map.)
- UTM projection, cell geometry, kriging (with IDW fallback), Jenks
  classification, the majority-agreement gate, GeoJSON validation.
- The entire Part 7 rendering path, browser-verified.

Placeholder-scored exports carry a `provenance.status = "PLACEHOLDER_SCORES"`
block, which the frontend surfaces as a visible banner in the detail panel.

---

## 5. Module map

| Part | Module | Runnable now? |
|------|--------|---------------|
| 1 | `gee_features.py` | No — raises `GEEUnavailableError` |
| 2 | `feature_selection.py` | Self-test only (`python -m prospectivity.feature_selection`) |
| 3 | `training_data.py` | **Yes** — generates per-site points |
| 4 | `train_models.py` | Blocked by design; `--allow-synthetic` for plumbing only |
| 5 | `grid.py` | **Yes** — prints per-site grid dimensions |
| 6 | `classify_export.py` | Self-test + `--demo` export |
| 7 | `oresight-frontend/src/…` | **Yes** — browser-verified |
