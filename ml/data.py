"""Load the PlanetLab CPU traces that ship with CloudSim into a numpy array.

Each trace file holds 288 integer CPU utilization samples (percent), one every
five minutes, for one VM on one day.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

DEFAULT_CLOUDSIM_HOME = r"C:\CloudSim\cloudsim-5.0"
TRACE_SUBDIR = Path("modules/cloudsim-examples/src/main/resources/workload/planetlab")
SAMPLES_PER_DAY = 288

TRAIN_DATES = ["20110303", "20110306", "20110309", "20110322", "20110325", "20110403"]
VALIDATION_DATES = ["20110409", "20110411"]
TEST_DATES = ["20110412", "20110420"]
ALL_DATES = TRAIN_DATES + VALIDATION_DATES + TEST_DATES


def trace_root() -> Path:
    home = Path(os.environ.get("CLOUDSIM_HOME", DEFAULT_CLOUDSIM_HOME))
    root = home / TRACE_SUBDIR
    if not root.is_dir():
        raise FileNotFoundError(f"PlanetLab traces not found at {root}; set CLOUDSIM_HOME")
    return root


def load_day(date: str) -> tuple[np.ndarray, list[str]]:
    """Return (vms x 288 float32 array of percent CPU, sorted VM names)."""
    folder = trace_root() / date
    names = sorted(p.name for p in folder.iterdir() if p.is_file())
    rows = np.empty((len(names), SAMPLES_PER_DAY), dtype=np.float32)
    for i, name in enumerate(names):
        values = np.loadtxt(folder / name, dtype=np.float32)
        if values.shape != (SAMPLES_PER_DAY,):
            raise ValueError(f"{date}/{name}: expected 288 samples, got {values.shape}")
        rows[i] = values
    return rows, names


def load_all(dates: list[str] = ALL_DATES) -> dict[str, np.ndarray]:
    return {date: load_day(date)[0] for date in dates}
