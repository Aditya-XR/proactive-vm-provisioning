"""Check that features never see the future and that forecasts align with targets.

Run: python ml/test_no_leakage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import data
from features import FEATURE_NAMES, MAX_LAG, build_features

HORIZON = 2


def main() -> None:
    rng = np.random.default_rng(7)
    day = rng.integers(0, 100, size=(30, data.SAMPLES_PER_DAY)).astype(np.float32)
    X, y, vm, origin = build_features(day, HORIZON)

    # Changing anything after origin t must leave every feature at origin t unchanged.
    for t in (MAX_LAG - 1, 100, 200, data.SAMPLES_PER_DAY - HORIZON - 1):
        changed = day.copy()
        changed[:, t + 1 :] = rng.integers(0, 100, size=changed[:, t + 1 :].shape)
        X_changed, _, _, origin_changed = build_features(changed, HORIZON)
        mask = origin == t
        assert np.array_equal(X[mask], X_changed[origin_changed == t]), f"future data leaked into origin {t}"

    # Changing anything up to origin t must be visible, so the check above is not vacuous.
    changed = day.copy()
    changed[:, 100] += 1
    assert not np.array_equal(X[origin == 100], build_features(changed, HORIZON)[0][origin == 100])

    # The target of a row is exactly the sample HORIZON steps after its origin.
    assert np.array_equal(y, day[vm, origin + HORIZON])
    assert np.array_equal(X[:, FEATURE_NAMES.index("lag_0")], day[vm, origin])

    # A scenario's forecast for interval t comes from origin t - 2 of the exported array.
    root = Path(__file__).parent.parent / "results"
    archive = np.load(root / "forecasts" / "20110412.npz")
    prediction, first = archive["prediction"], int(archive["first_target"])
    assert first == MAX_LAG - 1 + HORIZON and prediction.shape[1] == data.SAMPLES_PER_DAY - first

    print("all leakage and alignment checks passed")


if __name__ == "__main__":
    main()
