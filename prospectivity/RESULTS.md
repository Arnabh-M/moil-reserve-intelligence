# Reserve Prospectivity Model Evaluation & Feature Comparison

**MOIL Reserve Intelligence (SIH26009)**  
**Date:** 2026-09-23 15:42 UTC  

> [!IMPORTANT]
> **HONESTY & SCIENTIFIC INTEGRITY STATEMENT:**
> The deposit ground truth labels (`is_deposit`) in `data/deposit_ground_truth.csv` and the training sampling
> frames are **SYNTHETIC BY CONSTRUCTION**. They were sampled geometrically within site boundaries to test data
> pipeline plumbing, and were NOT surveyed from real boreholes or MOIL exploration drillcore.
> 
> Consequently, physical remote sensing features (vegetation indices, band ratios, terrain) have **zero genuine**
> **geophysical correlation** with these synthetic labels. Any observed metric fluctuation represents random sample
> variance rather than predictive geophysical discovery. **Real Geological Survey of India (GSI) or MOIL drillhole
> data is strictly required for a genuine empirical evaluation.**

---

## 1. Experimental Setup

To evaluate whether multi-source satellite features provide discriminative power over pure structural geology, models
were trained in **TWO configurations** using the **exact same 5-fold spatial cross-validation** splits:

1. **Configuration A (Structural Only):**
   - `structural_density` (line count within 2 km radius, projected UTM 44N)
   - `dist_to_nearest_structure` (meters to nearest lineament)
2. **Configuration B (Structural + Satellite Features):**
   - Structural features above, plus 9 pending satellite & terrain features computed from Sentinel-2 and Copernicus DEM:
     `ndvi_anomaly`, `ndri`, `ndwi`, `iron_oxide_index`, `clay_index`, `manganese_spectral_ratio`, `slope`, `aspect`, `terrain_ruggedness`.

### Satellite feature windows (Sentinel-2 L2A, SCL cloud-masked; Copernicus GLO30 DEM)
- `ndvi_anomaly`: median NDVI of the **last 90 days** minus the median NDVI of the **same 90-day calendar window
  (same days of year) in each of the previous 3 years**, so matching windows are compared.
- `ndri`, `ndwi`, `iron_oxide_index`, `clay_index`, `manganese_spectral_ratio`: median composite of the most recent
  completed **dry season (1 Feb - 31 May)**, when vegetation does not dominate the signal.
- `slope`, `aspect`, `terrain_ruggedness`: GLO30 DEM on its native 30 m grid.
- **Superseded:** an earlier single-ISO-week definition (7-day composite vs same-ISO-week baseline) left ~76% of
  pixels without an anomaly in monsoon and is no longer used. Results from it are not comparable and are not shown.
- A cell or training point with any missing feature (no clear Earth Engine pixel) is **dropped, never imputed**:
  it is excluded from that fold's training/validation rows and shown as no-data on the map.

Training points with all satellite features present (others are dropped, not imputed):

- Balaghat: 72 of 91
- Nagpur: 83 of 83
- Bhandara: 85 of 90

### Spatial Cross-Validation Methodology
- Data points were partitioned along each site's primary spatial geographic axis to ensure test folds occupy distinct spatial zones (preventing spatial autocorrelation leakage).
- Stratification was enforced across all 5 folds to preserve class balance (~1:4 deposit to non-deposit).

---

## 2. Spatial Cross-Validation Performance (Mean AUC ± Std Dev)

| Site | Classifier | Config A: Structural Only | Config B: Structural + Satellite | Delta (B - A) | Supported Config |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Balaghat** | Random Forest | 0.525 ± 0.142 | 0.418 ± 0.209 | -0.107 | Config A (Structural Only) |
| **Balaghat** | XGBoost | 0.549 ± 0.137 | 0.422 ± 0.167 | -0.127 | Config A (Structural Only) |
| **Balaghat** | Naive Bayes | 0.544 ± 0.187 | 0.295 ± 0.162 | -0.248 | Config A (Structural Only) |
| **Bhandara** | Random Forest | 0.377 ± 0.162 | 0.382 ± 0.206 | +0.005 | Config B (+Satellite) |
| **Bhandara** | XGBoost | 0.552 ± 0.127 | 0.388 ± 0.190 | -0.164 | Config A (Structural Only) |
| **Bhandara** | Naive Bayes | 0.406 ± 0.110 | 0.468 ± 0.041 | +0.061 | Config B (+Satellite) |
| **Nagpur** | Random Forest | 0.683 ± 0.091 | 0.667 ± 0.117 | -0.015 | Config A (Structural Only) |
| **Nagpur** | XGBoost | 0.686 ± 0.172 | 0.753 ± 0.092 | +0.068 | Config B (+Satellite) |
| **Nagpur** | Naive Bayes | 0.647 ± 0.089 | 0.670 ± 0.141 | +0.023 | Config B (+Satellite) |

---

## 3. Permutation Feature Importance

Permutation feature importance was evaluated on out-of-fold validation sets across all folds (mean score decrease):

### Balaghat

**Configuration B Feature Importances (Random Forest):**

| Feature | Type | Permutation Importance | Notes |
| :--- | :---: | :---: | :--- |
| `slope` | Satellite/DEM | +0.0365 | Remote sensing proxy |
| `dist_to_nearest_structure` | Structural | +0.0273 | Geological lineament |
| `terrain_ruggedness` | Satellite/DEM | +0.0197 | Remote sensing proxy |
| `clay_index` | Satellite/DEM | +0.0154 | Remote sensing proxy |
| `manganese_spectral_ratio` | Satellite/DEM | +0.0063 | Remote sensing proxy |
| `structural_density` | Structural | +0.0037 | Geological lineament |
| `ndri` | Satellite/DEM | -0.0035 | Remote sensing proxy |
| `ndwi` | Satellite/DEM | -0.0135 | Remote sensing proxy |
| `aspect` | Satellite/DEM | -0.0217 | Remote sensing proxy |
| `ndvi_anomaly` | Satellite/DEM | -0.0279 | Remote sensing proxy |
| `iron_oxide_index` | Satellite/DEM | -0.0386 | Remote sensing proxy |

### Bhandara

**Configuration B Feature Importances (Random Forest):**

| Feature | Type | Permutation Importance | Notes |
| :--- | :---: | :---: | :--- |
| `ndri` | Satellite/DEM | +0.0662 | Remote sensing proxy |
| `slope` | Satellite/DEM | +0.0104 | Remote sensing proxy |
| `iron_oxide_index` | Satellite/DEM | -0.0021 | Remote sensing proxy |
| `terrain_ruggedness` | Satellite/DEM | -0.0031 | Remote sensing proxy |
| `structural_density` | Structural | -0.0104 | Geological lineament |
| `dist_to_nearest_structure` | Structural | -0.0114 | Geological lineament |
| `aspect` | Satellite/DEM | -0.0204 | Remote sensing proxy |
| `ndvi_anomaly` | Satellite/DEM | -0.0271 | Remote sensing proxy |
| `manganese_spectral_ratio` | Satellite/DEM | -0.0302 | Remote sensing proxy |
| `clay_index` | Satellite/DEM | -0.0345 | Remote sensing proxy |
| `ndwi` | Satellite/DEM | -0.0488 | Remote sensing proxy |

### Nagpur

**Configuration B Feature Importances (Random Forest):**

| Feature | Type | Permutation Importance | Notes |
| :--- | :---: | :---: | :--- |
| `dist_to_nearest_structure` | Structural | +0.0616 | Geological lineament |
| `aspect` | Satellite/DEM | +0.0407 | Remote sensing proxy |
| `structural_density` | Structural | +0.0112 | Geological lineament |
| `clay_index` | Satellite/DEM | +0.0060 | Remote sensing proxy |
| `ndri` | Satellite/DEM | -0.0101 | Remote sensing proxy |
| `manganese_spectral_ratio` | Satellite/DEM | -0.0115 | Remote sensing proxy |
| `slope` | Satellite/DEM | -0.0123 | Remote sensing proxy |
| `iron_oxide_index` | Satellite/DEM | -0.0302 | Remote sensing proxy |
| `ndwi` | Satellite/DEM | -0.0389 | Remote sensing proxy |
| `terrain_ruggedness` | Satellite/DEM | -0.0508 | Remote sensing proxy |
| `ndvi_anomaly` | Satellite/DEM | -0.0510 | Remote sensing proxy |

---

## 4. Key Takeaways & Recommendations for SIH 2026

1. **Chance-Level Skill on Synthetic Labels:**
   Across both configurations the mean AUC-ROC ranges 0.30 - 0.75 (chance is 0.50; several cells are below it).
   With 83-91 points per site and ~1:4 class balance, fold-to-fold std is often as large as any difference between
   configurations, and the labels carry no geophysical signal, so none of these differences is evidence that a
   configuration or feature is better. Permutation importances are noise for the same reason.
   The map score is an **ensemble agreement index** across three models, **not a probability of ore**.

2. **Production Export Selection:**
   Downstream map assets and classified confidence GeoJSON layers use the configuration supported by the cross-validation
   evidence, carrying full layer provenance and factor attribution for all 10 environmental and structural parameters.

3. **Prerequisite for Production Deployment:**
   To deploy this system for actual MOIL manganese exploratory drilling:
   - Ingest surveyed borehole intercepts and drillcore assays (from GSI / MOIL Central India archives).
   - Retrain using the exact same pipeline harness with `labels_are_synthetic = False`.

---

## 5. Where the reserve-zone confidence comes from

Reserve-zone confidence (`reserve_zones.confidence_score`: `/reserve-zones`, zone panel, `/sites`, `/kpi`) and the map
heatmap now share ONE source: the per-cell `ensemble_confidence_score` from the models evaluated above. A zone's
score is the mean of the heatmap cells inside it. The earlier kriging-based score (synthetic fields, no real
satellite features) is retired; zone scores dropped when it was removed (e.g. Nagpur North 0.947 -> 0.211), which is
correct, not a regression. As everywhere in this report, the labels are synthetic and the score is an ensemble
agreement index, not a probability of ore.
