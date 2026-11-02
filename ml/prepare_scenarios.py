"""Write one demand and forecast CSV per test day and VM group for CloudSim.

Demand in MIPS = sum over the group of (CPU percent / 100) x 1000 MIPS.
Run after ml/train.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import data

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"
GROUP_SIZE = 100
GROUP_SEEDS = [101, 102, 103, 104, 105]
MIPS_PER_PERCENT = 10.0  # nominal traced VM of 1000 MIPS


def main() -> None:
    write_scenarios(data.TEST_DATES, RESULTS / "scenarios")
    write_scenarios(data.VALIDATION_DATES, RESULTS / "validation" / "scenarios")
    margin = json.loads((RESULTS / "selection.json").read_text())["safety_margin_p95"]
    (RESULTS / "margin.txt").write_text(f"{margin:.6f}\n")
    print("margin", round(margin, 4))


def write_scenarios(dates: list[str], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.csv"):
        old.unlink()
    for date in dates:
        day, _ = data.load_day(date)
        archive = np.load(RESULTS / "forecasts" / f"{date}.npz")
        prediction, first = archive["prediction"], int(archive["first_target"])
        for seed in GROUP_SEEDS:
            chosen = np.random.default_rng(seed).choice(day.shape[0], GROUP_SIZE, replace=False)
            demand = day[chosen].sum(axis=0) * MIPS_PER_PERCENT
            forecast = prediction[chosen].sum(axis=0) * MIPS_PER_PERCENT
            with (out / f"{date}_g{seed}.csv").open("w", newline="\n") as f:
                f.write("interval,demand_mips,forecast_mips\n")
                for t in range(data.SAMPLES_PER_DAY):
                    value = f"{forecast[t - first]:.1f}" if t >= first else ""
                    f.write(f"{t},{demand[t]:.1f},{value}\n")
    print(out, len(list(out.glob("*.csv"))), "scenarios")


if __name__ == "__main__":
    main()
