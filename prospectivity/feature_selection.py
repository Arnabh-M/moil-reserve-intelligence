"""
MOIL Reserve Intelligence (SIH26009) — PART 2: Feature Selection
=================================================================
Prunes redundancy from the Part 1 feature stack:

  2.1  Random Forest feature-importance ranking over the full feature set.
  2.2  Pearson correlation matrix across all features.
  2.3  For any pair with |r| > 0.9, keep the feature with higher RF importance
       and drop the other, reporting what was dropped and why.
  2.4  Report the final selected feature list.

STATUS: the selection MACHINERY is implemented and unit-verified (see
`_self_test` at the bottom, runnable with `python -m prospectivity.feature_selection`).
It has NOT been run on real feature values, because Part 1 cannot execute
without Earth Engine credentials. Running it on the repo's existing synthetic
features would produce a plausible-looking "dropped feature" list derived from
seeded RNG noise, which is worse than no list at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CORRELATION_THRESHOLD = 0.9  # Part 2.3


@dataclass
class SelectionResult:
    selected: list[str] = field(default_factory=list)
    dropped: dict[str, str] = field(default_factory=dict)     # feature -> reason
    importances: dict[str, float] = field(default_factory=dict)
    correlation_matrix: pd.DataFrame | None = None

    def report(self) -> str:
        lines = ["=" * 68, " PART 2 — FEATURE SELECTION RESULT", "=" * 68]

        lines.append("\nRF importance ranking (2.1):")
        for name, imp in sorted(self.importances.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name:<28s} {imp:.4f}")

        if self.dropped:
            lines.append(f"\nDropped for |r| > {CORRELATION_THRESHOLD} (2.3):")
            for name, reason in self.dropped.items():
                lines.append(f"  {name:<28s} {reason}")
        else:
            lines.append(f"\nNo feature pair exceeded |r| > {CORRELATION_THRESHOLD} — nothing dropped.")

        lines.append(f"\nFinal selected feature list (2.4) — {len(self.selected)} features:")
        for name in self.selected:
            lines.append(f"  - {name}")
        lines.append("=" * 68)
        return "\n".join(lines)


def rank_feature_importance(X: pd.DataFrame, y: np.ndarray, random_state: int = 42) -> dict[str, float]:
    """Part 2.1 — Random Forest importance over the full feature set."""
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=300, max_depth=6, random_state=random_state, n_jobs=-1
    )
    model.fit(X, y)
    return dict(zip(X.columns, model.feature_importances_))


def correlation_matrix(X: pd.DataFrame) -> pd.DataFrame:
    """Part 2.2 — Pearson correlation across all features."""
    return X.corr(method="pearson")


def prune_correlated(
    X: pd.DataFrame,
    importances: dict[str, float],
    threshold: float = CORRELATION_THRESHOLD,
) -> tuple[list[str], dict[str, str]]:
    """
    Part 2.3 — For each pair with |r| > threshold, keep the higher-importance
    feature and drop the other.

    Pairs are processed most-correlated-first so the most redundant relationship
    is resolved before weaker ones, and a feature already dropped is never used
    to justify dropping another (avoids cascading removal of an entire
    correlated cluster down to nothing).
    """
    corr = correlation_matrix(X).abs()
    features = list(X.columns)

    # Collect upper-triangle pairs above threshold.
    pairs = []
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r) and r > threshold:
                pairs.append((r, a, b))
    pairs.sort(reverse=True)

    dropped: dict[str, str] = {}
    for r, a, b in pairs:
        if a in dropped or b in dropped:
            continue
        imp_a, imp_b = importances.get(a, 0.0), importances.get(b, 0.0)
        loser, winner = (b, a) if imp_a >= imp_b else (a, b)
        dropped[loser] = (
            f"|r|={r:.3f} with '{winner}' (> {threshold}); "
            f"lower RF importance ({importances.get(loser, 0.0):.4f} vs {importances.get(winner, 0.0):.4f})"
        )

    selected = [f for f in features if f not in dropped]
    return selected, dropped


def select_features(X: pd.DataFrame, y: np.ndarray, threshold: float = CORRELATION_THRESHOLD) -> SelectionResult:
    """Run Parts 2.1 - 2.4 end to end."""
    if X.empty:
        raise ValueError("Feature frame is empty — cannot run selection.")
    if len(np.unique(y)) < 2:
        raise ValueError(
            "Target has a single class; RF importance is undefined. "
            "Check that training points contain both deposit and non-deposit labels."
        )

    importances = rank_feature_importance(X, y)
    selected, dropped = prune_correlated(X, importances, threshold)

    return SelectionResult(
        selected=selected,
        dropped=dropped,
        importances=importances,
        correlation_matrix=correlation_matrix(X),
    )


# ---------------------------------------------------------------------------
# Self-test: verifies the PRUNING LOGIC, not the geology.
# ---------------------------------------------------------------------------
def _self_test() -> bool:
    """
    Verify the pruning contract on a fixture with a known-correlated pair.

    CAVEAT THIS TEST SURFACED (worth knowing before trusting 2.3 on real data):
    when two features are correlated at r ~ 1.0 they are informationally
    identical, so Random Forest splits importance between them almost evenly
    (measured 0.4676 vs 0.4586 on a first pass here). "Keep the higher-importance
    one" is then effectively a coin flip. That is harmless -- either survivor
    carries the same information -- but it means the SURVIVOR'S IDENTITY is not
    reproducible for near-duplicate pairs, only the count. So the fixture below
    uses r ~ 0.93: above the 0.9 threshold, but with enough independent noise
    that the genuinely-more-predictive feature has a stable importance edge.

    Assertions follow the spec contract rather than a hard-coded winner:
      - exactly one member of the correlated pair is dropped
      - the survivor's importance >= the dropped feature's importance
      - an uncorrelated feature is never dropped
    """
    rng = np.random.default_rng(0)
    n = 600

    strong = rng.normal(0, 1, n)
    y = (strong + rng.normal(0, 0.35, n) > 0).astype(int)

    # Correlated with `strong` (~0.93) but degraded, so it predicts y worse.
    noisy_derivative = strong + rng.normal(0, 0.4, n)

    X = pd.DataFrame({
        "strong_signal": strong,
        "noisy_derivative": noisy_derivative,
        "independent_noise": rng.normal(0, 1, n),
    })

    result = select_features(X, y)
    print(result.report())

    ok = True
    pair = {"strong_signal", "noisy_derivative"}

    r = abs(result.correlation_matrix.loc["strong_signal", "noisy_derivative"])
    if r <= CORRELATION_THRESHOLD:
        print(f"FAIL: fixture correlation {r:.4f} did not exceed threshold {CORRELATION_THRESHOLD}")
        ok = False

    dropped_from_pair = pair & set(result.dropped)
    kept_from_pair = pair & set(result.selected)
    if len(dropped_from_pair) != 1 or len(kept_from_pair) != 1:
        print(f"FAIL: expected exactly 1 of the pair dropped, got dropped={dropped_from_pair}")
        ok = False
    else:
        loser, winner = dropped_from_pair.pop(), kept_from_pair.pop()
        if result.importances[winner] < result.importances[loser]:
            print(f"FAIL: kept '{winner}' despite lower importance than dropped '{loser}'")
            ok = False
        else:
            print(f"\n  correlated pair r={r:.3f}: kept '{winner}', dropped '{loser}' (correct)")

    if "independent_noise" not in result.selected:
        print("FAIL: uncorrelated feature should never be dropped")
        ok = False

    print("\nSELF-TEST:", "PASS — pruning logic correct" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(0 if _self_test() else 1)
