"""Create the report figures from the results folder. Run: python ml/make_figures.py"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))
import data

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
DARK = "#1f3f9e"
BLUE = "#5b9bd5"
ORANGE = "#d97f2b"
GREEN = "#70ad47"
GREY = "#7f7f7f"
RED = "#c0504d"
LABELS = {"STATIC_PEAK": "Static (peak)", "REACTIVE": "Reactive", "PROACTIVE": "Proactive ML",
          "PROACTIVE_MARGIN": "Proactive ML + margin", "ORACLE": "Oracle"}
COLORS = {"STATIC_PEAK": GREY, "REACTIVE": ORANGE, "PROACTIVE": BLUE, "PROACTIVE_MARGIN": DARK, "ORACLE": GREEN}
SCENARIO = "20110412_g101"
plt.rcParams.update({"figure.dpi": 200, "savefig.bbox": "tight", "font.size": 10, "axes.titlesize": 12})


def style(ax, grid="y"):
    ax.grid(axis=grid, alpha=0.3)
    ax.set_axisbelow(True)


def box(ax, x, y, w, h, text, fill="#eaf0fa"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.006", fc=fill, ec=DARK, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.8)


def arrow(ax, start, end, rad=0.0):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=13, lw=1.6, color="#333333",
                                 connectionstyle=f"arc3,rad={rad}"))


def architecture():
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.14, 0.97, "Machine learning (Python)", ha="center", fontsize=9.5, weight="bold", color=DARK)
    ax.text(0.5, 0.97, "Simulation (CloudSim 5.0, Java)", ha="center", fontsize=9.5, weight="bold", color=DARK)
    ax.text(0.86, 0.97, "Output", ha="center", fontsize=9.5, weight="bold", color=DARK)

    box(ax, 0.02, 0.76, 0.24, 0.15, "PlanetLab CPU traces\n(11,746 VM-days, 5 min)")
    box(ax, 0.02, 0.53, 0.24, 0.15, "Feature builder\n(lags, rolling statistics,\nfleet mean, time of day)")
    box(ax, 0.02, 0.30, 0.24, 0.15, "Train and compare models\n(Ridge, RF, GB, MLP)")
    box(ax, 0.02, 0.07, 0.24, 0.15, "Select on validation days;\nforecast 10 minutes ahead")
    arrow(ax, (0.14, 0.76), (0.14, 0.685))
    arrow(ax, (0.14, 0.53), (0.14, 0.455))
    arrow(ax, (0.14, 0.30), (0.14, 0.225))

    box(ax, 0.36, 0.76, 0.28, 0.15, "Demand and forecast series\nfor a 100-VM group")
    box(ax, 0.36, 0.53, 0.28, 0.15, "ProvisioningBroker\nevery 5 min: choose VM count\n(reactive, proactive, oracle)", "#fdf5e0")
    box(ax, 0.36, 0.30, 0.28, 0.15, "Start VMs (4 min boot) or\ndrain VMs (scale-in cooldown)")
    box(ax, 0.36, 0.07, 0.28, 0.15, "Datacenter, hosts, worker VMs\nrun one-minute cloudlets")
    arrow(ax, (0.26, 0.145), (0.33, 0.145))
    ax.plot([0.33, 0.33], [0.145, 0.835], color="#333333", lw=1.6)
    arrow(ax, (0.33, 0.835), (0.36, 0.835))
    arrow(ax, (0.50, 0.76), (0.50, 0.685))
    arrow(ax, (0.50, 0.53), (0.50, 0.455))
    arrow(ax, (0.50, 0.30), (0.50, 0.225))

    box(ax, 0.74, 0.53, 0.24, 0.15, "Metrics: VM hours, SLA\nviolations, response time,\nutilization, scaling events")
    box(ax, 0.74, 0.20, 0.24, 0.15, "Streamlit dashboard\nand report figures")
    arrow(ax, (0.64, 0.145), (0.70, 0.145))
    ax.plot([0.70, 0.70], [0.145, 0.605], color="#333333", lw=1.6)
    arrow(ax, (0.70, 0.605), (0.74, 0.605))
    arrow(ax, (0.86, 0.53), (0.86, 0.355))
    fig.savefig(FIGURES / "fig1_architecture.png")
    plt.close(fig)


def workload():
    frame = pd.read_csv(RESULTS / "scenarios" / f"{SCENARIO}.csv")
    days = data.load_all()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2), gridspec_kw={"width_ratios": [1.5, 1]})
    hours = frame.interval * 5 / 60
    axes[0].plot(hours, frame.demand_mips, color=DARK, lw=1)
    axes[0].set(title="CPU demand of one 100-VM group (12 April 2011)", xlabel="Hour of day", ylabel="Demand (MIPS)", xlim=(0, 24))
    style(axes[0])
    values = np.concatenate([d.ravel() for d in days.values()])
    axes[1].hist(values, bins=np.arange(0, 102, 5), color=BLUE, edgecolor="white", weights=np.full(values.size, 100 / values.size))
    axes[1].set(title="Per-VM CPU utilization (all days)", xlabel="CPU utilization (percent)", ylabel="Share of samples (percent)")
    style(axes[1])
    fig.tight_layout()
    fig.savefig(FIGURES / "fig2_workload.png")
    plt.close(fig)


def models():
    test = pd.read_csv(RESULTS / "model_metrics.csv").query("split == 'test'")
    names = test.model.str.replace(" (baseline)", "\n(baseline)").str.replace(" (MLP)", "\n(MLP)").str.replace(" ", "\n", 1)
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.3))
    colors = [GREY, GREY, BLUE, DARK, BLUE, BLUE]
    for ax, column, title, unit in ((axes[0], "RMSE", "Per-VM RMSE on the test days", "RMSE (percent CPU)"),
                                    (axes[1], "GroupMAPE", "Error of 100-VM group demand", "MAPE (percent)")):
        ax.bar(range(len(test)), test[column], color=colors)
        ax.set_xticks(range(len(test)), names, fontsize=6.8)
        ax.set(title=title, ylabel=unit)
        style(ax)
        for i, value in enumerate(test[column]):
            ax.text(i, value, f"{value:.2f}", ha="center", va="bottom", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig3_models.png")
    plt.close(fig)


def predictions():
    frame = pd.read_csv(RESULTS / "scenarios" / f"{SCENARIO}.csv").dropna()
    hours = frame.interval * 5 / 60
    previous = frame.demand_mips.shift(2)
    fig, ax = plt.subplots(figsize=(8.0, 3.2))
    ax.plot(hours, frame.demand_mips, color=DARK, lw=1, label="Actual demand")
    ax.plot(hours, frame.forecast_mips, color=ORANGE, lw=1.4, label="Random Forest forecast (10 min ahead)")
    ax.plot(hours, previous, color=GREY, lw=0.7, alpha=0.7, label="Persistence baseline")
    ax.set(title="Prediction against actual demand, one test workload", xlabel="Hour of day", ylabel="Demand (MIPS)", xlim=(1, 24))
    ax.legend(fontsize=8, ncol=3, loc="upper center")
    ax.set_ylim(top=frame.demand_mips.max() * 1.15)
    style(ax)
    fig.savefig(FIGURES / "fig4_predictions.png")
    plt.close(fig)


def horizons():
    frame = pd.read_csv(RESULTS / "horizon_metrics.csv")
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    for name, color, marker in (("Random Forest", DARK, "o"), ("Persistence (baseline)", GREY, "s")):
        part = frame[frame.model == name]
        ax.plot(part.minutes, part.RMSE, color=color, marker=marker, label=name)
    ax.set(title="Forecast error against horizon", xlabel="Forecast horizon (minutes)", ylabel="Per-VM RMSE (percent CPU)", ylim=(0, 15))
    ax.legend(fontsize=8)
    style(ax, "both")
    fig.savefig(FIGURES / "fig5_horizon.png")
    plt.close(fig)


def provisioning():
    target = 0.9
    frame = pd.read_csv(RESULTS / "sim_intervals.csv")
    frame = frame[(frame.scenario == SCENARIO) & (frame.target_utilization == target)]
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 4.8), sharex=True)
    demand = frame[frame.policy == "REACTIVE"]
    for policy in ("REACTIVE", "PROACTIVE_MARGIN"):
        part = frame[frame.policy == policy]
        hours = part.interval * 5 / 60
        axes[0].step(hours, part.ready_vms, where="post", color=COLORS[policy], label=LABELS[policy], lw=1.2)
        axes[1].step(hours, part.capacity_mips, where="post", color=COLORS[policy], label=f"Capacity, {LABELS[policy]}", lw=1.2)
    axes[1].plot(demand.interval * 5 / 60, demand.demand_mips, color="black", lw=0.8, label="Demand")
    axes[0].set(title="Provisioning decisions on one test workload (target 90 percent)", ylabel="Ready VMs")
    axes[1].set(xlabel="Hour of day", ylabel="MIPS", xlim=(1, 24))
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8, ncol=3, loc="upper center")
    axes[1].set_ylim(top=demand.demand_mips.max() * 1.45)
    style(axes[0])
    style(axes[1])
    fig.tight_layout()
    fig.savefig(FIGURES / "fig6_provisioning.png")
    plt.close(fig)


def frontier():
    frame = pd.read_csv(RESULTS / "frontier.csv")
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for policy in ("STATIC_PEAK", "REACTIVE", "PROACTIVE", "PROACTIVE_MARGIN", "ORACLE"):
        part = frame[frame.policy == policy].sort_values("billed_vm_hours")
        ax.plot(part.billed_vm_hours, part.sla_violation_pct, marker="o", ms=3.5, color=COLORS[policy], label=LABELS[policy])
    ax.axhline(1, color=RED, ls="--", lw=1)
    ax.text(ax.get_xlim()[1], 1.08, "1 percent SLA limit", color=RED, ha="right", fontsize=8)
    ax.set_yscale("symlog", linthresh=0.1)
    ax.set_yticks([0, 0.1, 1, 10], ["0", "0.1", "1", "10"])
    ax.set_ylim(-0.01, 40)
    ax.set(title="Cost against SLA violations (average of 10 test workloads)", xlabel="Billed VM hours per day", ylabel="SLA violations (percent of slices)")
    ax.legend(fontsize=8)
    style(ax, "both")
    fig.savefig(FIGURES / "fig7_frontier.png")
    plt.close(fig)


def utilization():
    comparison = pd.read_csv(RESULTS / "policy_comparison.csv")
    labels = [LABELS[p].replace(" + ", "\n+ ").replace(" (", "\n(").replace("Proactive ML\n", "Proactive\nML\n").replace("Proactive ML", "Proactive\nML") for p in comparison.policy]
    colors = [COLORS[p] for p in comparison.policy]
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 3.0))
    for ax, column, title, ylabel in ((axes[0], "pool_utilization_pct", "CPU utilization", "Percent"),
                                      (axes[1], "mean_memory_gb", "Memory allocated", "GB"),
                                      (axes[2], "p99_response_s", "99th percentile response", "Seconds")):
        ax.bar(range(len(comparison)), comparison[column], color=colors)
        ax.set_xticks(range(len(comparison)), labels, fontsize=6.5)
        ax.set(title=title, ylabel=ylabel)
        style(ax)
        for i, value in enumerate(comparison[column]):
            ax.text(i, value, f"{value:.1f}", ha="center", va="bottom", fontsize=7)
    axes[2].axhline(61, color=RED, ls="--", lw=1)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig8_utilization.png")
    plt.close(fig)


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    architecture()
    workload()
    models()
    predictions()
    horizons()
    provisioning()
    frontier()
    utilization()
    print("figures written to", FIGURES)
