"""
MOIL Reserve Intelligence (SIH26009) — Shortfall Forecaster, finalize step
=======================================================================
This script used to carry its own copy of the feature engineering (including the
cosine rainfall_proxy and a hardcoded 5-machines-per-site count), duplicated from
train_shortfall_model.py. The two copies drifted and both encoded assumptions the
data no longer supports, so there is now ONE implementation:

    shortfall_feature_engineering.py   features + the look-ahead guard
    train_shortfall_model.py           evaluation, baselines, ship gate, artifacts

This wrapper runs that pipeline (forwarding any flags, e.g. --ship) and then
prints a reasoned fit-quality judgment for methodology.md instead of silently
passing whatever comes out.

Run: python finalize_shortfall_model.py [--ship]
"""

import json
import os
import sys

import train_shortfall_model as trainer


def main() -> int:
    code = trainer.main()

    installed = "--ship" in sys.argv
    out_dir = trainer.MODELS_DIR if installed else trainer.CANDIDATE_DIR
    metrics_path = os.path.join(out_dir, "model_metrics.json")
    if not os.path.exists(metrics_path):
        return code
    with open(metrics_path, encoding="utf-8") as f:
        m = json.load(f)

    rmse, std = m["rmse"], m["target_shortfall_std"]
    print("\n" + "-" * 70)
    print("Fit-quality judgment (reasoned from the data, not a fixed threshold):")
    ratio = rmse / std if std else float("inf")
    print(
        f"  holdout RMSE {rmse:.4f} vs test-target std {std:.4f} ({ratio:.2f}x); "
        f"train-mean baseline {m['baseline_train_mean_rmse']:.4f}, persistence {m['baseline_persistence_rmse']:.4f}; "
        f"R^2 gain over persistence {m['r2_gain_over_persistence']:+.3f}."
    )
    print(f"  {m['perfect_forecast_caveat']}")
    print("-" * 70)
    return code


if __name__ == "__main__":
    sys.exit(main())
