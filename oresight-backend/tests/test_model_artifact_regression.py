"""Regression test for the shortfall forecaster ARTIFACT (not the code around it).

    !!! DO NOT "HELPFULLY" UPGRADE XGBOOST !!!

An XGBoost model pickled by xgboost 3.4.1 and loaded by xgboost 2.1.4 raises no
error. It loads and returns wrong numbers: measured on this repo's model, the
maximum divergence from the trained model's own predictions was 0.37, on a target
whose whole range is roughly 0-0.6 (the currently shipped, older-format pickle
loaded fine in both directions, which is exactly why the failure is easy to miss).
So the artifact is only valid under the xgboost it was trained with.

  * oresight-backend/requirements.txt pins that version exactly (2.1.4).
  * The training version is stored inside the pickle (model.moil_training_meta)
    and in model_metrics.json, and app.services.forecast_model refuses to load a
    mismatched artifact.
  * THIS test reloads the artifact and requires it to reproduce, to 1e-6, the
    predictions the trainer recorded in shortfall_regression_fixture.json (stored
    beside the pickle). If you bump xgboost you must retrain
    (train_shortfall_model.py, run from this venv) and regenerate the fixture; a
    version bump without that fails here instead of in front of a judge.

The shipped artifact is checked as soon as its model_metrics.json records a
training xgboost version. A legacy artifact from before that existed is skipped
(and is replaced when the retrained model is installed with --ship). The
candidate artifact, if present, is checked the same way.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.forecast_model import load_shortfall_model

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
TOLERANCE = 1e-6


def _cases():
    return [pytest.param(MODELS_DIR, id="shipped"), pytest.param(MODELS_DIR / "candidate", id="candidate")]


@pytest.mark.parametrize("artifact_dir", _cases())
def test_artifact_reproduces_stored_predictions(artifact_dir):
    if not (artifact_dir / "shortfall_forecaster.pkl").exists():
        pytest.skip(f"no artifact in {artifact_dir}")
    metrics_path = artifact_dir / "model_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if "xgboost_version" not in metrics:
        pytest.skip("legacy artifact with no recorded training xgboost version; replaced at ship")

    fixture_path = artifact_dir / "shortfall_regression_fixture.json"
    assert fixture_path.exists(), (
        f"{fixture_path} is missing: regenerate it with train_shortfall_model.py alongside the model"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    model = load_shortfall_model(artifact_dir / "shortfall_forecaster.pkl")  # raises on version mismatch
    assert fixture["xgboost_version"] == metrics["xgboost_version"] == model.moil_training_meta["xgboost_version"]
    columns = json.loads((artifact_dir / "feature_columns.json").read_text(encoding="utf-8"))
    assert fixture["feature_columns"] == columns == model.moil_training_meta["feature_columns"]

    x = pd.DataFrame(
        [[np.nan if v is None else v for v in row] for row in fixture["inputs"]], columns=columns, dtype=float
    )
    predicted = model.predict(x)
    np.testing.assert_allclose(predicted, np.array(fixture["expected"]), rtol=0, atol=TOLERANCE)
    assert len(predicted) >= 20
