"""Build the project report as a .docx in the same format as the Q8 report.

The styles, numbering and footer parts are taken from a template .docx; all
numbers in the text are read from the results folder.

Run: python report/build_report.py --template path/to/Q8_report.docx
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
OUTPUT = ROOT / "report" / "Cloud_Computing_Lab_Q10_Project_Report.docx"
REPO_URL = "https://github.com/Aditya-XR/proactive-vm-provisioning"

BLUE = "1F3F9E"
TNR = '<w:rFonts w:ascii="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman"/>'
COURIER = '<w:rFonts w:ascii="Courier New" w:cs="Courier New" w:eastAsia="Courier New" w:hAnsi="Courier New"/>'


class Doc:
    def __init__(self) -> None:
        self.body: list[str] = []
        self.images: list[Path] = []

    def run(self, text: str, size: int = 24, bold=False, italic=False, color=None, font=TNR) -> str:
        props = font
        if bold:
            props += "<w:b/><w:bCs/>"
        if italic:
            props += "<w:i/><w:iCs/>"
        if color:
            props += f'<w:color w:val="{color}"/>'
        props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(text, {chr(34): "&quot;"})}</w:t></w:r>'

    def para(self, text: str, props: str, **run) -> None:
        self.body.append(f"<w:p><w:pPr>{props}</w:pPr>{self.run(text, **run)}</w:p>")

    def center(self, text: str, after: int, size: int = 24, **run) -> None:
        self.para(text, f'<w:spacing w:after="{after}"/><w:jc w:val="center"/>', size=size, **run)

    def h1(self, text: str) -> None:
        self.para(text, '<w:pStyle w:val="Heading1"/><w:keepNext/><w:spacing w:after="140" w:before="300"/>', size=30, bold=True, color=BLUE)

    def h2(self, text: str) -> None:
        self.para(text, '<w:pStyle w:val="Heading2"/><w:keepNext/><w:spacing w:after="100" w:before="200"/>', size=26, bold=True, color=BLUE)

    def p(self, text: str) -> None:
        self.para(text, '<w:spacing w:after="140" w:line="300"/><w:jc w:val="both"/>')

    def eq(self, text: str) -> None:
        self.para(text, '<w:spacing w:after="140" w:line="300"/><w:jc w:val="center"/>', bold=True)

    def bullets(self, items: list[str]) -> None:
        for item in items:
            self.para(item, '<w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>'
                            '<w:spacing w:after="80" w:line="290"/><w:jc w:val="both"/>')

    def caption(self, text: str) -> None:
        self.para(text, '<w:spacing w:after="200"/><w:jc w:val="center"/>', size=22, italic=True)

    def reference(self, text: str) -> None:
        self.para(text, '<w:spacing w:after="100" w:line="290"/><w:ind w:left="500" w:hanging="500"/>')

    def code(self, lines: list[str]) -> None:
        for line in lines:
            self.para(line, '<w:keepNext/><w:spacing w:after="20"/><w:ind w:left="400"/>', size=20, font=COURIER)

    def page_break(self) -> None:
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def blank(self) -> None:
        self.body.append('<w:p><w:pPr><w:spacing w:after="120"/></w:pPr></w:p>')

    def table(self, rows: list[list[str]], widths: list[int], caption: str | None = None) -> None:
        borders = "".join(f'<w:{s} w:val="single" w:color="808080" w:sz="4"/>' for s in ("top", "left", "bottom", "right"))
        margins = '<w:tcMar><w:top w:type="dxa" w:w="60"/><w:left w:type="dxa" w:w="100"/><w:bottom w:type="dxa" w:w="60"/><w:right w:type="dxa" w:w="100"/></w:tcMar>'
        outer = "".join(f'<w:{s} w:val="single" w:color="auto" w:sz="4"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
        out = [f'<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="{sum(widths)}"/><w:tblBorders>{outer}</w:tblBorders></w:tblPr><w:tblGrid>']
        out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
        out.append("</w:tblGrid>")
        for r, row in enumerate(rows):
            header = r == 0
            out.append(f'<w:tr><w:trPr><w:cantSplit/>{"<w:tblHeader/>" if header else ""}</w:trPr>')
            for c, cell in enumerate(row):
                fill = '<w:shd w:fill="DCE6F5" w:color="auto" w:val="clear"/>' if header else ""
                jc = "left" if c == 0 else "center"
                out.append(f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{widths[c]}"/><w:tcBorders>{borders}</w:tcBorders>{fill}{margins}</w:tcPr>'
                           f'<w:p><w:pPr><w:keepNext/><w:jc w:val="{jc}"/></w:pPr>{self.run(str(cell), size=22, bold=header)}</w:p></w:tc>')
            out.append("</w:tr>")
        out.append("</w:tbl>")
        self.body.append("".join(out))
        if caption:
            self.caption(caption)

    def figure(self, name: str, caption: str, width_inches: float = 5.6) -> None:
        path = FIGURES / name
        with path.open("rb") as f:
            head = f.read(24)
        w, h = struct.unpack(">II", head[16:24])
        cx = int(width_inches * 914400)
        cy = int(cx * h / w)
        self.images.append(path)
        index = len(self.images)
        rid = f"rId{100 + index}"
        self.body.append(
            '<w:p><w:pPr><w:keepNext/><w:spacing w:after="60" w:before="100"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent t="0" r="0" b="0" l="0"/>'
            f'<wp:docPr id="{index}" name="{name}" descr="{escape(caption)}"/><wp:cNvGraphicFramePr>'
            '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="" descr=""/>'
            '<pic:cNvPicPr><a:picLocks noChangeAspect="1" noChangeArrowheads="1"/></pic:cNvPicPr></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}" cstate="none"/><a:srcRect/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr bwMode="auto"><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )
        self.caption(caption)


def write_report(doc: Doc) -> None:
    models = pd.read_csv(RESULTS / "model_metrics.csv")
    horizon = pd.read_csv(RESULTS / "horizon_metrics.csv")
    importance = pd.read_csv(RESULTS / "feature_importance.csv")
    selection = json.loads((RESULTS / "selection.json").read_text())
    policy = pd.read_csv(RESULTS / "policy_comparison.csv").set_index("policy")
    paired = pd.read_csv(RESULTS / "paired_comparison.csv").set_index("policy")
    frontier = pd.read_csv(RESULTS / "frontier.csv")
    equal = pd.read_csv(RESULTS / "equal_cost.csv")
    by_day = pd.read_csv(RESULTS / "policy_by_day.csv", dtype={"date": str})

    test = models[models.split == "test"].set_index("model")
    val = models[models.split == "validation"].set_index("model")
    selected = selection["selected_model"]
    margin = selection["safety_margin_p95"]
    rf, pers, ma = test.loc[selected], test.loc["Persistence (baseline)"], test.loc["Moving Average (baseline)"]
    best_r2 = test[~test.index.str.contains("baseline")].R2
    r, pm, m, o, s = (policy.loc[k] for k in ("REACTIVE", "PROACTIVE", "PROACTIVE_MARGIN", "ORACLE", "STATIC_PEAK"))
    day = lambda p, d: by_day[(by_day.policy == p) & (by_day.date == d)].iloc[0].sla_violation_pct
    front = lambda p, t, c: frontier[(frontier.policy == p) & (abs(frontier.target_utilization - t) < 1e-9)].iloc[0][c]
    h = lambda minutes, name: horizon[(horizon.minutes == minutes) & (horizon.model == name)].iloc[0]
    total = lambda row: row.scale_ups + row.scale_downs
    hi, mid, lo = equal.iloc[0], equal.iloc[1], equal.iloc[2]

    # Title page
    doc.center("BIRLA INSTITUTE OF TECHNOLOGY, MESRA", 60, 32, bold=True, color=BLUE)
    doc.center("Ranchi, Jharkhand", 900)
    doc.center("CLOUD COMPUTING LAB", 200, 28, bold=True)
    doc.center("Day to Day Performance: Project Report", 700)
    doc.center("Forecasting VM Resource Requirements for Proactive Provisioning", 160, 36, bold=True, color=BLUE)
    doc.center("A Machine Learning Workload Predictor Integrated with CloudSim and a Monitoring Dashboard", 100, 26)
    doc.center("(Question 10)", 800)
    doc.center("Submitted by", 160, bold=True)
    doc.table([["Name", "Roll Number"], ["Aditya Kumar", "BTECH/10259/23"], ["Anish Mehta", "BTECH/10242/23"], ["Tanishq Karmali", "BTECH/10258/23"]], [3600, 3600])
    doc.blank()
    doc.blank()
    doc.center("Course: Cloud Computing Lab", 60)
    doc.center("Institute: BIT Mesra", 60)
    doc.center("Submission deadline: 13th October 2026", 0)
    doc.page_break()

    doc.h1("Abstract")
    doc.p("A cloud provider must decide how many virtual machines (VMs) to keep running before the demand for them arrives. A new VM takes minutes to become ready, so an autoscaler that only reacts to the current load is always a little late. Proactive provisioning tries to close this gap by forecasting demand and starting VMs in advance. In this project we built and tested such a system from end to end, using real workload data and an actual CloudSim 5.0 simulation.")
    doc.p(f"We used the PlanetLab CPU traces distributed with CloudSim (11,746 VM-days sampled every five minutes) and compared four machine learning models, namely Ridge Regression, Random Forest, Gradient Boosting and a neural network, against two simple baselines for forecasting CPU demand 10 minutes ahead. {selected} was selected on validation days and reached an R2 of {rf.R2:.3f} on unseen test days, against {pers.R2:.3f} for the persistence baseline. However, all four models were almost tied, and a plain one-hour moving average was nearly as good (R2 of {ma.R2:.3f}), because most short-term variation in these traces is noise. We then wrote a custom CloudSim broker that starts and drains VMs during the simulation and ran 800 simulations. Tuned on validation days, proactive provisioning used {paired.loc['PROACTIVE_MARGIN'].mean_vm_hour_saving_pct:.1f} to {paired.loc['PROACTIVE'].mean_vm_hour_saving_pct:.1f} percent fewer VM hours than a reactive autoscaler and cut scaling events by about {paired.loc['PROACTIVE_MARGIN'].scale_event_reduction_pct:.0f} percent. It did not, however, hold the 1 percent SLA limit on the test days ({m.sla_violation_pct:.2f} to {pm.sla_violation_pct:.2f} percent, against {r.sla_violation_pct:.2f} percent for reactive), mainly because one test day was harder to forecast than the days used for tuning. A Streamlit dashboard presents the workload patterns, predictions, provisioning decisions and resource utilization.")

    doc.h1("1. Introduction")
    doc.h2("1.1 Background")
    doc.p("Elasticity is one of the main promises of cloud computing: resources should grow and shrink with demand, and users should pay only for what they use. In practice this is handled by an autoscaler, which watches a metric such as CPU utilization and changes the number of VMs. Most deployed autoscalers are reactive, meaning they respond to load that has already been measured [9].")
    doc.p("A reactive decision takes time to have any effect. The load must first be measured over an interval, and a new VM must then boot and start its application, which can take a few minutes. If demand rises during this time, the running VMs are overloaded until the new one is ready. Predictive autoscaling tries to avoid this by forecasting demand far enough ahead to cover the delay [8].")
    doc.h2("1.2 Motivation")
    doc.p("Provisioning has two opposite costs. Too few VMs means slow responses and broken service level agreements (SLAs), while too many means paying for idle machines. Keeping a fixed pool large enough for the daily peak is simple but wasteful, because the pool is then under-used for most of the day. A good forecast could keep the pool small without being caught out by rising demand, so it is worth finding out how much a forecast really helps on real workload data, and not only how accurate it looks in a table of prediction errors.")
    doc.h2("1.3 Problem Being Addressed")
    doc.p("A forecasting model with low error does not automatically produce better provisioning. The error that matters is the error at the time and scale at which the scaling decision is made, and an under-prediction costs more than an over-prediction. This project therefore connects the two halves of the problem. We train and compare forecasting models on real traces, then feed the selected model into a running CloudSim simulation and measure the effect on cost, SLA violations, response time and utilization.")

    doc.h1("2. Problem Statement and Objectives")
    doc.h2("2.1 Problem Statement")
    doc.p("Question 10 of the assignment sheet [11] states: Develop a machine learning application to forecast future virtual machine resource requirements in a cloud data centre. Use a suitable workload dataset and compare the performance of at least three machine learning models for predicting CPU and/or memory requirements. Evaluate the models using appropriate prediction metrics. Integrate the selected model with a cloud simulation environment to demonstrate proactive VM provisioning based on predicted demand. Develop a dashboard to visualize workload patterns, predictions, VM provisioning decisions, and resource utilization.")
    doc.h2("2.2 Objectives")
    doc.bullets([
        "To prepare a real VM workload dataset and turn it into a supervised forecasting problem with no leakage from the future.",
        "To compare at least three machine learning models, and simple baselines, using suitable prediction metrics.",
        "To select one model using validation data only, keeping the test days for the final evaluation.",
        "To integrate the selected model with CloudSim through a custom broker that starts and drains VMs during the simulation.",
        "To compare proactive provisioning with static and reactive provisioning on cost, SLA violations, response time and utilization.",
        "To build a dashboard showing workload patterns, predictions, provisioning decisions and resource utilization.",
    ])

    doc.h1("3. Dataset and Problem Formulation")
    doc.h2("3.1 Dataset")
    doc.p("We used the PlanetLab workload traces, a set of real CPU utilization measurements collected by the CoMon monitoring project [2] and prepared for cloud research by Beloglazov and Buyya [1]. They are distributed inside CloudSim itself, which makes them a natural choice for this project. We first tried the Bitbrains GWA-T-12 traces, which also contain memory, but the download server could not be reached. The PlanetLab traces hold CPU only, and the question allows CPU and/or memory, so this project forecasts CPU.")
    doc.table([
        ["Item", "Details"],
        ["Dataset name", "PlanetLab CoMon CPU traces, as distributed with CloudSim"],
        ["Source", "CoMon project [2]; prepared by Beloglazov and Buyya [1]"],
        ["URL", "github.com/Cloudslab/cloudsim, path modules/cloudsim-examples/src/main/resources/workload/planetlab"],
        ["Number of instances", "11,746 VM-days, 3,382,848 samples"],
        ["Time span", "10 non-consecutive days, March and April 2011"],
        ["Sampling", "One sample every 5 minutes, 288 per VM per day"],
        ["Raw field", "CPU utilization of one VM, integer percent (0 to 99)"],
        ["Engineered features", f"{selection['feature_count']} (Table 3)"],
        ["Target variable", "CPU utilization 10 minutes ahead (percent)"],
    ], [3000, 5500], "Table 1: Dataset summary")
    doc.p("Over all days the mean CPU utilization is 11.1 percent, the median is 5 percent and the 95th percentile is 43 percent, while 16.2 percent of samples are exactly zero. Most VMs are lightly loaded and a few are busy, as Figure 1 shows. The most important property for this project is how noisy each VM is: within one VM on a test day, the correlation between one sample and the next averages only 0.09. A VM's recent level is informative, but its next move is close to random.")
    doc.figure("fig2_workload.png", "Figure 1: Workload patterns: demand of one VM group over a day, and the distribution of CPU utilization")
    doc.h2("3.2 Preprocessing and Data Split")
    doc.p("Every file was checked to contain exactly 288 values in the valid range. There were no missing values, so no cleaning or imputation was needed, and tree models need no scaling (Ridge and the neural network use a standard scaler fitted on training data). The split follows time, so the model is always tested on days later than those it learned from. Each VM-day gives 275 rows, because the first hour supplies history and the last 10 minutes have no target.")
    doc.table([
        ["Split", "Days", "VM-days", "Rows", "Use"],
        ["Training", "3, 6, 9, 22, 25 March; 3 April", "7,068", "1,943,700", "Fit the models"],
        ["Validation", "9 and 11 April", "2,591", "712,525", "Select model, margin and targets"],
        ["Test", "12 and 20 April", "2,087", "573,925", "Final results only"],
    ], [1300, 2700, 1100, 1300, 2100], "Table 2: Time-ordered data split")
    doc.p(f"Each model was trained on the same random sample of {selection['train_rows']:,} training rows, repeated for five seeds, so that the slower models were not treated differently. VM names can repeat across days (for example 778 VMs appear on both 11 and 12 April), so a test VM may have been seen in earlier days, though never at a later time.")
    doc.h2("3.3 Forecasting Problem")
    doc.p("Let y_v(t) be the CPU utilization of VM v in interval t. Using only data up to interval t, the model predicts the value two intervals later. One global model is trained on all VMs, which lets it learn general behaviour and apply it to VMs with little history:")
    doc.eq("y_v(t + 2) = f( y_v(t), y_v(t - 1), ..., y_v(t - 11), fleet state, time of day )")
    doc.table([
        ["Feature group", "Features", "Count"],
        ["Lagged values", "CPU at t, t - 1, ..., t - 11 (last hour)", "12"],
        ["Rolling statistics", "Mean over 3, 6 and 12 samples; standard deviation over 6 and 12; maximum and minimum over 12; short-term trend", "8"],
        ["Fleet state", "Mean CPU of all VMs, now and over the last 6 samples", "2"],
        ["Time of day", "Sine and cosine of the time of day", "2"],
    ], [2300, 5200, 1000], "Table 3: Input features")
    doc.h2("3.4 Decision Timing")
    doc.p("The forecast horizon comes from the provisioning delay, not from a free choice. The broker makes a decision at the start of each 5 minute interval t. At that moment the latest complete measurement is for interval t - 1. A VM requested now needs 4 minutes to boot and so serves from interval t + 1. Each decision must therefore target interval t + 1 using data up to t - 1, which is two intervals, or 10 minutes, ahead.")
    doc.h2("3.5 Provisioning Problem and Assumptions")
    doc.p("We modelled one service whose load equals the combined demand of a random group of 100 traced VMs, served by a pool of identical worker VMs. Group demand in MIPS (million instructions per second) is D(t) = sum over the group of (y_v(t) / 100) x 1000. The decision variable is the number of VMs n(t) in each interval. The goal is to minimize billed VM hours while keeping SLA violations small, subject to a boot delay, a maximum pool size, and capacity limits on the hosts. The assignment leaves these details open, so we made the assumptions in Table 4.")
    doc.table([
        ["Assumption", "Value", "Justification"],
        ["Traced VM size", "1000 MIPS", "Traces give percent only; 1000 MIPS is a VM size used in CloudSim's own PlanetLab examples"],
        ["VM group size", "100 VMs", "Large enough to need many workers, small enough that demand still varies (peak about 1.3 times the mean)"],
        ["Worker VM", "1000 MIPS, 1 core, 2 GB RAM, 1 Gbps", "A small, common VM size, giving 10 to 20 workers"],
        ["Hosts", "5 hosts, 16 cores, 32 GB RAM, 10 Gbps", "Same size as PM1 in Question 7; room for 80 workers, so hosts are never the limit"],
        ["VM boot delay", "4 minutes", "Covers VM start and application warm-up; ready by the next interval"],
        ["Scale-in rule", "Remove a VM only after 3 ticks (15 minutes) below the pool size", "Avoids removing VMs on one low sample; same for all policies"],
        ["SLA", "One minute of work finishes within 60 s (+1 s for rounding); limit of 1 percent late slices", "The pool must keep up with arriving work; 1 percent is a common style of SLA target"],
    ], [2100, 2700, 3700], "Table 4: Simulation assumptions")
    doc.h2("3.6 Performance Measures")
    doc.p("Forecasts are judged at two levels. Per-VM error is the standard measure, but provisioning sees only group demand, so we also report the error of the 100-VM total. For actual value y, prediction p and n samples:")
    doc.bullets([
        "MAE = (1/n) x sum of |p - y|. Average size of the error in percent CPU.",
        "RMSE = square root of (1/n) x sum of (p - y)^2. Punishes large errors more.",
        "R2 = 1 - (sum of (p - y)^2) / (sum of (y - mean of y)^2). Share of variance explained.",
        "sMAPE = (100/n) x sum of 2|p - y| / (|y| + |p|). Scale-free, and usable when y is zero (the denominator is floored at 1).",
        "Group MAPE = mean of |P - Y| / Y for group totals P and Y, over 20 random 100-VM groups per day.",
    ])
    doc.p("Provisioning is judged by the following measures.")
    doc.bullets([
        "Billed VM hours: time from each VM request to its removal, including boot time, because clouds bill from the start. This is our measure of cost.",
        "SLA violations: percentage of one-minute work slices that finished late.",
        "Response time: time from a slice's arrival to its completion, as a mean and at the 99th percentile.",
        "Pool utilization: completed work divided by the capacity of ready VMs.",
        "Scaling events: the number of ticks at which VMs were added or removed.",
    ])

    doc.h1("4. System Architecture and Methodology")
    doc.h2("4.1 Architecture and Workflow")
    doc.p("Figure 2 shows the system. The Python side turns traces into features, trains and compares the models, and exports forecasts. The Java side runs the forecasts through CloudSim, where the custom broker makes a scaling decision every five minutes. The results go to the dashboard. Forecasts are computed in advance and read by the broker at the right interval, and we checked that each forecast uses only data available at its decision time.")
    doc.figure("fig1_architecture.png", "Figure 2: System architecture and workflow")
    doc.h2("4.2 Forecasting Models")
    doc.p("We compared four machine learning models, chosen to cover linear, bagged tree, boosted tree and neural approaches, with two baselines that any useful model must beat.")
    doc.table([
        ["Model", "Configuration"],
        ["Persistence (baseline)", "Predict the latest value"],
        ["Moving Average (baseline)", "Predict the mean of the last 12 samples (one hour)"],
        ["Ridge Regression", "Standardized inputs, alpha = 1.0"],
        ["Random Forest [5]", "100 trees, depth 14, at least 20 samples per leaf, 50 percent of features per split"],
        ["Gradient Boosting [6]", "Histogram method, 300 trees, learning rate 0.05, 31 leaves, at least 50 samples per leaf"],
        ["Neural Network (MLP)", "Two hidden layers (64, 32), batch 1024, up to 30 epochs, early stopping"],
    ], [3000, 5500], "Table 5: Models compared")
    doc.p("All models were built with scikit-learn [4] and use one chosen configuration, without a hyperparameter search. The configurations are sensible standard choices, and since the models ended up tied, a search would be unlikely to change the conclusion. The model with the lowest validation RMSE is selected.")
    doc.h2("4.3 Provisioning Policies")
    doc.p("At each tick a policy estimates the demand D for its target interval, and the pool size follows from a target utilization U (the same formula for every policy):")
    doc.eq("n(t + 1) = ceiling( D / (1000 x U) ), limited to between 1 and 64 VMs")
    doc.table([
        ["Policy", "Demand estimate D", "Purpose"],
        ["Static (peak)", "Highest demand of the whole day", "Baseline with no scaling; assumes hindsight"],
        ["Reactive", "Latest measurement D(t - 1)", "Target tracking, as in common cloud autoscalers"],
        ["Proactive ML", "Forecast of D(t + 1)", "The approach under test"],
        ["Proactive ML + margin", f"Forecast x {1 + margin:.3f}", "Protects against under-prediction"],
        ["Oracle", "True D(t + 1)", "Best any forecast could do"],
    ], [2500, 2900, 3100], "Table 6: Provisioning policies")
    doc.p(f"The margin of {margin * 100:.1f} percent is the 95th percentile of actual divided by forecast group demand on the validation days, minus one. It is a simple way of learning a safety buffer from past errors. Each policy gets its own target U, because comparing policies at the same U would be misleading: the same U gives different costs. For each policy we chose the cheapest U in the set 0.60, 0.65, ..., 0.95 that kept SLA violations at or below 1 percent on the validation days, and then applied that choice to the test days.")
    doc.h2("4.4 Dashboard")
    doc.p("The dashboard is built with Streamlit and Plotly [10]. The user picks a test day, a VM group, a target utilization and the policies to compare, and all charts update. It has five tabs: workload patterns, predictions, VM provisioning (VM counts, capacity against demand, and a scaling log), resource utilization (CPU, memory and response time), and policy comparison.")

    doc.h1("5. Mapping the Model to CloudSim")
    doc.p("The simulation is a real CloudSim 5.0 [3, 7] program, run on JDK 8 with the setup from Lab 1. Table 7 shows how each element maps to a CloudSim entity.")
    doc.table([
        ["Problem element", "CloudSim entity", "Setting"],
        ["Data centre", "Datacenter, Host, Pe", "5 hosts of Table 4, VmAllocationPolicySimple"],
        ["Worker VM", "Vm", "1000 MIPS, CloudletSchedulerTimeShared"],
        ["Demand", "Cloudlet", "One minute of demand, split equally over ready VMs"],
        ["Autoscaler", "ProvisioningBroker (extends DatacenterBroker)", "Self-sent tick event every 300 s"],
        ["VM boot", "VM_CREATE_ACK sent with a delay", "Request delayed by 240 s"],
        ["Scale-in", "VM_DESTROY after draining", "No new work; removed when its cloudlets finish"],
        ["Overload", "Time-shared queue on the Vm", "Cloudlets overlap and finish late"],
    ], [2200, 3200, 3100], "Table 7: Correspondence between the problem and CloudSim")
    doc.p("The default broker creates all VMs at the start and runs a fixed list of cloudlets, so it cannot do what this project needs. Our broker overrides that behaviour. It schedules events to itself every 60 seconds to release work, and every 300 seconds to take a scaling decision. Since overload is not calculated by a formula but arises from cloudlets sharing a VM inside CloudSim, a late response is a direct result of the simulation. The core logic is in the Appendix, and the full code is in the project repository [12].")

    doc.h1("6. Experimental Setup")
    doc.table([
        ["Item", "Details"],
        ["Hardware", "Intel Core i7-14700HX (28 logical processors), 16 GB RAM"],
        ["Operating system", "Windows 11"],
        ["Machine learning", "Python 3.13, scikit-learn 1.9, pandas 3.1, NumPy 2.5"],
        ["Simulation", "CloudSim 5.0, Java 8 (Temurin 8u502), Eclipse 2023-12"],
        ["Dashboard", "Streamlit 1.66, Plotly 7.1, Matplotlib 3.11"],
        ["Forecast runs", "4 models x 5 seeds; baselines are deterministic"],
        ["Test workloads", "2 test days x 5 random 100-VM groups = 10"],
        ["Validation workloads", "2 validation days x 5 random 100-VM groups = 10"],
        ["Simulation runs", "10 workloads x 5 policies x 8 targets = 400 for test, and 400 for validation"],
        ["Simulated period", "1 hour 5 minutes to 23 hours 55 minutes of each day (274 intervals)"],
        ["Forecast metrics", "MAE, RMSE, R2, sMAPE, Group MAPE"],
        ["Provisioning metrics", "VM hours, SLA violations, response time, utilization, scaling events"],
    ], [3000, 5500], "Table 8: Experimental configuration")
    doc.p("All policies received exactly the same demand in each workload. CloudSim is deterministic given its input, so repeating a run gives identical results, and the spread in our results comes from the different workloads. The question does not ask for cloud deployment, so the dashboard runs locally.")

    doc.h1("7. Results")
    doc.h2("7.1 Forecasting Results")
    doc.p("Table 9 gives the results on the test days. The four machine learning rows are averages over five seeds.")
    order = ["Persistence (baseline)", "Moving Average (baseline)", "Ridge Regression", "Random Forest", "Gradient Boosting", "Neural Network (MLP)"]
    doc.table([["Model", "MAE", "RMSE", "R2", "sMAPE", "Group MAPE"]] + [
        [n, f"{test.loc[n].MAE:.3f}", f"{test.loc[n].RMSE:.3f}", f"{test.loc[n].R2:.3f}", f"{test.loc[n].sMAPE:.2f} %", f"{test.loc[n].GroupMAPE:.2f} %"] for n in order
    ], [3000, 1000, 1000, 1000, 1100, 1400], "Table 9: Forecast accuracy on the test days, 10 minutes ahead (MAE and RMSE in percent CPU)")
    doc.figure("fig3_models.png", "Figure 3: Forecast error of each model on the test days")
    doc.p(f"{selected} had the lowest validation RMSE and was selected, as Table 10 shows. Its lead is very small: the four validation RMSE values all lie within {val.loc[order[2:]].RMSE.max() - val.loc[order[2:]].RMSE.min():.3f} of each other. On the test days Gradient Boosting was in fact slightly better on RMSE ({test.loc['Gradient Boosting'].RMSE:.3f} against {rf.RMSE:.3f}), which we report for honesty but did not use to change the selection. Gradient Boosting also trained about {test.loc['Random Forest'].fit_seconds / test.loc['Gradient Boosting'].fit_seconds:.0f} times faster.")
    doc.table([["Model", "Validation RMSE", "Validation R2", "Training time (s)", "Prediction per row (microseconds)"]] + [
        [n, f"{val.loc[n].RMSE:.3f}", f"{val.loc[n].R2:.3f}", f"{test.loc[n].fit_seconds:.1f}", f"{test.loc[n].predict_us_per_row:.2f}"] for n in order[2:]
    ], [2800, 1500, 1300, 1400, 1500], f"Table 10: Model selection on validation days (training on {selection['train_rows']:,} rows)")
    doc.figure("fig4_predictions.png", "Figure 4: Forecast against actual group demand on one test workload")
    doc.p(f"Figure 4 shows what the numbers mean. The forecast follows the slow daily shape of demand and ignores the rapid swings, while persistence copies each swing two intervals late. Figure 5 shows that accuracy hardly falls with the horizon: {selected} RMSE rises only from {h(5, selected).RMSE:.2f} at 5 minutes to {h(60, selected).RMSE:.2f} at 60 minutes. The permutation importance of the features agrees: shuffling the 12-sample mean raises RMSE by {importance.iloc[0].importance:.2f} points, the 6-sample mean by {importance.iloc[1].importance:.2f}, and every other feature by less than 0.1.")
    doc.figure("fig5_horizon.png", "Figure 5: Forecast error against horizon on the test days", 4.4)

    doc.h2("7.2 Provisioning Results")
    doc.p("Table 11 gives the test results for each policy at the target chosen on the validation days, averaged over 10 workloads. All 800 runs completed all submitted work, and no VM creation failed.")
    names = {"STATIC_PEAK": "Static (peak)", "REACTIVE": "Reactive", "PROACTIVE": "Proactive ML", "PROACTIVE_MARGIN": "ML + margin", "ORACLE": "Oracle"}
    doc.table([["Policy", "Target", "VM hours", "SLA violations", "Utilization", "P99 response", "Scaling events"]] + [
        [names[k], f"{v.chosen_target:.2f}", f"{v.billed_vm_hours:.1f}", f"{v.sla_violation_pct:.2f} %", f"{v.pool_utilization_pct:.1f} %", f"{v.p99_response_s:.1f} s", f"{v.scale_ups + v.scale_downs:.1f}"]
        for k, v in policy.iterrows()
    ], [1800, 900, 1100, 1300, 1200, 1200, 1000], "Table 11: Test results at the validation-tuned targets (average of 10 workloads)")
    doc.p(f"Compared with reactive scaling, Proactive ML used {paired.loc['PROACTIVE'].mean_vm_hour_saving_pct:.1f} percent fewer VM hours and ML + margin {paired.loc['PROACTIVE_MARGIN'].mean_vm_hour_saving_pct:.1f} percent fewer, and both were cheaper on all 10 workloads. They made {paired.loc['PROACTIVE'].scale_event_reduction_pct:.0f} and {paired.loc['PROACTIVE_MARGIN'].scale_event_reduction_pct:.0f} percent fewer scaling events. However, neither met the 1 percent limit, and reactive did. The Oracle needed {paired.loc['ORACLE'].mean_vm_hour_saving_pct:.1f} percent fewer VM hours than reactive with almost no violations, while the static pool cost {-paired.loc['STATIC_PEAK'].mean_vm_hour_saving_pct:.1f} percent more even with perfect hindsight of the peak.")
    doc.p("Table 12 splits the SLA results by day. The two test days behaved very differently.")
    doc.table([["Policy", "12 April", "20 April"]] + [
        [names[k], f"{day(k, '20110412'):.2f} %", f"{day(k, '20110420'):.2f} %"] for k in ["REACTIVE", "PROACTIVE", "PROACTIVE_MARGIN", "ORACLE"]
    ], [3000, 2000, 2000], "Table 12: SLA violations by test day")
    doc.figure("fig6_provisioning.png", "Figure 6: Provisioning decisions on one test workload at a target of 90 percent")
    doc.p("Figure 6 shows the main behavioural difference. The reactive pool moves up and down with almost every noisy sample, while the ML + margin pool follows the shape of the day in a few steps. Figure 7 compares all policies across all eight targets, which removes the effect of choosing a target. A curve that is lower or further left is better.")
    doc.figure("fig7_frontier.png", "Figure 7: Cost against SLA violations for all targets, with the vertical axis on a log scale above 0.1")
    doc.p("ML + margin at a target of U + 0.05 costs about the same as reactive at U, which allows the direct comparison in Table 13.")
    doc.table([["Reactive target", "ML + margin target", "VM hours (reactive / ML)", "SLA violations (reactive / ML)", "Workloads where ML is better"]] + [
        [f"{e.reactive_target:.2f}", f"{e.ml_margin_target:.2f}", f"{e.reactive_vm_hours:.1f} / {e.ml_margin_vm_hours:.1f}", f"{e.reactive_sla_pct:.2f} % / {e.ml_margin_sla_pct:.2f} %",
         f"{int(e.ml_margin_fewer_violations)} of {int(e.workloads)}" + (f" ({int(e.ties)} tied)" if e.ties else "")] for e in equal.itertuples()
    ], [1300, 1400, 1900, 2100, 1800], "Table 13: Reactive and ML + margin at about equal cost")
    doc.figure("fig8_utilization.png", "Figure 8: CPU utilization, allocated memory and response time at the tuned targets")

    doc.h2("7.3 Dashboard")
    doc.p("Figures 9 to 13 are screenshots of the running dashboard for one test workload at a target of 80 percent. Every chart has a title, labelled axes with units, and a legend.")
    doc.figure("dash_workload.png", "Figure 9: Dashboard, workload patterns", 5.8)
    doc.figure("dash_predictions.png", "Figure 10: Dashboard, prediction against actual demand", 5.8)
    doc.figure("dash_provisioning.png", "Figure 11: Dashboard, VM provisioning decisions", 5.8)
    doc.figure("dash_utilization.png", "Figure 12: Dashboard, resource utilization", 5.8)
    doc.figure("dash_comparison.png", "Figure 13: Dashboard, policy comparison", 5.8)

    doc.h1("8. Analysis and Discussion")
    doc.h2("8.1 What Worked")
    doc.p(f"The whole pipeline worked from end to end, on real data and in real CloudSim. All four models beat persistence clearly: RMSE fell from {pers.RMSE:.2f} to about {rf.RMSE:.2f}, and group MAPE from {pers.GroupMAPE:.2f} to {rf.GroupMAPE:.2f} percent. The clearest provisioning benefit is stability, with about 70 to 74 percent fewer scaling events, which means fewer VM starts and less disruption to a service. The forecast also saved money at the same target utilization, and at the low-cost end of Figure 7 it reduced SLA violations for the same spending: Table 13 shows {mid.reactive_sla_pct:.2f} falling to {mid.ml_margin_sla_pct:.2f} percent and {lo.reactive_sla_pct:.2f} falling to {lo.ml_margin_sla_pct:.2f} percent. On 12 April, ML provisioning beat reactive on both cost and SLA.")
    doc.h2("8.2 What Did Not")
    doc.p(f"The tuned proactive policies missed the 1 percent SLA limit on the test days, which is the most important negative result of this project. The learned margin did not generalize: on 20 April, violations reached {day('PROACTIVE_MARGIN', '20110420'):.2f} percent with the margin and {day('PROACTIVE', '20110420'):.2f} percent without it, against {day('REACTIVE', '20110420'):.2f} percent for reactive. The added machine learning also gave little gain over a simple method: the selected model was only slightly better than a one-hour moving average (R2 of {rf.R2:.3f} against {ma.R2:.3f}), and the choice of model barely mattered. At high spending the forecast did not help, since Table 13 shows reactive and ML equal at the first row ({hi.reactive_sla_pct:.2f} and {hi.ml_margin_sla_pct:.2f} percent).")
    doc.h2("8.3 Why")
    doc.p(f"The models tie because there is little left to learn. Each VM has a level that persists over an hour, but its movement around that level is nearly random (the correlation between neighbouring samples is about 0.09). Almost all the signal is in the recent mean, which every model finds, and which the moving average already is. This is also why accuracy barely changes with the horizon and why persistence does so badly: it copies noise.")
    doc.p("The saving in scaling events has the same cause. A reactive policy sees noise as real change, so it scales up on random peaks. The scale-in rule then holds those VMs for 15 minutes, which keeps the pool high. A smooth forecast does not chase these peaks. This same smoothness is a weakness, though: the forecast deliberately misses real short peaks, and the reactive pool, by holding on to recent peaks, happens to carry spare capacity that absorbs later ones. This explains the Oracle's advantage, which comes from knowing the noise in advance and which no forecast of this data can reach.")
    doc.p(f"The failure on 20 April comes from a difference between days. On the validation days and on 12 April the forecast bias was within 0.5 percent and group MAPE was 6.3 to 6.6 percent. On 20 April the forecast was 3.0 percent too low on average, and group MAPE rose to 8.5 percent. The actual-to-forecast ratio reached 1.22 at the 95th percentile, more than the 1.14 margin learned earlier. So a margin taken from a few past days can fail on a new day. The reactive policy does not depend on such a model and so was more robust here.")
    doc.h2("8.4 Trends Observed")
    doc.bullets([
        "Forecast accuracy is nearly flat from 5 to 60 minutes ahead, so horizon is not the limit here; the noise is.",
        "Every policy shows the same trade-off: raising the target lowers cost and raises SLA violations, slowly at first and then sharply. Above a target of about 0.85, violations grow by roughly three to four times for each 0.05 increase in the target.",
        f"At equal targets, the forecast runs hotter than reactive: at 0.85, Proactive ML costs {front('PROACTIVE', 0.85, 'billed_vm_hours'):.0f} VM hours against {front('REACTIVE', 0.85, 'billed_vm_hours'):.0f}, with {front('PROACTIVE', 0.85, 'sla_violation_pct'):.2f} against {front('REACTIVE', 0.85, 'sla_violation_pct'):.2f} percent violations. This is why equal-target comparisons mislead.",
        "Memory follows the VM count, because each worker holds a fixed 2 GB, so its saving matches the VM saving.",
        f"The gain from forecasting is bounded. Even the Oracle saved only {paired.loc['ORACLE'].mean_vm_hour_saving_pct:.1f} percent against reactive here, since this workload peaks at only about 1.3 times its mean. A burstier workload would leave more to gain.",
    ])
    doc.h2("8.5 Limitations")
    doc.bullets([
        "Only CPU is forecast, because the PlanetLab traces contain no memory data. Memory in our results is allocated memory, not forecast demand.",
        "Only two test days and ten workloads were used, and the VM groups on a day overlap. The results show a direction, not a precise estimate, and one difficult day strongly affected them.",
        "The trace days are not consecutive, so weekly patterns and day-to-day continuity cannot be used.",
        "The MIPS scale, boot delay, scale-in rule and SLA are our assumptions, and different values would change the numbers. The boot delay in particular fixes the 10 minute horizon.",
        "Traced VMs are treated as parts of one service with evenly divided work. Real services route requests differently, and work is not shifted away from a VM that has fallen behind.",
        "Each model has one configuration, with no hyperparameter search, and the forecast is trained once and never retrained during a day.",
        "Hosts are never the limit, so VM placement, migration and energy are not studied.",
    ])

    doc.h1("9. Validation of the Simulation")
    doc.p("Because the conclusions depend on the custom broker, we tested it on small scenarios whose correct answer can be worked out by hand. The program SimulatorChecks runs these automatically, and all checks passed. The results are in Table 14.")
    doc.table([
        ["Check", "Expected", "Measured"],
        ["Steady load 1600 MIPS, target 0.8: VMs used", "2", "2"],
        ["Same: response time (60 s x 0.8)", "48.0 s", "48.0 s"],
        ["Same: SLA violations", "0 %", "0 %"],
        ["Same: work completed equals work submitted", "8,640,000 MI", "8,640,000 MI"],
        ["Step in demand: reactive VMs before the step", "1", "1"],
        ["Step: reactive VMs one boot after seeing it", "4", "4"],
        ["Step: oracle VMs when the step begins", "4", "4"],
        ["Step: oracle SLA violations", "0 %", "0 %"],
        ["Static pool: VMs from the peak", "3", "3"],
        ["Static pool: billed hours (3 VMs, 8 intervals)", "2.00", "1.99"],
        ["Static pool: utilization equals the target", "80 %", "80.4 %"],
    ], [5000, 1750, 1750], "Table 14: Simulator checks")
    doc.p("The step test confirms the core idea of the project in the simulator. With the same demand step, the reactive policy was late and the Oracle was on time, so the timing of Section 3.4 is what the broker actually does. The small differences in the last two rows arise because the final slice finishes before the end of its interval, so the VMs are released slightly early. We also confirmed that completed work equals submitted work in all 800 full runs, so no work is lost when VMs are drained.")
    doc.p("To protect the results from bias, the model, margin and target were all chosen on validation days, and the test days were used only for final reporting. When the test results turned out worse than validation, we kept them and did not retune.")

    doc.h1("10. Conclusion")
    doc.p(f"We built a complete proactive provisioning system: a forecasting pipeline on real PlanetLab traces, a custom CloudSim 5.0 broker that scales VMs during the simulation, and an interactive dashboard. Machine learning models clearly beat persistence (R2 of about {best_r2.max():.2f} against {pers.R2:.2f}), but were almost tied with each other and only slightly better than a moving average. In the simulation, proactive provisioning cut VM hours by about 5 to 7 percent and scaling events by about 70 percent compared with a reactive autoscaler. However, it broke the 1 percent SLA limit on the test days, mainly on one day that was harder to forecast than the tuning days, while the reactive policy held it. Our conclusion is therefore mixed: on this workload, forecasting gives a calmer and somewhat cheaper pool but less safety, and its main value is stability rather than lower SLA violations. The project also shows why such a system must be judged in simulation and not only by prediction error, since near-identical forecast errors hid a large difference between days.")

    doc.h1("11. Future Scope")
    doc.bullets([
        "Use a trace with both CPU and memory, such as Bitbrains or the Google cluster data, to forecast both resources and size VMs on both.",
        "Replace the fixed margin with one that adapts to recent forecast errors during the day, and test whether this holds the SLA on days like 20 April.",
        "Combine the policies by taking the larger of the forecast and the latest measurement, which may keep the stability of the forecast and the safety of reactive scaling.",
        "Use quantile regression to predict an upper bound on demand directly, since under-prediction costs more than over-prediction.",
        "Test on consecutive days with more test days, and retrain the model during the simulation.",
        "Test burstier workloads and different boot delays, where forecasting should matter more.",
        "Add host-level consolidation and a power model to measure energy, using CloudSim's power package.",
    ])

    doc.h1("References")
    for line in [
        '[1]  A. Beloglazov and R. Buyya, "Optimal online deterministic algorithms and adaptive heuristics for energy and performance efficient dynamic consolidation of virtual machines in cloud data centers," Concurrency and Computation: Practice and Experience, vol. 24, no. 13, pp. 1397-1420, 2012.',
        '[2]  K. Park and V. S. Pai, "CoMon: a mostly-scalable monitoring system for PlanetLab," ACM SIGOPS Operating Systems Review, vol. 40, no. 1, pp. 65-74, 2006.',
        '[3]  R. N. Calheiros, R. Ranjan, A. Beloglazov, C. A. F. De Rose and R. Buyya, "CloudSim: a toolkit for modeling and simulation of cloud computing environments and evaluation of resource provisioning algorithms," Software: Practice and Experience, vol. 41, no. 1, pp. 23-50, 2011.',
        '[4]  F. Pedregosa et al., "Scikit-learn: machine learning in Python," Journal of Machine Learning Research, vol. 12, pp. 2825-2830, 2011.',
        '[5]  L. Breiman, "Random forests," Machine Learning, vol. 45, no. 1, pp. 5-32, 2001.',
        '[6]  J. H. Friedman, "Greedy function approximation: a gradient boosting machine," Annals of Statistics, vol. 29, no. 5, pp. 1189-1232, 2001.',
        '[7]  CloudSim project page and documentation, Cloud Computing and Distributed Systems (CLOUDS) Laboratory, University of Melbourne. https://github.com/Cloudslab/cloudsim',
        '[8]  N. Roy, A. Dubey and A. Gokhale, "Efficient autoscaling in the cloud using predictive models for workload forecasting," Proceedings of IEEE International Conference on Cloud Computing, pp. 500-507, 2011.',
        '[9]  T. Lorido-Botran, J. Miguel-Alonso and J. A. Lozano, "A review of auto-scaling techniques for elastic applications in cloud environments," Journal of Grid Computing, vol. 12, no. 4, pp. 559-592, 2014.',
        '[10]  Python, pandas, NumPy, Matplotlib, Streamlit and Plotly documentation (python.org, pandas.pydata.org, numpy.org, matplotlib.org, streamlit.io, plotly.com).',
        '[11]  Assignment sheet, Cloud Computing Lab: Day to Day Performance, Question 10, BIT Mesra, September 2026.',
        f'[12]  Project source code and results. {REPO_URL}',
    ]:
        doc.reference(line)

    doc.page_break()
    doc.h1("Appendix: Core Logic of the Provisioning Broker")
    doc.p("The following shortened code from ProvisioningBroker.java runs at every tick. The complete program, the training code and steps to reproduce every result are in the repository [12].")
    doc.code([
        "double planned = plannedDemand();  // depends on the policy",
        "int target = vmsFor(planned);      // ceil(planned / (mips x U))",
        "recentTargets.addLast(target);",
        "int pool = ready - draining + booting;",
        "if (target > pool) {",
        "    for (int i = pool; i < target; i++) {",
        "        requestVm(bootDelaySeconds);  // VM_CREATE after 240 s",
        "    }",
        "} else if (recentTargets.size() == scaleInTicks) {",
        "    int keep = max(recentTargets);    // last 3 ticks",
        "    if (keep < pool) {",
        "        drain(pool - keep);  // no new work, destroy when idle",
        "    }",
        "}",
    ])


def package(doc: Doc, template: Path) -> None:
    work = OUTPUT.with_suffix(".tmp")
    if work.exists():
        shutil.rmtree(work)
    with zipfile.ZipFile(template) as z:
        z.extractall(work)
        names = z.namelist()
    for old in (work / "word" / "media").glob("*"):
        old.unlink()

    head_source = (work / "word" / "document.xml").read_text(encoding="utf-8")
    head = head_source[: head_source.index("<w:body>") + len("<w:body>")]
    section = head_source[head_source.rindex("<w:sectPr"):head_source.rindex("</w:body>")]
    (work / "word" / "document.xml").write_text(head + "".join(doc.body) + section + "</w:body></w:document>", encoding="utf-8")

    rels_path = work / "word" / "_rels" / "document.xml.rels"
    rels = rels_path.read_text(encoding="utf-8")
    kept = "".join(part + ">" for part in rels.split(">") if part and 'relationships/image"' not in part and "</Relationships" not in part)
    image_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    media = []
    for index, path in enumerate(doc.images, 1):
        target = f"media/image{index}.png"
        shutil.copy(path, work / "word" / target)
        media.append(f'<Relationship Id="rId{100 + index}" Type="{image_type}" Target="{target}"/>')
    rels_path.write_text(kept + "".join(media) + "</Relationships>", encoding="utf-8")

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (work / "docProps" / "core.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>Cloud Computing Lab Question 10 Project Report</dc:title><dc:creator>Aditya Kumar</dc:creator><cp:lastModifiedBy>Aditya Kumar</cp:lastModifiedBy><cp:revision>1</cp:revision>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>',
        encoding="utf-8",
    )

    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(work / "[Content_Types].xml", "[Content_Types].xml")
        for path in sorted(work.rglob("*")):
            arcname = path.relative_to(work).as_posix()
            if path.is_file() and arcname != "[Content_Types].xml":
                z.write(path, arcname)
    shutil.rmtree(work)
    print("wrote", OUTPUT, "images", len(doc.images))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args()
    document = Doc()
    write_report(document)
    package(document, args.template)
