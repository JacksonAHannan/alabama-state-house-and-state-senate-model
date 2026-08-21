"""Test demographic national-swing reactivity as a Southern legislative baseline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "processed" / "forecast_calibration"

FEATURES = {
    "direct_environment_baseline": [],
    "demographic_context": ["nonwhite_share", "white_college_share", "chamber"],
    "demographic_reactivity": ["nonwhite_share", "white_college_share", "swing_x_nonwhite",
                               "swing_x_white_college", "chamber"],
}


def model(features: list[str]) -> Pipeline:
    numeric = [x for x in features if x != "chamber"]
    return Pipeline([
        ("prep", ColumnTransformer([
            ("numeric", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), numeric),
            ("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]),
        ])),
        ("ridge", Ridge(alpha=20.0)),
    ])


def probability_scale(train: pd.DataFrame, predictions: np.ndarray) -> float:
    grid = np.linspace(4, 30, 261)
    y = train.dem_win.to_numpy()
    scores = [np.mean((ndtr(predictions / scale) - y) ** 2) for scale in grid]
    return float(grid[int(np.argmin(scores))])


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray, float]:
    if not features:
        train_prediction = train.environment_baseline_margin.to_numpy()
        test_prediction = test.environment_baseline_margin.to_numpy()
    else:
        fitted = model(features)
        target = train.dem_margin - train.environment_baseline_margin
        fitted.fit(train[features], target)
        train_prediction = train.environment_baseline_margin.to_numpy() + fitted.predict(train[features])
        test_prediction = test.environment_baseline_margin.to_numpy() + fitted.predict(test[features])
    scale = probability_scale(train, train_prediction)
    return test_prediction, ndtr(test_prediction / scale), scale


def main() -> None:
    data = pd.read_csv(DIR / "southern_legislative_probability_panel.csv")
    data = data[data.primary_calibration_eligible.astype(bool)].dropna(
        subset=["nonwhite_share", "white_college_share"]
    ).copy()
    rows, predictions = [], []
    for test_year in (2020, 2022, 2024):
        train, test = data[data.year.lt(test_year)], data[data.year.eq(test_year)]
        for name, features in FEATURES.items():
            margin, probability, scale = fit_predict(train, test, features)
            actual = test.dem_margin.to_numpy(); winner = test.dem_win.to_numpy()
            rows.append({
                "test_year": test_year, "specification": name, "n": len(test),
                "mae": np.mean(np.abs(actual - margin)),
                "rmse": np.sqrt(np.mean((actual - margin) ** 2)),
                "bias": np.mean(actual - margin),
                "winner_accuracy": np.mean((margin > 0) == winner),
                "brier": brier_score_loss(winner, probability),
                "log_loss": log_loss(winner, np.clip(probability, 1e-5, 1 - 1e-5)),
                "probability_scale": scale,
            })
            for row, m, p in zip(test.itertuples(), margin, probability):
                predictions.append({
                    "test_year": test_year, "specification": name, "state": row.state,
                    "chamber": row.chamber, "district": row.district, "actual_margin": row.dem_margin,
                    "predicted_margin": m, "dem_win": row.dem_win, "dem_probability": p,
                })
    detail = pd.DataFrame(rows)
    summary = (detail.groupby("specification", as_index=False)
               .agg(cycles=("test_year", "nunique"), mae=("mae", "mean"), rmse=("rmse", "mean"),
                    absolute_bias=("bias", lambda x: np.mean(np.abs(x))),
                    winner_accuracy=("winner_accuracy", "mean"), brier=("brier", "mean"),
                    log_loss=("log_loss", "mean")))
    summary = summary.sort_values(["mae", "brier"])
    detail.to_csv(DIR / "southern_demographic_forecast_cycle_metrics.csv", index=False)
    summary.to_csv(DIR / "southern_demographic_forecast_summary.csv", index=False)
    pd.DataFrame(predictions).to_csv(DIR / "southern_demographic_forecast_predictions.csv", index=False)
    print(summary.to_string(index=False))
    print("\nCycle detail")
    print(detail.sort_values(["test_year", "mae"]).to_string(index=False))


if __name__ == "__main__":
    main()
