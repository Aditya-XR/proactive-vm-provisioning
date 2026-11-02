# Proactive VM Provisioning

Forecasts VM CPU demand with machine learning, uses the forecast to scale a VM pool ahead of demand inside a real CloudSim 5.0 simulation, and shows the results in a Streamlit dashboard.

Built for Question 10 of the Cloud Computing Lab (Day to Day Performance), BIT Mesra.

| Name | Roll number |
| --- | --- |
| Aditya Kumar | BTECH/10259/23 |
| Anish Mehta | BTECH/10242/23 |
| Tanishq Karmali | BTECH/10258/23 |

The full write-up is in [report/Cloud_Computing_Lab_Q10_Project_Report.pdf](report/Cloud_Computing_Lab_Q10_Project_Report.pdf) ([.docx](report/Cloud_Computing_Lab_Q10_Project_Report.docx)).

## How it works

1. **Data:** PlanetLab CPU traces bundled with CloudSim (11,746 VM-days, one sample every 5 minutes).
2. **Forecasting:** Ridge, Random Forest, Gradient Boosting and an MLP are compared with persistence and moving-average baselines, predicting CPU 10 minutes ahead. That horizon comes from the provisioning delay: the latest full measurement is one interval old, and a VM requested now serves from the next interval.
3. **Simulation:** `ProvisioningBroker` extends CloudSim's `DatacenterBroker` to start VMs with a 4 minute boot delay, drain them before removal, and release one minute of work at a time. Overload is real queueing inside CloudSim, not a formula.
4. **Comparison:** static, reactive, proactive, proactive with a safety margin, and an oracle with perfect foresight, on 10 test workloads.
5. **Dashboard:** workload patterns, predictions, provisioning decisions, resource utilization and policy comparison.

The model, safety margin and each policy's utilization target are all chosen on validation days. The test days are used only for the final numbers.

## Results

Forecast accuracy on the test days, per VM, 10 minutes ahead:

| Model | MAE | RMSE | R2 | Group MAPE |
| --- | --- | --- | --- | --- |
| Persistence (baseline) | 6.701 | 12.791 | 0.293 | 9.88 % |
| Moving Average (baseline) | 5.351 | 9.532 | 0.607 | 7.55 % |
| Ridge Regression | 5.244 | 9.467 | 0.612 | 7.42 % |
| **Random Forest (selected)** | 5.224 | 9.446 | 0.614 | 7.44 % |
| Gradient Boosting | 5.238 | 9.444 | 0.614 | 7.44 % |
| Neural Network (MLP) | 5.253 | 9.465 | 0.613 | 7.56 % |

Provisioning on the test days, at each policy's validation-tuned target (average of 10 workloads):

| Policy | VM hours | SLA violations | Scaling events |
| --- | --- | --- | --- |
| Static (peak, with hindsight) | 369.8 | 0.00 % | 0.0 |
| Reactive | 338.0 | 0.87 % | 84.3 |
| Proactive ML | 314.9 | 2.69 % | 21.8 |
| Proactive ML + margin | 322.5 | 1.59 % | 24.8 |
| Oracle | 304.3 | 0.05 % | 81.1 |

The findings are mixed, and the report discusses them in full:

- All four models clearly beat persistence, but they are almost tied with each other and only slightly better than a one-hour moving average. Within a VM, most short-term variation is noise.
- Proactive provisioning used 5 to 7 percent fewer VM hours and about 70 percent fewer scaling events than reactive.
- It missed the 1 percent SLA limit on the test days, while reactive held it. Most of the miss comes from 20 April, when the forecast ran 3 percent low and errors exceeded the margin learned on earlier days.

## Reproducing the results

You need Windows, JDK 8, Python 3.13 and a compiled CloudSim 5.0. Import CloudSim into Eclipse as an existing Maven project, which also fills your local Maven repository with `commons-math3`. CloudSim is expected at `C:\CloudSim\cloudsim-5.0`; set `CLOUDSIM_HOME` if yours is elsewhere, and `JDK8_HOME` if your JDK 8 is not the Temurin 8u502 default.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe ml\train.py             # about 10 minutes
.\.venv\Scripts\python.exe ml\test_no_leakage.py
.\scripts\run_experiments.ps1                      # checks, 800 simulations, analysis
.\.venv\Scripts\python.exe ml\make_figures.py
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Results are already committed in `results/`, so the dashboard runs without repeating the experiments.

`report/build_report.py` regenerates the report from `results/`. It takes the formatting from a template `.docx` passed with `--template`, which is not included here.

## Layout

| Path | Contents |
| --- | --- |
| `ml/` | Data loading, features, training, leakage test, analysis, figures |
| `simulator/src/provisioning/` | CloudSim broker, policies, experiment runner, hand-computed checks |
| `dashboard/app.py` | Streamlit dashboard |
| `results/` | Metrics, scenarios and simulation output |
| `figures/` | Report figures and dashboard screenshots |
| `report/` | Project report and its generator |
| `scripts/` | Build, experiment and screenshot scripts |

The workload traces are not copied here. They are read from the CloudSim source tree, and come from the CoMon project as prepared by Beloglazov and Buyya.
