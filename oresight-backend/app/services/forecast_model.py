"""Version-guarded loader for the shortfall forecaster pickle.

WHY THIS EXISTS. An XGBoost model pickled by a NEWER xgboost and loaded by an
OLDER one does not raise. It loads (with a warning that is easy to miss) and then
returns wrong predictions. Measured on this repo's model: xgboost 3.4.1 -> 2.1.4
gave predictions up to 0.37 away from the trained model's, on a target whose
whole range is roughly 0-0.6. That would surface as "the demo gives strange
numbers on someone else's machine" with no traceback. So loading fails fast
instead: the training-time xgboost version is stored inside the artifact
(`model.moil_training_meta`, set by train_shortfall_model.py) and the runtime
major.minor must match it.

A missing version is treated as a mismatch: an artifact of unknown provenance is
not loaded either.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import xgboost

META_ATTRIBUTE = "moil_training_meta"


class ModelVersionMismatchError(RuntimeError):
    """The pickled model cannot be trusted under the running xgboost."""


def _major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int(parts[1])


def check_runtime_matches(training_version: str | None, runtime_version: str | None = None) -> None:
    """Raise ModelVersionMismatchError unless runtime and training xgboost
    agree on major.minor. `runtime_version` defaults to the imported xgboost's."""
    runtime = runtime_version or xgboost.__version__
    if not training_version:
        raise ModelVersionMismatchError(
            "The shortfall model carries no training xgboost version, so it cannot be checked "
            f"against the running xgboost {runtime}. Retrain it with train_shortfall_model.py "
            "under the backend's pinned xgboost (requirements.txt)."
        )
    if _major_minor(training_version) != _major_minor(runtime):
        raise ModelVersionMismatchError(
            f"Shortfall model was trained with xgboost {training_version} but this process runs "
            f"xgboost {runtime}. Their pickles are not interchangeable: predictions would be silently "
            "wrong (up to 0.37 off, no error raised). Install the pinned version from "
            "oresight-backend/requirements.txt, or retrain under this version and regenerate "
            "models/shortfall_regression_fixture.json."
        )


def load_shortfall_model(path: Path | str):
    """joblib.load the model, then verify its training xgboost version. Never
    returns a model that failed the check."""
    model = joblib.load(path)
    meta = getattr(model, META_ATTRIBUTE, None) or {}
    check_runtime_matches(meta.get("xgboost_version"))
    return model
