"""Machine-checks that the shortfall forecaster's features never look ahead.

Every history feature for day t must be reproducible from input rows dated
strictly before t (rain_today_mm is the one documented exception: a "perfect
forecast"). shortfall_feature_engineering.assert_no_lookahead re-derives each
feature with an independent loop-based reference that is only handed rows
dated < t, requires exact agreement with the vectorised pipeline, and demands
that deliberately leaky canary variants are rejected. Leakage here would
silently invalidate any model-vs-baseline comparison.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    # APPEND, never insert(0): the repo root has its own `scripts/` package that must not
    # shadow the backend's `scripts/` for other tests in this process.
    sys.path.append(str(REPO_ROOT))

import shortfall_feature_engineering as fe  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def built():
    inputs = fe.load_inputs()
    n_machines = fe.machines_per_site()
    return inputs, n_machines, fe.build_feature_frame(inputs, n_machines)


def test_features_have_no_lookahead(built):
    inputs, n_machines, frame = built
    result = fe.assert_no_lookahead(frame, inputs, n_machines, verbose=False, stride=3)
    assert result["rows_checked"] > 500
    assert all(flagged > 0 for flagged in result["canaries_flagged"].values())


def test_warmup_rows_are_flagged(built):
    _, _, frame = built
    assert frame["in_warmup"].sum() == fe.WARMUP_DAYS * frame["site_id"].nunique()
