#!/usr/bin/env python3
"""Tournament cross-state historical CMO structural expectations."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_heda_panel.csv"
PANEL_MANIFEST = ROOT / "data/processed/forecast_calibration/historical_southern_heda_manifest.json"
OUTPUT = ROOT / "data/processed/war"
KEYS = ["state", "year", "chamber", "district"]
MODEL_SPECS = {
    "baseline_only": {"kind": "baseline"},
    "pooled_lag": {"kind": "mean"},
    "symmetric_incumbency": {"numeric": ["incumbency_balance"], "categorical": [], "alpha": 1.0},
    "state_chamber_lag": {"numeric": [], "categorical": ["state", "chamber"], "alpha": 10.0},
    "state_chamber_incumbency": {
        "numeric": ["incumbency_balance"], "categorical": ["state", "chamber"], "alpha": 10.0,
    },
    "portable_temporal": {
        "numeric": ["incumbency_balance", "year_center", "baseline_dem_margin", "baseline_year_interaction", "inc_year_interaction"],
        "categorical": ["chamber", "office"], "alpha": 10.0,
    },
    "full_temporal": {
        "numeric": ["incumbency_balance", "year_center", "baseline_dem_margin", "baseline_year_interaction", "inc_year_interaction"],
        "categorical": ["state", "chamber", "office"], "alpha": 10.0,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["year_center"] = out["year"] - 2002
    out["baseline_year_interaction"] = out["baseline_dem_margin"] * out["year_center"] / 10
    out["inc_year_interaction"] = out["incumbency_balance"] * out["year_center"] / 10
    out["gap"] = out["legislative_dem_margin"] - out["baseline_dem_margin"]
    return out


def fit_estimator(train: pd.DataFrame, spec: dict[str, object]) -> tuple[Pipeline, list[str]]:
    numeric = list(spec["numeric"])
    categorical = list(spec["categorical"])
    transformers = []
    if numeric:
        transformers.append(("numeric", StandardScaler(), numeric))
    if categorical:
        transformers.append(("categorical", OneHotEncoder(handle_unknown="ignore"), categorical))
    model = Pipeline([
        ("features", ColumnTransformer(transformers, remainder="drop")),
        ("ridge", Ridge(alpha=float(spec["alpha"]))),
    ])
    columns = numeric + categorical
    model.fit(train[columns], train["gap"])
    return model, columns


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, spec: dict[str, object]) -> np.ndarray:
    if spec.get("kind") == "baseline":
        return np.zeros(len(test))
    if spec.get("kind") == "mean":
        return np.repeat(train["gap"].mean(), len(test))
    model, columns = fit_estimator(train, spec)
    return model.predict(test[columns])


def prediction_rows(train: pd.DataFrame, test: pd.DataFrame, model_name: str, fold_type: str, fold: str) -> pd.DataFrame:
    predicted_gap = fit_predict(train, test, MODEL_SPECS[model_name])
    out = test[KEYS + ["dem_candidate", "rep_candidate", "baseline_allocation_quality",
                       "baseline_dem_margin", "legislative_dem_margin", "incumbency_balance"]].copy()
    out["model"] = model_name
    out["fold_type"] = fold_type
    out["fold"] = str(fold)
    out["train_rows"] = len(train)
    out["predicted_gap"] = predicted_gap
    out["predicted_dem_margin"] = out["baseline_dem_margin"] + out["predicted_gap"]
    out["residual"] = out["legislative_dem_margin"] - out["predicted_dem_margin"]
    out["correct_winner"] = (out["predicted_dem_margin"] > 0) == (out["legislative_dem_margin"] > 0)
    return out


def cross_validated_predictions(data: pd.DataFrame) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    years = sorted(data["year"].unique())
    for year in years:
        train, test = data.loc[data["year"] < year], data.loc[data["year"] == year]
        if train["year"].nunique() < 2 or len(train) < 200:
            continue
        for model_name in MODEL_SPECS:
            outputs.append(prediction_rows(train, test, model_name, "forward_year", str(year)))
    for state in sorted(data["state"].unique()):
        train, test = data.loc[data["state"] != state], data.loc[data["state"] == state]
        for model_name in MODEL_SPECS:
            outputs.append(prediction_rows(train, test, model_name, "leave_state_out", state))
    return pd.concat(outputs, ignore_index=True)


def metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, fold_type, fold), group in predictions.groupby(["model", "fold_type", "fold"]):
        error = group["residual"]
        rows.append({
            "model": model, "fold_type": fold_type, "fold": fold, "rows": len(group),
            "mae": error.abs().mean(), "rmse": np.sqrt(np.mean(error**2)),
            "bias": error.mean(), "winner_accuracy": group["correct_winner"].mean(),
            "whole_precinct_rmse": np.sqrt(np.mean(error[group["baseline_allocation_quality"].eq("whole_precincts")] ** 2))
            if group["baseline_allocation_quality"].eq("whole_precincts").any() else np.nan,
        })
    return pd.DataFrame(rows)


def summarize(metric_frame: pd.DataFrame) -> pd.DataFrame:
    summary = metric_frame.groupby(["model", "fold_type"], as_index=False).agg(
        folds=("fold", "nunique"), rows=("rows", "sum"), mean_mae=("mae", "mean"),
        mean_rmse=("rmse", "mean"), mean_bias=("bias", "mean"),
        mean_winner_accuracy=("winner_accuracy", "mean"),
        mean_whole_precinct_rmse=("whole_precinct_rmse", "mean"),
    )
    wide = summary.pivot(index="model", columns="fold_type", values="mean_rmse")
    sensitivity = summary.pivot(index="model", columns="fold_type", values="mean_whole_precinct_rmse")
    ranking = pd.DataFrame(index=wide.index)
    ranking["forward_rmse"] = wide.get("forward_year")
    ranking["leave_state_out_rmse"] = wide.get("leave_state_out")
    ranking["leave_state_out_whole_precinct_rmse"] = sensitivity.get("leave_state_out")
    for column in ranking.columns:
        ranking[f"{column}_rank"] = ranking[column].rank(method="min")
    ranking["rank_sum"] = ranking.filter(like="_rank").sum(axis=1)
    complexity = {name: index for index, name in enumerate(MODEL_SPECS)}
    ranking["complexity_order"] = ranking.index.map(complexity)
    best_forward = ranking["forward_rmse"].min()
    ranking["forward_guardrail_pass"] = ranking["forward_rmse"].le(best_forward + 1.0)
    ranking = ranking.reset_index().sort_values(
        ["forward_guardrail_pass", "leave_state_out_rmse", "leave_state_out_whole_precinct_rmse", "complexity_order"],
        ascending=[False, True, True, True],
    )
    ranking["selected"] = False
    ranking.loc[ranking.index[0], "selected"] = True
    return summary, ranking


def selected_model_effects(data: pd.DataFrame, selected: str) -> pd.DataFrame:
    spec = MODEL_SPECS[selected]
    if spec.get("kind") in {"baseline", "mean"}:
        return pd.DataFrame([{"model": selected, "dem_incumbent_effect": 0.0,
                              "rep_incumbent_effect": 0.0, "two_year_time_effect": 0.0,
                              "ten_point_baseline_effect_on_gap": 0.0}])
    model, columns = fit_estimator(data, spec)

    def predict(changed: pd.DataFrame) -> np.ndarray:
        return model.predict(changed[columns])

    neutral = data.copy()
    neutral["incumbency_balance"] = 0.0
    neutral["inc_year_interaction"] = 0.0
    dem_inc = neutral.copy(); dem_inc["incumbency_balance"] = 1.0
    dem_inc["inc_year_interaction"] = dem_inc["year_center"] / 10
    rep_inc = neutral.copy(); rep_inc["incumbency_balance"] = -1.0
    rep_inc["inc_year_interaction"] = -rep_inc["year_center"] / 10
    future = data.copy(); future["year_center"] = future["year_center"] + 2
    future["baseline_year_interaction"] = future["baseline_dem_margin"] * future["year_center"] / 10
    future["inc_year_interaction"] = future["incumbency_balance"] * future["year_center"] / 10
    shifted = data.copy(); shifted["baseline_dem_margin"] = shifted["baseline_dem_margin"] + 10
    shifted["baseline_year_interaction"] = shifted["baseline_dem_margin"] * shifted["year_center"] / 10
    neutral_prediction = predict(neutral)
    return pd.DataFrame([{
        "model": selected,
        "dem_incumbent_effect": float(np.mean(predict(dem_inc) - neutral_prediction)),
        "rep_incumbent_effect": float(np.mean(predict(rep_inc) - neutral_prediction)),
        "two_year_time_effect": float(np.mean(predict(future) - predict(data))),
        "ten_point_baseline_effect_on_gap": float(np.mean(predict(shifted) - predict(data))),
    }])


def candidate_residuals(data: pd.DataFrame, predictions: pd.DataFrame, selected: str) -> pd.DataFrame:
    race = predictions.loc[
        predictions["model"].eq(selected) & predictions["fold_type"].eq("leave_state_out")
    ].copy()
    records = []
    for party, candidate_column, sign in (("D", "dem_candidate", 1), ("R", "rep_candidate", -1)):
        part = race.copy()
        part["party"] = party
        part["candidate"] = part[candidate_column]
        part["candidate_quality_residual"] = sign * part["residual"]
        part["candidate_actual_margin"] = sign * part["legislative_dem_margin"]
        part["candidate_expected_margin"] = sign * part["predicted_dem_margin"]
        records.append(part[KEYS + ["party", "candidate", "candidate_actual_margin", "candidate_expected_margin",
                                    "candidate_quality_residual", "model", "fold_type", "fold",
                                    "baseline_allocation_quality", "incumbency_balance"]])
    return pd.concat(records, ignore_index=True).sort_values(KEYS + ["party"])


def build(panel_path: Path, panel_manifest: Path, output: Path) -> dict[str, object]:
    panel_path, panel_manifest, output = panel_path.resolve(), panel_manifest.resolve(), output.resolve()
    data = add_features(pd.read_csv(panel_path, low_memory=False))
    data = data.loc[data["model_eligible"].eq(True)].copy().sort_values(KEYS).reset_index(drop=True)
    predictions = cross_validated_predictions(data)
    metric_frame = metrics(predictions)
    summary, ranking = summarize(metric_frame)
    selected = ranking.loc[ranking["selected"], "model"].iloc[0]
    candidates = candidate_residuals(data, predictions, selected)
    effects = selected_model_effects(data, selected)

    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "predictions": output / "historical_southern_cmo_predictions.csv",
        "metrics": output / "historical_southern_cmo_metrics.csv",
        "summary": output / "historical_southern_cmo_summary.csv",
        "ranking": output / "historical_southern_cmo_ranking.csv",
        "candidates": output / "historical_southern_cmo_candidate_residuals.csv",
        "effects": output / "historical_southern_cmo_selected_effects.csv",
    }
    predictions.sort_values(["fold_type", "model"] + KEYS).to_csv(paths["predictions"], index=False)
    metric_frame.sort_values(["fold_type", "model", "fold"]).to_csv(paths["metrics"], index=False)
    summary.sort_values(["fold_type", "model"]).to_csv(paths["summary"], index=False)
    ranking.to_csv(paths["ranking"], index=False)
    candidates.to_csv(paths["candidates"], index=False)
    effects.to_csv(paths["effects"], index=False)

    script_path = Path(__file__).resolve()
    manifest = {
        "schema_version": 1,
        "build_id": hashlib.sha256(f"{sha256(panel_manifest)}:{sha256(script_path)}".encode()).hexdigest()[:20],
        "code_commit": git_commit(), "pipeline": display_path(script_path),
        "input": {"path": display_path(panel_path), "sha256": sha256(panel_path),
                  "manifest_path": display_path(panel_manifest), "manifest_sha256": sha256(panel_manifest)},
        "configuration": {"models": MODEL_SPECS, "strict_model_eligible_only": True,
                          "forward_minimum_prior_cycles": 2,
                          "selection": "lowest leave-state-out RMSE among models within 1 point of best forward RMSE; whole-precinct LOSO and simplicity break ties"},
        "selected_model": selected,
        "row_counts": {"input": len(data), "predictions": len(predictions), "candidate_residuals": len(candidates)},
        "outputs": [{"name": name, "path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
                    for name, path in paths.items()],
    }
    manifest_path = output / "historical_southern_cmo_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"input_rows": len(data), "prediction_rows": len(predictions), "selected_model": selected,
            "candidate_rows": len(candidates)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--panel-manifest", type=Path, default=PANEL_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    counts = build(args.panel, args.panel_manifest, args.output)
    print("Historical Southern CMO tournament:", ", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
