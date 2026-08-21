"""Evaluate probability calibrators on Southern legislative elections, 2018-2024."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "processed" / "forecast_calibration"
PANEL = DIR / "southern_legislative_probability_panel.csv"
WAR = ROOT / "data" / "processed" / "war"
EPS = 1e-5


def logistic(features: list[str]) -> Pipeline:
    numeric = [x for x in features if x != "chamber"]
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]), numeric))
    if "chamber" in features:
        transformers.append(("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]))
    return Pipeline([
        ("prep", ColumnTransformer(transformers)),
        ("model", LogisticRegression(C=1.0, max_iter=2000)),
    ])


def spline_logistic() -> Pipeline:
    return Pipeline([
        ("prep", ColumnTransformer([
            ("margin", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("spline", SplineTransformer(n_knots=5, degree=2, include_bias=False)),
                ("scale", StandardScaler()),
            ]), ["environment_baseline_margin"]),
            ("other", Pipeline([
                ("impute", SimpleImputer(strategy="constant", fill_value=0)),
                ("scale", StandardScaler()),
            ]), ["incumbency_balance"]),
            ("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]),
        ])),
        ("model", LogisticRegression(C=.5, max_iter=2000)),
    ])


SPECS = {
    "logit_margin": (logistic(["environment_baseline_margin"]), ["environment_baseline_margin"]),
    "logit_margin_chamber": (logistic(["environment_baseline_margin", "chamber"]), ["environment_baseline_margin", "chamber"]),
    "logit_margin_incumbency": (logistic(["environment_baseline_margin", "incumbency_balance", "chamber"]),
                                 ["environment_baseline_margin", "incumbency_balance", "chamber"]),
    "spline_margin_incumbency": (spline_logistic(), ["environment_baseline_margin", "incumbency_balance", "chamber"]),
    "logit_demographic_reactivity": (
        logistic(["prior_pres_margin", "national_swing", "nonwhite_share", "white_college_share",
                  "swing_x_nonwhite", "swing_x_white_college", "chamber"]),
        ["prior_pres_margin", "national_swing", "nonwhite_share", "white_college_share",
         "swing_x_nonwhite", "swing_x_white_college", "chamber"],
    ),
}


def metrics(frame: pd.DataFrame) -> dict[str, float]:
    y = frame.dem_win.to_numpy(); p = np.clip(frame.dem_probability.to_numpy(), EPS, 1 - EPS)
    bins = pd.qcut(p, q=min(10, p.size), duplicates="drop")
    grouped = frame.assign(bin=bins).groupby("bin", observed=True).agg(p=("dem_probability", "mean"), y=("dem_win", "mean"))
    return {
        "n": len(frame), "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p),
        "auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan,
        "calibration_mae": float((grouped.p - grouped.y).abs().mean()),
    }


def normal_scale(train: pd.DataFrame) -> float:
    grid = np.linspace(4, 30, 261)
    y = train.dem_win.to_numpy(); margin = train.environment_baseline_margin.to_numpy()
    scores = [np.mean((ndtr(margin / scale) - y) ** 2) for scale in grid]
    return float(grid[int(np.argmin(scores))])


def fit_predict(name: str, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    if name == "normal_margin":
        return ndtr(test.environment_baseline_margin.to_numpy() / normal_scale(train))
    if name == "isotonic_margin":
        iso = IsotonicRegression(y_min=.01, y_max=.99, out_of_bounds="clip")
        return iso.fit(train.environment_baseline_margin, train.dem_win).predict(test.environment_baseline_margin)
    model, features = SPECS[name]
    fitted = clone(model).fit(train[features], train.dem_win)
    return fitted.predict_proba(test[features])[:, 1]


def main() -> None:
    data = pd.read_csv(PANEL)
    data = data[data.primary_calibration_eligible.astype(bool)].copy()
    names = ["normal_margin", "isotonic_margin", *SPECS]
    if data[["nonwhite_share", "white_college_share"]].notna().all(axis=1).sum() < 100:
        names.remove("logit_demographic_reactivity")
    predictions = []
    # Genuine temporal tests. The first model sees 2018 before predicting 2020;
    # later tests never train on the cycle they predict.
    for test_year in (2020, 2022, 2024):
        train = data[data.year.lt(test_year)]
        test = data[data.year.eq(test_year)]
        if train.empty or test.empty:
            continue
        for name in names:
            probability = fit_predict(name, train, test)
            for row, p in zip(test.itertuples(), probability):
                predictions.append({
                    "validation": "forward_cycle", "holdout": str(test_year), "specification": name,
                    "state": row.state, "year": row.year, "chamber": row.chamber, "district": row.district,
                    "environment_baseline_margin": row.environment_baseline_margin,
                    "dem_win": row.dem_win, "dem_probability": float(p),
                })
    # Geographic portability: Alabama is not in the calibration sample, so a
    # winning specification must also survive unseen-state tests.
    for state in sorted(data.state.unique()):
        train, test = data[data.state.ne(state)], data[data.state.eq(state)]
        if train.empty or test.empty:
            continue
        for name in names:
            probability = fit_predict(name, train, test)
            for row, p in zip(test.itertuples(), probability):
                predictions.append({
                    "validation": "leave_state_out", "holdout": state, "specification": name,
                    "state": row.state, "year": row.year, "chamber": row.chamber, "district": row.district,
                    "environment_baseline_margin": row.environment_baseline_margin,
                    "dem_win": row.dem_win, "dem_probability": float(p),
                })
    pred = pd.DataFrame(predictions)
    pred.to_csv(DIR / "southern_probability_tournament_predictions.csv", index=False)
    rows = []
    for keys, group in pred.groupby(["validation", "holdout", "specification"]):
        rows.append(dict(zip(["validation", "holdout", "specification"], keys), **metrics(group)))
    detail = pd.DataFrame(rows)
    detail.to_csv(DIR / "southern_probability_tournament_metrics.csv", index=False)
    summary = (detail.groupby(["validation", "specification"], as_index=False)
               .agg(holdouts=("holdout", "nunique"), brier=("brier", "mean"),
                    log_loss=("log_loss", "mean"), auc=("auc", "mean"),
                    calibration_mae=("calibration_mae", "mean")))
    overall = (summary.pivot(index="specification", columns="validation", values=["brier", "log_loss", "calibration_mae"])
               .reset_index())
    overall.columns = ["_".join([str(x) for x in col if x]).rstrip("_") if isinstance(col, tuple) else col for col in overall.columns]
    overall = overall.sort_values(["brier_forward_cycle", "brier_leave_state_out"])
    overall.to_csv(DIR / "southern_probability_tournament_summary.csv", index=False)

    selected = overall.specification.iloc[0]
    al = pd.read_csv(WAR / "next_forecast_tournament_2026.csv")
    al = al[al.specification.isin(["cmo_expectation__blend20", "cmo_expectation__blend100"])].copy()
    al = al.rename(columns={"predicted_dem_margin": "environment_baseline_margin"})
    # Current Alabama candidates are intentionally not assigned cross-state
    # incumbency values in the probability-only first pass.
    al["incumbency_balance"] = 0.0
    # Alabama demographic fields are already available in the prospective
    # forecast table; retain them for the demographic-reactivity challenger.
    al["national_swing"] = np.nan
    al["prior_pres_margin"] = al.environment_baseline_margin
    al["swing_x_nonwhite"] = al.national_swing * al.get("nonwhite_share", np.nan)
    al["swing_x_white_college"] = al.national_swing * al.get("white_college_share", np.nan)
    al["dem_probability_calibrated"] = fit_predict(selected, data, al)
    al["probability_specification"] = selected
    al.to_csv(DIR / "alabama_2026_southern_calibrated_probabilities.csv", index=False)

    curve_margin = np.linspace(-60, 60, 241)
    curve = pd.DataFrame({"environment_baseline_margin": curve_margin, "incumbency_balance": 0.0, "chamber": "lower"})
    curve["dem_probability"] = fit_predict(selected, data, curve)
    curve["specification"] = selected
    curve.to_csv(DIR / "southern_probability_calibration_curve.csv", index=False)
    print(overall.to_string(index=False))
    print("\nSelected:", selected)
    print("\nAlabama HD-21")
    print(al[(al.chamber.eq("house")) & (al.district.eq(21))][
        ["specification", "environment_baseline_margin", "dem_probability_calibrated"]].to_string(index=False))


if __name__ == "__main__":
    main()
