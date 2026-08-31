"""
MOIL Reserve Intelligence (SIH26009) — Part 2: Train Reserve Classifier
====================================================================
Trains RandomForestClassifier and XGBClassifier on
data/training_features.csv, compares them on a stratified 80/20
split, and saves the better-performing model to
models/reserve_classifier.pkl via joblib.

Run: python train_reserve_classifier.py
"""

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURES = ["dist_to_nearest_structure", "structural_density", "synthetic_ndvi", "synthetic_elevation"]
TARGET = "is_confirmed_deposit"
RNG_SEED = 42


def evaluate(name, model, X_test, y_test):
    proba = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)

    auc = roc_auc_score(y_test, proba)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, preds, average="binary", zero_division=0
    )

    print(f"\n--- {name} ---")
    print(f"  AUC-ROC:   {auc:.3f}")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1:        {f1:.3f}")
    return auc


def main():
    print("=" * 70)
    print("Part 2: Train Reserve Classifier")
    print("=" * 70)

    df = pd.read_csv(os.path.join(DATA_DIR, "training_features.csv"))
    X = df[FEATURES]
    y = df[TARGET].astype(int)

    print(f"\nLoaded {len(df)} rows. Class balance: {y.value_counts().to_dict()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RNG_SEED
    )
    print(f"Train: {len(X_train)} rows {y_train.value_counts().to_dict()}")
    print(f"Test:  {len(X_test)} rows {y_test.value_counts().to_dict()}")

    # --- Random Forest ---
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=RNG_SEED)
    rf.fit(X_train, y_train)
    rf_auc = evaluate("RandomForestClassifier", rf, X_test, y_test)

    print("  Feature importances:")
    for feat, imp in sorted(zip(FEATURES, rf.feature_importances_), key=lambda t: -t[1]):
        print(f"    {feat}: {imp:.3f}")

    # --- XGBoost ---
    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=RNG_SEED,
    )
    xgb.fit(X_train, y_train)
    xgb_auc = evaluate("XGBClassifier", xgb, X_test, y_test)

    print("  Feature importances:")
    for feat, imp in sorted(zip(FEATURES, xgb.feature_importances_), key=lambda t: -t[1]):
        print(f"    {feat}: {imp:.3f}")

    # --- Compare and save the better model ---
    print("\n" + "-" * 70)
    if rf_auc >= xgb_auc:
        best_name, best_model, best_auc = "RandomForestClassifier", rf, rf_auc
    else:
        best_name, best_model, best_auc = "XGBClassifier", xgb, xgb_auc

    print(f"Winner: {best_name} (test AUC-ROC {best_auc:.3f} vs "
          f"{'XGBClassifier' if best_name == 'RandomForestClassifier' else 'RandomForestClassifier'} "
          f"{xgb_auc if best_name == 'RandomForestClassifier' else rf_auc:.3f})")

    # NOTE: with only 40 labeled points (8 in the test fold), AUC here
    # is high-variance and should be read as a rough signal, not a
    # precise estimate. In practice the simpler, more heavily
    # regularized model (shallow RandomForest) tends to generalize
    # at least as well as XGBoost at this sample size, since XGBoost's
    # extra flexibility has very little data to be validated against.
    # Re-run with a different RNG_SEED / split to sanity-check this
    # isn't just a lucky test fold before trusting it for Day 3+.

    model_path = os.path.join(MODELS_DIR, "reserve_classifier.pkl")
    joblib.dump(best_model, model_path)
    print(f"\nSaved best model to {model_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
