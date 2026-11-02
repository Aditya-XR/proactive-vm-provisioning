"""Turn VM CPU traces into a supervised learning table.

For a decision made with data up to and including interval t, the target is the
CPU utilization at interval t + horizon. Nothing later than t enters a feature.
"""
from __future__ import annotations

import numpy as np

MAX_LAG = 12  # one hour of history at 5 minute sampling
FEATURE_NAMES = (
    [f"lag_{k}" for k in range(MAX_LAG)]
    + ["mean_3", "mean_6", "mean_12", "std_6", "std_12", "max_12", "min_12", "trend_6"]
    + ["fleet_mean", "fleet_mean_6", "tod_sin", "tod_cos"]
)


def build_features(day: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return X, y, vm index and origin index t for one day of traces.

    Origins run from MAX_LAG - 1 to 287 - horizon, so each row has a full hour of
    history and a target inside the same day.
    """
    vms, steps = day.shape
    origins = np.arange(MAX_LAG - 1, steps - horizon)
    fleet = day.mean(axis=0)

    # windows[v, o, k] is the sample k steps before origin o for VM v.
    windows = np.stack([day[:, origins - k] for k in range(MAX_LAG)], axis=2)
    fleet_6 = np.stack([fleet[origins - k] for k in range(6)], axis=1).mean(axis=1)
    phase = 2 * np.pi * origins / steps

    columns = [windows[:, :, k] for k in range(MAX_LAG)]
    columns += [
        windows[:, :, :3].mean(axis=2),
        windows[:, :, :6].mean(axis=2),
        windows.mean(axis=2),
        windows[:, :, :6].std(axis=2),
        windows.std(axis=2),
        windows.max(axis=2),
        windows.min(axis=2),
        windows[:, :, :3].mean(axis=2) - windows[:, :, 3:6].mean(axis=2),
    ]
    tile = lambda values: np.broadcast_to(values, (vms, origins.size))
    columns += [tile(fleet[origins]), tile(fleet_6), tile(np.sin(phase)), tile(np.cos(phase))]

    X = np.stack([c.ravel() for c in columns], axis=1).astype(np.float32)
    y = day[:, origins + horizon].ravel().astype(np.float32)
    vm_index = np.repeat(np.arange(vms), origins.size)
    origin_index = np.tile(origins, vms)
    return X, y, vm_index, origin_index


def build_many(days: dict[str, np.ndarray], dates: list[str], horizon: int) -> tuple[np.ndarray, np.ndarray]:
    parts = [build_features(days[d], horizon) for d in dates]
    return np.vstack([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
