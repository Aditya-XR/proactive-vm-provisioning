"""Summarise the simulation runs.

Each policy's utilization target is chosen on validation days as the cheapest one
that keeps SLA violations at or below 1 percent. The choice is then applied to
the test days, which took no part in it. Writes results/policy_comparison.csv,
results/paired_comparison.csv and results/frontier.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).parent.parent / "results"
SLA_LIMIT_PERCENT = 1.0
ORDER = ["STATIC_PEAK", "REACTIVE", "PROACTIVE", "PROACTIVE_MARGIN", "ORACLE"]
METRICS = ["billed_vm_hours", "pool_utilization_pct", "sla_violation_pct", "mean_response_s", "p99_response_s",
           "overloaded_intervals", "scale_ups", "scale_downs", "peak_vms", "mean_memory_gb"]


def main() -> None:
    validation = pd.read_csv(RESULTS / "validation" / "sim_summary.csv")
    test = pd.read_csv(RESULTS / "sim_summary.csv")

    frontier = test.groupby(["policy", "target_utilization"], as_index=False)[METRICS].mean()
    frontier.to_csv(RESULTS / "frontier.csv", index=False)

    tuned = validation.groupby(["policy", "target_utilization"], as_index=False)[["billed_vm_hours", "sla_violation_pct"]].mean()
    rows, paired = [], []
    for policy in ORDER:
        options = tuned[(tuned.policy == policy) & (tuned.sla_violation_pct <= SLA_LIMIT_PERCENT)]
        chosen = options.sort_values("billed_vm_hours").iloc[0]
        target = float(chosen.target_utilization)
        runs = test[(test.policy == policy) & (test.target_utilization == target)]
        row = {"policy": policy, "chosen_target": target, "validation_vm_hours": chosen.billed_vm_hours,
               "validation_sla_pct": chosen.sla_violation_pct, "runs": len(runs)}
        for metric in METRICS:
            row[metric] = runs[metric].mean()
        row["vm_hours_std"] = runs.billed_vm_hours.std()
        row["sla_std"] = runs.sla_violation_pct.std()
        rows.append(row)
    comparison = pd.DataFrame(rows)
    comparison.to_csv(RESULTS / "policy_comparison.csv", index=False)

    chosen_target = dict(zip(comparison.policy, comparison.chosen_target))
    pick = lambda policy: test[(test.policy == policy) & (test.target_utilization == chosen_target[policy])].set_index("scenario")
    base = pick("REACTIVE")
    for policy in ["PROACTIVE", "PROACTIVE_MARGIN", "ORACLE", "STATIC_PEAK"]:
        other = pick(policy).loc[base.index]
        saving = 100 * (base.billed_vm_hours - other.billed_vm_hours) / base.billed_vm_hours
        paired.append({
            "policy": policy, "mean_vm_hour_saving_pct": saving.mean(), "std_saving_pct": saving.std(),
            "workloads_cheaper": int((saving > 0).sum()), "workloads": len(saving),
            "workloads_sla_not_worse": int((other.sla_violation_pct <= base.sla_violation_pct).sum()),
            "scale_event_reduction_pct": 100 * (1 - (other.scale_ups + other.scale_downs).sum() / (base.scale_ups + base.scale_downs).sum()),
        })
    paired = pd.DataFrame(paired)
    paired.to_csv(RESULTS / "paired_comparison.csv", index=False)

    # Equal-cost pairs: the margin raises VM hours by about one target step, so
    # ML + margin at target x + 0.05 costs about the same as Reactive at target x.
    pairs = []
    for target in (0.80, 0.85, 0.90):
        reactive = test[(test.policy == "REACTIVE") & (np.isclose(test.target_utilization, target))].set_index("scenario")
        margin = test[(test.policy == "PROACTIVE_MARGIN") & (np.isclose(test.target_utilization, target + 0.05))].set_index("scenario").loc[reactive.index]
        pairs.append({
            "reactive_target": target, "ml_margin_target": target + 0.05,
            "reactive_vm_hours": reactive.billed_vm_hours.mean(), "ml_margin_vm_hours": margin.billed_vm_hours.mean(),
            "reactive_sla_pct": reactive.sla_violation_pct.mean(), "ml_margin_sla_pct": margin.sla_violation_pct.mean(),
            "reactive_p99_s": reactive.p99_response_s.mean(), "ml_margin_p99_s": margin.p99_response_s.mean(),
            "ml_margin_fewer_violations": int((margin.sla_violation_pct < reactive.sla_violation_pct).sum()),
            "ties": int((margin.sla_violation_pct == reactive.sla_violation_pct).sum()), "workloads": len(reactive),
        })
    pairs = pd.DataFrame(pairs)
    pairs.to_csv(RESULTS / "equal_cost.csv", index=False)

    # Per-day results at the validation-tuned targets show how far the days differ.
    test["date"] = test.scenario.str.split("_").str[0]
    by_day = []
    for policy in ORDER:
        runs = test[(test.policy == policy) & (test.target_utilization == chosen_target[policy])]
        for date, part in runs.groupby("date"):
            by_day.append({"policy": policy, "date": date, "billed_vm_hours": part.billed_vm_hours.mean(), "sla_violation_pct": part.sla_violation_pct.mean()})
    by_day = pd.DataFrame(by_day)
    by_day.to_csv(RESULTS / "policy_by_day.csv", index=False)

    pd.set_option("display.width", 220, "display.max_columns", 40)
    print(pairs.round(3).T)
    print(by_day.pivot(index="policy", columns="date", values="sla_violation_pct").round(2))
    print(tuned.pivot(index="target_utilization", columns="policy", values="sla_violation_pct").round(2)[ORDER])
    print(comparison.round(3).T)
    print(paired.round(3))
    print(frontier.pivot(index="target_utilization", columns="policy", values="billed_vm_hours").round(1)[ORDER])
    print(frontier.pivot(index="target_utilization", columns="policy", values="sla_violation_pct").round(2)[ORDER])
    print("work conserved in all runs:", bool((test.submitted_mi == test.completed_mi).all()), "failed VM creations:", int(test.failed_vm_creations.sum()))


if __name__ == "__main__":
    main()
