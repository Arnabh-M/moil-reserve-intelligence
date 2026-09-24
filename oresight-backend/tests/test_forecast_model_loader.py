"""Unit tests for the xgboost-version guard around the shortfall model pickle
(app/services/forecast_model.py). No database or trained artifact needed.

See test_model_artifact_regression.py for WHY the guard exists.
"""

import re
from pathlib import Path

import joblib
import pytest
import xgboost

from app.services import forecast_model
from app.services.forecast_model import (
    META_ATTRIBUTE,
    ModelVersionMismatchError,
    check_runtime_matches,
    load_shortfall_model,
)

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


class _StubModel:
    """Picklable stand-in for a trained XGBRegressor (fitting one needs sklearn,
    which the backend venv deliberately does not have)."""


def _dump_stub(tmp_path, meta):
    model = _StubModel()
    if meta is not None:
        setattr(model, META_ATTRIBUTE, meta)
    path = tmp_path / "model.pkl"
    joblib.dump(model, path)
    return path


def test_matching_major_minor_loads(tmp_path):
    path = _dump_stub(tmp_path, {"xgboost_version": xgboost.__version__})
    assert isinstance(load_shortfall_model(path), _StubModel)


def test_patch_level_difference_is_allowed():
    check_runtime_matches("2.1.0", runtime_version="2.1.9")


@pytest.mark.parametrize(
    "trained, runtime",
    [("3.4.1", "2.1.4"), ("2.1.4", "3.4.1"), ("2.0.3", "2.1.4"), ("2.1.4", "2.2.0")],
)
def test_major_or_minor_mismatch_raises_naming_both_versions(trained, runtime):
    with pytest.raises(ModelVersionMismatchError) as exc:
        check_runtime_matches(trained, runtime_version=runtime)
    assert trained in str(exc.value) and runtime in str(exc.value)


def test_load_refuses_a_mismatched_artifact(tmp_path):
    path = _dump_stub(tmp_path, {"xgboost_version": "0.9.0"})
    with pytest.raises(ModelVersionMismatchError):
        load_shortfall_model(path)


@pytest.mark.parametrize("meta", [None, {}, {"xgboost_version": None}, {"xgboost_version": ""}])
def test_artifact_without_a_training_version_is_refused(tmp_path, meta):
    with pytest.raises(ModelVersionMismatchError, match="no training xgboost version"):
        load_shortfall_model(_dump_stub(tmp_path, meta))


def test_requirements_pin_is_exact_and_matches_the_installed_xgboost():
    """Compares VERSIONS, not distribution names: the venv has `xgboost`, the
    Docker image installs `xgboost-cpu`, both provide the same module."""
    pins = re.findall(r"^\s*xgboost(?:-cpu)?\s*(.*)$", REQUIREMENTS.read_text(encoding="utf-8"), re.M)
    assert len(pins) == 1, f"expected one xgboost line in requirements.txt, found {pins}"
    match = re.match(r"==\s*([0-9][0-9.]*)", pins[0])
    assert match, f"xgboost must be pinned with '==' (a range lets a silently-incompatible pickle through): {pins[0]!r}"
    assert match.group(1) == xgboost.__version__, (
        f"requirements.txt pins xgboost {match.group(1)} but {xgboost.__version__} is installed"
    )
    assert forecast_model.xgboost.__version__ == xgboost.__version__
