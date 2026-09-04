"""
MOIL Reserve Intelligence (SIH26009) — PART 4: Per-Site Model Training
=======================================================================
  4.1  Three classifiers per site: Random Forest, Naive Bayes, XGBoost.
  4.2  Report AUC-ROC / accuracy / precision / recall / F1 for every
       (site, model) pair.
  4.3  Persist all 9 models (3 models x 3 sites) via joblib, named by site
       and model type, e.g. models/prospectivity/rf_balaghat.pkl.
  4.4  Explicitly flag any unreliable (site, model) combination — AUC < 0.6,
       too few positives, or a training failure — instead of proceeding
       silently.

=========================== WHY NO METRICS TABLE ===========================
This harness is complete and will produce the full Part 4.2 table the moment
it is given real inputs. It deliberately REFUSES to run today.

Two independent blockers, either one sufficient:

  1. NO SATELLITE FEATURES. Part 1 cannot execute without Earth Engine
     credentials, so 9 of the 10 features are NaN.

  2. NO REAL LABELS — and this one credentials cannot fix. `is_deposit` is
     assigned by construction (Part 3), independent of any feature. Training
     on it yields a true AUC of ~0.5 by definition; the classifier can only
     learn the sampler. Any table produced now would be a precise measurement
     of noise, formatted to look like evidence.

For reference on why that matters here: the pipeline this replaces
(train_reserve_classifier.py) selected RF-vs-XGBoost on an 8-sample test set
using features that were seeded Gaussian white noise (geo_utils.build_correlated_field).
Its reported AUC was an artifact of that setup, not a geological result.

To unblock: supply GEE credentials (see gee_features.py) AND real deposit
ground truth — MOIL borehole / exploration records with confirmed and
unconfirmed locations — then run this module. Override with
--allow-synthetic ONLY for plumbing tests, never for reported results.
============================================================================
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_DIR = "models/prospectivity"
MIN_ACCEPTABLE_AUC = 0.60      # Part 4.4
MIN_POSITIVE_SAMPLES = 10      # Part 4.4 — below this, metrics are meaningless
RANDOM_STATE = 42

METRIC_NAMES = ["auc_roc", "accuracy", "precision", "recall", "f1"]


class TrainingBlockedError(RuntimeError):
    """Raised when inputs cannot support a meaningful model."""


@dataclass
class ModelResult:
    site_id: str
    model_name: str
    metrics: dict[str, float] = field(default_factory=dict)
    model_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    failed: bool = False
    failure_reason: str | None = None


def build_models(random_state: int = RANDOM_STATE) -> dict:
    """Part 4.1 — the three classifiers, instantiated per site."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.naive_bayes import GaussianNB

    models = {
        "rf": RandomForestClassifier(
            n_estimators=300, max_depth=6, random_state=random_state,
            class_weight="balanced", n_jobs=-1,
        ),
        "nb": GaussianNB(),
    }
    try:
        from xgboost import XGBClassifier
        models["xgb"] = XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            eval_metric="logloss", random_state=random_state,
        )
    except ImportError:
        logger.error("xgboost not installed — XGBoost models will be skipped (Part 4.1 incomplete)")
    return models


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict[str, float]:
    """Part 4.2 — all five metrics, not just AUC."""
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
    )
    return {
        "auc_roc": float(roc_auc_score(y_true, y_proba)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def assert_inputs_usable(train_df: pd.DataFrame, features: list[str], allow_synthetic: bool = False) -> None:
    """
    Gate that stops a meaningless training run before it produces a
    misleadingly authoritative metrics table.
    """
    if allow_synthetic:
        logger.warning(
            "--allow-synthetic: training on synthetic labels. Results are NOT valid "
            "evidence of model skill and must not be reported as such."
        )
        return

    missing = [f for f in features if f not in train_df.columns]
    if missing:
        raise TrainingBlockedError(f"Features absent from training frame: {missing}")

    all_nan = [f for f in features if train_df[f].isna().all()]
    if all_nan:
        raise TrainingBlockedError(
            f"{len(all_nan)} feature(s) are entirely NaN because Part 1 could not run "
            f"without Earth Engine credentials: {all_nan}\n"
            "See prospectivity/gee_features.py for setup steps."
        )

    if train_df.attrs.get("labels_are_synthetic", True):
        raise TrainingBlockedError(
            "Labels are synthetic (assigned by construction, independent of features). "
            "A model trained on these has a true AUC of ~0.5; any metrics table would "
            "measure noise. Supply real deposit ground truth, or pass --allow-synthetic "
            "for plumbing tests only."
        )


def train_site(
    site_id: str, train_df: pd.DataFrame, test_df: pd.DataFrame, features: list[str],
    model_dir: str = MODEL_DIR,
) -> list[ModelResult]:
    """Train all three models for one site, returning per-model results."""
    import joblib

    os.makedirs(model_dir, exist_ok=True)
    X_train, y_train = train_df[features].values, train_df["is_deposit"].values
    X_test, y_test = test_df[features].values, test_df["is_deposit"].values

    results: list[ModelResult] = []
    n_pos = int(y_train.sum())

    for name, model in build_models().items():
        result = ModelResult(site_id=site_id, model_name=name)

        # Part 4.4 — flag rather than silently proceed.
        if n_pos < MIN_POSITIVE_SAMPLES:
            result.warnings.append(
                f"only {n_pos} positive training samples (< {MIN_POSITIVE_SAMPLES}) — metrics unstable"
            )
        if len(np.unique(y_test)) < 2:
            result.failed = True
            result.failure_reason = "test split contains a single class; AUC undefined"
            results.append(result)
            continue

        try:
            model.fit(X_train, y_train)
            y_proba = model.predict_proba(X_test)[:, 1]
            y_pred = (y_proba >= 0.5).astype(int)
            result.metrics = evaluate(y_test, y_pred, y_proba)

            if result.metrics["auc_roc"] < MIN_ACCEPTABLE_AUC:
                result.warnings.append(
                    f"AUC {result.metrics['auc_roc']:.3f} < {MIN_ACCEPTABLE_AUC} — unreliable"
                )

            path = os.path.join(model_dir, f"{name}_{site_id}.pkl")  # Part 4.3
            joblib.dump({"model": model, "features": features, "site_id": site_id}, path)
            result.model_path = path

        except Exception as exc:  # noqa: BLE001
            result.failed = True
            result.failure_reason = str(exc)
            logger.error("Training failed for %s/%s: %s", site_id, name, exc)

        results.append(result)

    return results


def metrics_table(results: list[ModelResult]) -> str:
    """Part 4.2 — rows = sites, columns = models, one block per metric."""
    sites = sorted({r.site_id for r in results})
    models = sorted({r.model_name for r in results})
    lookup = {(r.site_id, r.model_name): r for r in results}

    out = ["=" * 68, " PART 4.2 — PER-SITE, PER-MODEL METRICS", "=" * 68]
    for metric in METRIC_NAMES:
        out.append(f"\n{metric.upper()}")
        out.append(f"{'site':<14}" + "".join(f"{m.upper():>12}" for m in models))
        out.append("-" * 68)
        for site in sites:
            row = f"{site:<14}"
            for m in models:
                r = lookup.get((site, m))
                row += f"{'FAILED':>12}" if (r is None or r.failed) else f"{r.metrics.get(metric, float('nan')):>12.3f}"
            out.append(row)

    flagged = [r for r in results if r.warnings or r.failed]
    if flagged:
        out.append("\n" + "=" * 68)
        out.append(" PART 4.4 — FLAGGED (SITE, MODEL) COMBINATIONS")
        out.append("=" * 68)
        for r in flagged:
            for w in (r.warnings + ([r.failure_reason] if r.failure_reason else [])):
                out.append(f"  {r.site_id}/{r.model_name}: {w}")
    out.append("=" * 68)
    return "\n".join(out)


def run(allow_synthetic: bool = False) -> list[ModelResult]:
    from prospectivity.training_data import build_all_sites, stratified_split
    from prospectivity.gee_features import FEATURE_NAMES

    sets = build_all_sites()
    all_results: list[ModelResult] = []

    for site_id, ts in sets.items():
        train_df, test_df = stratified_split(ts.points)
        train_df.attrs["labels_are_synthetic"] = True   # set False once real labels land
        assert_inputs_usable(train_df, FEATURE_NAMES, allow_synthetic=allow_synthetic)
        all_results.extend(train_site(site_id, train_df, test_df, FEATURE_NAMES))

    return all_results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    allow = "--allow-synthetic" in sys.argv

    try:
        results = run(allow_synthetic=allow)
        print(metrics_table(results))
        print(f"\nSaved {sum(1 for r in results if r.model_path)} model(s) to {MODEL_DIR}/")
    except TrainingBlockedError as exc:
        print("\n" + "=" * 68)
        print(" PART 4 — TRAINING INTENTIONALLY BLOCKED")
        print("=" * 68)
        print(exc)
        print("\nNo metrics table emitted: publishing one from these inputs would")
        print("present a measurement of noise as evidence of model skill.")
        print("=" * 68)
        raise SystemExit(2)
