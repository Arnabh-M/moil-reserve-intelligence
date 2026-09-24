"""Unit tests for the xgboost-version guard around the shortfall model pickle
(app/services/forecast_model.py). No database or trained artifact needed.

See test_model_artifact_regression.py for WHY the guard exists.
"""

import importlib.metadata
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
    which is only in requirements-train.txt): keeps these guard tests independent
    of both sklearn and any trained artifact."""


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


def _xgboost_pin(path: Path) -> tuple[str, str]:
    """(distribution, exact version) from the single xgboost line of a requirements file."""
    pins = re.findall(r"^\s*(xgboost(?:-cpu)?)\s*([^\s#]*)", path.read_text(encoding="utf-8"), re.M)
    assert len(pins) == 1, f"expected one xgboost line in {path.name}, found {pins}"
    dist, spec = pins[0]
    match = re.fullmatch(r"==\s*([0-9][0-9.]*)", spec)
    assert match, f"xgboost must be pinned with '==' (a range lets a silently-incompatible pickle through): {dist}{spec!r}"
    return dist, match.group(1)


def test_requirements_pin_is_exact_and_matches_the_installed_xgboost():
    """Checks the DISTRIBUTION as well as the version. `xgboost` and `xgboost-cpu`
    provide the same module and overwrite each other's files, so a venv that has one
    while the Docker image installs the other is exactly the silent drift the pin
    exists to prevent. Both requirements files must name the same one, and it must be
    the only one installed."""
    dist, version = _xgboost_pin(REQUIREMENTS)
    assert version == xgboost.__version__, f"requirements.txt pins xgboost {version} but {xgboost.__version__} is installed"
    assert forecast_model.xgboost.__version__ == xgboost.__version__

    assert importlib.metadata.version(dist) == version, f"{dist} is not installed at the pinned {version}"
    other = ({"xgboost", "xgboost-cpu"} - {dist}).pop()
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        importlib.metadata.version(other)  # the venv must not also carry the other distribution

    root_requirements = REQUIREMENTS.parents[1] / "requirements.txt"
    if not root_requirements.exists():  # e.g. inside the Docker image, whose build context is oresight-backend/
        return
    assert _xgboost_pin(root_requirements) == (dist, version), (
        f"repo-root requirements.txt must pin exactly the same xgboost as the backend's ({dist}=={version})"
    )
