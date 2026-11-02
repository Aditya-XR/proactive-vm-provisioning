"""Compare forecasting models, select one on validation data, export forecasts.

Run: python ml/train.py
Writes results/model_metrics.csv, results/horizon_metrics.csv,
results/feature_importance.csv, results/selection.json and results/forecasts/*.npz
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
import data
import features
from features import FEATURE_NAMES, build_features, build_many

RESULTS = Path(__file__).parent.parent / "results"
HORIZON = 2  # decide at the end of t for interval t + 2, see report section 3.4
TRAIN_ROWS = 400_000
SEEDS = [11, 22, 33, 44, 55]
GROUP_SIZE = 100
LAG_1 = FEATURE_NAMES.index("lag_0")
MEAN_12 = FEATURE_NAMES.index("mean_12")


def model_factories() -> dict:
    return {
        "Ridge Regression": lambda seed: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Random Forest": lambda seed: RandomForestRegressor(
            n_estimators=100, max_depth=14, min_samples_leaf=20, max_features=0.5, n_jobs=-1, random_state=seed
        ),
        "Gradient Boosting": lambda seed: HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50, random_state=seed
        ),
        "Neural Network (MLP)": lambda seed: make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32), batch_size=1024, learning_rate_init=1e-3, max_iter=30,
                early_stopping=True, n_iter_no_change=4, random_state=seed,
            ),
        ),
    }


def per_vm_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    error = p - y
    denom = (np.abs(y) + np.abs(p)).clip(min=1.0)
    return {
        "MAE": float(np.abs(error).mean()),
        "RMSE": float(np.sqrt((error**2).mean())),
        "R2": float(1 - (error**2).sum() / ((y - y.mean()) ** 2).sum()),
        "sMAPE": float(200 * (np.abs(error) / denom).mean()),
    }


def group_series(day: np.ndarray, prediction: np.ndarray, seed: int, size: int = GROUP_SIZE):
    """Sum actual and predicted CPU of a random VM group, per target interval."""
    vms = day.shape[0]
    origins = prediction.size // vms
    rows = prediction.reshape(vms, origins)
    chosen = np.random.default_rng(seed).choice(vms, size, replace=False)
    start = features.MAX_LAG - 1 + HORIZON
    return day[chosen, start:].sum(axis=0), rows[chosen].sum(axis=0)


def group_metrics(day: np.ndarray, prediction: np.ndarray) -> dict:
    """Aggregate error over 20 random 100-VM groups; this is what provisioning sees."""
    relative, under = [], []
    for seed in range(20):
        actual, predicted = group_series(day, prediction, seed)
        relative.append(np.abs(predicted - actual) / actual)
        under.append(predicted < actual)
    return {"GroupMAPE": float(100 * np.mean(relative)), "GroupUnder": float(100 * np.mean(under))}


def evaluate(days, dates, predict, split, name, seed, rows):
    ys, ps, groups = [], [], []
    for date in dates:
        X, y, _, _ = build_features(days[date], HORIZON)
        p = predict(X)
        ys.append(y)
        ps.append(p)
        groups.append(group_metrics(days[date], p))
    row = {"model": name, "split": split, "seed": seed}
    row.update(per_vm_metrics(np.concatenate(ys), np.concatenate(ps)))
    row.update({k: float(np.mean([g[k] for g in groups])) for k in groups[0]})
    rows.append(row)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "forecasts").mkdir(exist_ok=True)
    days = data.load_all()
    X_full, y_full = build_many(days, data.TRAIN_DATES, HORIZON)
    print("training pool", X_full.shape, flush=True)

    rows: list[dict] = []
    timings: list[dict] = []
    evaluate(days, data.VALIDATION_DATES, lambda X: X[:, LAG_1], "validation", "Persistence (baseline)", 0, rows)
    evaluate(days, data.TEST_DATES, lambda X: X[:, LAG_1], "test", "Persistence (baseline)", 0, rows)
    evaluate(days, data.VALIDATION_DATES, lambda X: X[:, MEAN_12], "validation", "Moving Average (baseline)", 0, rows)
    evaluate(days, data.TEST_DATES, lambda X: X[:, MEAN_12], "test", "Moving Average (baseline)", 0, rows)

    fitted: dict[tuple[str, int], object] = {}
    for name, factory in model_factories().items():
        for seed in SEEDS:
            index = np.random.default_rng(seed).choice(y_full.size, TRAIN_ROWS, replace=False)
            model = factory(seed)
            start = time.perf_counter()
            model.fit(X_full[index], y_full[index])
            fit_seconds = time.perf_counter() - start
            start = time.perf_counter()
            model.predict(X_full[:100_000])
            timings.append({
                "model": name, "seed": seed, "fit_seconds": fit_seconds,
                "predict_us_per_row": (time.perf_counter() - start) * 10,
            })
            predict = lambda X, m=model: np.clip(m.predict(X), 0, 100)
            evaluate(days, data.VALIDATION_DATES, predict, "validation", name, seed, rows)
            evaluate(days, data.TEST_DATES, predict, "test", name, seed, rows)
            fitted[(name, seed)] = model
            print(name, seed, f"fit {fit_seconds:.1f}s", {k: round(v, 3) for k, v in rows[-1].items() if k not in ("model", "split", "seed")}, flush=True)

    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "model_metrics_by_seed.csv", index=False)
    summary = metrics.groupby(["split", "model"], sort=False).agg(
        MAE=("MAE", "mean"), MAE_std=("MAE", "std"), RMSE=("RMSE", "mean"), RMSE_std=("RMSE", "std"),
        R2=("R2", "mean"), sMAPE=("sMAPE", "mean"), GroupMAPE=("GroupMAPE", "mean"),
        GroupMAPE_std=("GroupMAPE", "std"), GroupUnder=("GroupUnder", "mean"),
    ).reset_index()
    summary = summary.merge(pd.DataFrame(timings).groupby("model").mean(numeric_only=True).drop(columns="seed").reset_index(), how="left", on="model")
    summary.to_csv(RESULTS / "model_metrics.csv", index=False)

    # Model selection uses validation data only; the test rows play no part.
    candidates = summary[(summary.split == "validation") & (~summary.model.str.contains("baseline"))]
    best_name = candidates.sort_values("RMSE").iloc[0].model
    best_seed = SEEDS[0]
    best = fitted[(best_name, best_seed)]
    print("selected", best_name, flush=True)

    predict = lambda X: np.clip(best.predict(X), 0, 100)

    # Under-forecast margin: a validation-set quantile of relative group error.
    ratios = []
    for date in data.VALIDATION_DATES:
        X, _, _, _ = build_features(days[date], HORIZON)
        p = predict(X)
        for seed in range(20):
            actual, predicted = group_series(days[date], p, seed)
            ratios.append(actual / predicted.clip(min=1e-6))
    ratios = np.concatenate(ratios)
    margin = float(np.quantile(ratios, 0.95) - 1)

    # Export per-VM forecasts for the simulator (dates needed by the policies).
    for date in data.VALIDATION_DATES + data.TEST_DATES:
        X, _, _, origins = build_features(days[date], HORIZON)
        vms = days[date].shape[0]
        prediction = predict(X).reshape(vms, -1).astype(np.float32)
        np.savez_compressed(RESULTS / "forecasts" / f"{date}.npz", prediction=prediction, first_target=features.MAX_LAG - 1 + HORIZON)

    # Horizon study for the selected model family against persistence.
    horizon_rows = []
    for horizon in (1, 2, 3, 6, 12):
        X_h, y_h = build_many(days, data.TRAIN_DATES, horizon)
        index = np.random.default_rng(SEEDS[0]).choice(y_h.size, TRAIN_ROWS, replace=False)
        model = model_factories()[best_name](SEEDS[0])
        model.fit(X_h[index], y_h[index])
        X_t, y_t = build_many(days, data.TEST_DATES, horizon)
        p = np.clip(model.predict(X_t), 0, 100)
        horizon_rows.append({"minutes": horizon * 5, "model": best_name, **per_vm_metrics(y_t, p)})
        horizon_rows.append({"minutes": horizon * 5, "model": "Persistence (baseline)", **per_vm_metrics(y_t, X_t[:, LAG_1])})
    pd.DataFrame(horizon_rows).to_csv(RESULTS / "horizon_metrics.csv", index=False)

    # Permutation importance on a validation sample.
    X_val, y_val = build_many(days, data.VALIDATION_DATES, HORIZON)
    index = np.random.default_rng(1).choice(y_val.size, 50_000, replace=False)
    importance = permutation_importance(best, X_val[index], y_val[index], scoring="neg_root_mean_squared_error", n_repeats=3, random_state=1, n_jobs=-1)
    pd.DataFrame({"feature": FEATURE_NAMES, "importance": importance.importances_mean}).sort_values("importance", ascending=False).to_csv(RESULTS / "feature_importance.csv", index=False)

    (RESULTS / "selection.json").write_text(json.dumps({
        "selected_model": best_name, "selection_seed": best_seed, "horizon_steps": HORIZON,
        "train_rows": TRAIN_ROWS, "training_pool_rows": int(y_full.size), "feature_count": len(FEATURE_NAMES),
        "safety_margin_p95": margin,
    }, indent=2))
    print(summary.round(3).to_string())
    print("margin", margin)


if __name__ == "__main__":
    main()
