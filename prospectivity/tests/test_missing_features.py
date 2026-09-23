"""Rows with a missing (cloud-masked) feature are dropped, never imputed."""

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from prospectivity.train_models import evaluate_spatial_cv


def test_cv_drops_nan_rows_and_naive_bayes_still_evaluates():
    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n), "is_deposit": np.tile([0, 0, 0, 0, 1], 20)})
    df.loc[rng.choice(n, 15, replace=False), "b"] = np.nan
    folds = list(StratifiedKFold(5, shuffle=False).split(df, df["is_deposit"]))
    res = evaluate_spatial_cv("t", df, ["a", "b"], folds, "cfg")
    for name in ("rf", "nb"):  # GaussianNB raises on NaN, so a non-NaN AUC proves rows were dropped
        assert np.isfinite(res[name]["mean_auc"]), name
