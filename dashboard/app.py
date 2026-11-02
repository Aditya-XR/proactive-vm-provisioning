"""Streamlit dashboard for the proactive VM provisioning results.

Run: streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

RESULTS = Path(__file__).parent.parent / "results"
POLICY_LABELS = {
    "STATIC_PEAK": "Static (peak)",
    "REACTIVE": "Reactive",
    "PROACTIVE": "Proactive ML",
    "PROACTIVE_MARGIN": "Proactive ML + margin",
    "ORACLE": "Oracle",
}
POLICY_COLORS = {
    "Static (peak)": "#7f7f7f",
    "Reactive": "#d97f2b",
    "Proactive ML": "#5b9bd5",
    "Proactive ML + margin": "#1f3f9e",
    "Oracle": "#70ad47",
}
MINUTES = 5


@st.cache_data
def load():
    summary = pd.read_csv(RESULTS / "sim_summary.csv")
    intervals = pd.read_csv(RESULTS / "sim_intervals.csv")
    models = pd.read_csv(RESULTS / "model_metrics.csv")
    horizons = pd.read_csv(RESULTS / "horizon_metrics.csv")
    importance = pd.read_csv(RESULTS / "feature_importance.csv")
    selection = json.loads((RESULTS / "selection.json").read_text())
    for frame in (summary, intervals):
        frame["policy_label"] = frame["policy"].map(POLICY_LABELS)
        frame["date"] = frame["scenario"].str.split("_").str[0]
        frame["group"] = frame["scenario"].str.split("_").str[1]
    intervals["hour"] = intervals["interval"] * MINUTES / 60
    return summary, intervals, models, horizons, importance, selection


def load_scenario(name: str) -> pd.DataFrame:
    frame = pd.read_csv(RESULTS / "scenarios" / f"{name}.csv")
    frame["hour"] = frame["interval"] * MINUTES / 60
    return frame


summary, intervals, models, horizons, importance, selection = load()

st.set_page_config(page_title="Proactive VM Provisioning", layout="wide")
st.title("Proactive VM Provisioning Dashboard")
st.caption(
    "Cloud Computing Lab, BIT Mesra, Question 10. CPU demand from PlanetLab traces, "
    f"forecast by {selection['selected_model']}, simulated in CloudSim 5.0."
)

with st.sidebar:
    st.header("Scenario")
    scenario = st.selectbox("Test day and VM group", sorted(summary["scenario"].unique()))
    target = st.select_slider(
        "Target pool utilization", options=sorted(summary["target_utilization"].unique()), value=0.8,
        format_func=lambda v: f"{v:.0%}",
    )
    chosen = st.multiselect(
        "Policies", list(POLICY_LABELS.values()), default=["Reactive", "Proactive ML", "Proactive ML + margin"],
    )
    st.caption(f"Forecast horizon: {selection['horizon_steps'] * MINUTES} minutes. Worker VM: 1000 MIPS, 2 GB.")

view = intervals[(intervals["scenario"] == scenario) & (intervals["target_utilization"] == target)]
runs = summary[(summary["scenario"] == scenario) & (summary["target_utilization"] == target)]
averages = (
    summary[summary["target_utilization"] == target]
    .groupby("policy_label", sort=False)
    .mean(numeric_only=True)
    .reset_index()
)

tab_workload, tab_forecast, tab_provision, tab_utilization, tab_compare = st.tabs(
    ["Workload patterns", "Predictions", "VM provisioning", "Resource utilization", "Policy comparison"]
)

with tab_workload:
    frame = load_scenario(scenario)
    left, right = st.columns([2, 1])
    with left:
        figure = px.line(frame, x="hour", y="demand_mips", labels={"hour": "Hour of day", "demand_mips": "CPU demand (MIPS)"},
                         title="CPU demand of the selected 100-VM group")
        figure.update_traces(line_color="#1f3f9e")
        st.plotly_chart(figure, width='stretch')
    with right:
        figure = px.histogram(frame, x="demand_mips", nbins=30, labels={"demand_mips": "CPU demand (MIPS)", "count": "Intervals"},
                              title="Distribution of demand")
        figure.update_traces(marker_color="#5b9bd5")
        figure.update_layout(yaxis_title="Intervals")
        st.plotly_chart(figure, width='stretch')
    a, b, c, d = st.columns(4)
    a.metric("Mean demand", f"{frame.demand_mips.mean():,.0f} MIPS")
    b.metric("Peak demand", f"{frame.demand_mips.max():,.0f} MIPS")
    c.metric("Peak / mean", f"{frame.demand_mips.max() / frame.demand_mips.mean():.2f}")
    d.metric("Coefficient of variation", f"{frame.demand_mips.std() / frame.demand_mips.mean():.3f}")

with tab_forecast:
    frame = load_scenario(scenario).dropna(subset=["forecast_mips"])
    left, right = st.columns([2, 1])
    with left:
        figure = go.Figure()
        figure.add_scatter(x=frame.hour, y=frame.demand_mips, name="Actual", line=dict(color="#1f3f9e"))
        figure.add_scatter(x=frame.hour, y=frame.forecast_mips, name="Forecast", line=dict(color="#d97f2b"))
        figure.update_layout(title=f"Prediction vs actual, {selection['horizon_steps'] * MINUTES} minutes ahead",
                             xaxis_title="Hour of day", yaxis_title="CPU demand (MIPS)")
        st.plotly_chart(figure, width='stretch')
    with right:
        error = (frame.forecast_mips - frame.demand_mips).abs() / frame.demand_mips * 100
        st.metric("Group MAPE on this day", f"{error.mean():.2f} %")
        st.metric("Under-forecast intervals", f"{(frame.forecast_mips < frame.demand_mips).mean():.1%}")
        figure = px.scatter(frame, x="demand_mips", y="forecast_mips", labels={"demand_mips": "Actual (MIPS)", "forecast_mips": "Forecast (MIPS)"})
        low, high = frame.demand_mips.min(), frame.demand_mips.max()
        figure.add_shape(type="line", x0=low, y0=low, x1=high, y1=high, line=dict(color="#7f7f7f", dash="dash"))
        figure.update_traces(marker=dict(color="#5b9bd5", size=5))
        st.plotly_chart(figure, width='stretch')
    test = models[models["split"] == "test"]
    left, right = st.columns(2)
    with left:
        figure = px.bar(test, x="model", y="RMSE", title="Per-VM RMSE on the test days (percent CPU)", labels={"model": ""})
        figure.update_traces(marker_color="#1f3f9e")
        st.plotly_chart(figure, width='stretch')
    with right:
        figure = px.bar(test, x="model", y="GroupMAPE", title="Group demand MAPE on the test days (percent)", labels={"model": ""})
        figure.update_traces(marker_color="#5b9bd5")
        st.plotly_chart(figure, width='stretch')
    st.dataframe(test[["model", "MAE", "RMSE", "R2", "sMAPE", "GroupMAPE", "GroupUnder"]].round(3), width='stretch', hide_index=True)

with tab_provision:
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                           subplot_titles=("Ready VMs", "Capacity against demand"))
    for label in chosen:
        part = view[view.policy_label == label]
        figure.add_scatter(x=part.hour, y=part.ready_vms, name=label, line=dict(color=POLICY_COLORS[label], shape="hv"), row=1, col=1)
        figure.add_scatter(x=part.hour, y=part.capacity_mips, name=label, line=dict(color=POLICY_COLORS[label], shape="hv"),
                           showlegend=False, row=2, col=1)
    if len(view):
        part = view[view.policy == view.policy.iloc[0]]
        figure.add_scatter(x=part.hour, y=part.demand_mips, name="Demand", line=dict(color="black", width=1), row=2, col=1)
    figure.update_yaxes(title_text="VMs", row=1, col=1)
    figure.update_yaxes(title_text="MIPS", row=2, col=1)
    figure.update_xaxes(title_text="Hour of day", row=2, col=1)
    figure.update_layout(height=620, title="Provisioning decisions")
    st.plotly_chart(figure, width='stretch')
    decisions = view[view.policy_label.isin(chosen)]
    decisions = decisions.sort_values(["policy_label", "interval"]).copy()
    decisions["change"] = decisions.groupby("policy_label").ready_vms.diff().fillna(0).astype(int)
    log = decisions[decisions.change != 0][["policy_label", "hour", "demand_mips", "planned_mips", "ready_vms", "change"]]
    st.subheader("VM scaling log")
    st.dataframe(log.rename(columns={"policy_label": "Policy", "hour": "Hour", "demand_mips": "Demand", "planned_mips": "Planned", "ready_vms": "Ready VMs", "change": "Change"}).round(2),
                 width='stretch', hide_index=True, height=260)

with tab_utilization:
    left, right = st.columns(2)
    with left:
        figure = go.Figure()
        for label in chosen:
            part = view[view.policy_label == label]
            figure.add_scatter(x=part.hour, y=part.offered_utilization_pct, name=label, line=dict(color=POLICY_COLORS[label]))
        figure.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Capacity")
        figure.update_layout(title="CPU utilization of the VM pool", xaxis_title="Hour of day", yaxis_title="Utilization (percent)")
        st.plotly_chart(figure, width='stretch')
    with right:
        figure = go.Figure()
        for label in chosen:
            part = view[view.policy_label == label]
            figure.add_scatter(x=part.hour, y=part.memory_gb, name=label, line=dict(color=POLICY_COLORS[label], shape="hv"))
        figure.update_layout(title="Memory allocated to the pool", xaxis_title="Hour of day", yaxis_title="Memory (GB)")
        st.plotly_chart(figure, width='stretch')
    figure = go.Figure()
    for label in chosen:
        part = view[view.policy_label == label]
        figure.add_scatter(x=part.hour, y=part.mean_response_s, name=label, line=dict(color=POLICY_COLORS[label]))
    figure.add_hline(y=61, line_dash="dash", line_color="red", annotation_text="SLA limit")
    figure.update_layout(title="Mean response time of the one-minute work slices", xaxis_title="Hour of day", yaxis_title="Seconds")
    st.plotly_chart(figure, width='stretch')

with tab_compare:
    st.subheader(f"Average over {summary.scenario.nunique()} workloads at {target:.0%} target")
    table = averages[["policy_label", "billed_vm_hours", "pool_utilization_pct", "sla_violation_pct", "mean_response_s", "p99_response_s", "overloaded_intervals", "scale_ups", "scale_downs"]]
    st.dataframe(table.rename(columns={
        "policy_label": "Policy", "billed_vm_hours": "VM hours", "pool_utilization_pct": "Utilization %",
        "sla_violation_pct": "SLA violations %", "mean_response_s": "Mean response (s)", "p99_response_s": "P99 response (s)",
        "overloaded_intervals": "Overloaded intervals", "scale_ups": "Scale ups", "scale_downs": "Scale downs",
    }).round(2), width='stretch', hide_index=True)
    st.subheader("Targets tuned on validation days for at most 1% SLA violations")
    tuned = pd.read_csv(RESULTS / "policy_comparison.csv")
    tuned["Policy"] = tuned["policy"].map(POLICY_LABELS)
    st.dataframe(tuned[["Policy", "chosen_target", "billed_vm_hours", "sla_violation_pct", "pool_utilization_pct", "p99_response_s", "scale_ups", "scale_downs"]].rename(columns={
        "chosen_target": "Target", "billed_vm_hours": "VM hours", "sla_violation_pct": "SLA violations %",
        "pool_utilization_pct": "Utilization %", "p99_response_s": "P99 response (s)", "scale_ups": "Scale ups", "scale_downs": "Scale downs",
    }).round(2), width='stretch', hide_index=True)
    trade = summary.groupby(["policy_label", "target_utilization"], sort=False).mean(numeric_only=True).reset_index()
    trade = trade[trade.sla_violation_pct > 0]  # a log axis cannot show zero
    figure = px.line(trade.sort_values("billed_vm_hours"), x="billed_vm_hours", y="sla_violation_pct", color="policy_label", markers=True, log_y=True,
                     color_discrete_map=POLICY_COLORS, hover_data=["target_utilization"],
                     labels={"billed_vm_hours": "Billed VM hours", "sla_violation_pct": "SLA violations (percent, log scale)", "policy_label": "Policy", "target_utilization": "Target"},
                     title="Cost against SLA violations (runs with zero violations are not shown)")
    figure.add_hline(y=1, line_dash="dash", line_color="red", annotation_text="1% limit")
    st.plotly_chart(figure, width='stretch')
