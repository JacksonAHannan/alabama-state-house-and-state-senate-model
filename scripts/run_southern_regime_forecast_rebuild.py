#!/usr/bin/env python3
"""Tournament regime-aware Southern expected-margin models for 2026."""
from __future__ import annotations

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

from run_forecast_experiment_tournament import prepare_prospective_data


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
CAL = ROOT / "data/processed/forecast_calibration"
HISTORICAL = CAL / "historical_southern_extended_v2_panel.csv"
RECENT = CAL / "southern_legislative_probability_panel.csv"
KEYS = ["state", "year", "chamber", "district"]
SPECS = {
    "baseline_only": {"kind": "zero", "training": "all"},
    "pooled_recent": {"kind": "mean", "training": "recent"},
    "ridge_all_era": {"kind": "ridge", "training": "all", "half_life": None},
    "ridge_half_life_8": {"kind": "ridge", "training": "all", "half_life": 8.0},
    "ridge_half_life_4": {"kind": "ridge", "training": "all", "half_life": 4.0},
    "ridge_recent_only": {"kind": "ridge", "training": "recent", "half_life": None},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalized_panel() -> pd.DataFrame:
    historical = pd.read_csv(HISTORICAL, low_memory=False)
    historical = historical.loc[historical.model_eligible.eq(True)].copy()
    historical = historical.assign(
        actual_dem_margin=historical.legislative_dem_margin,
        environment_baseline_margin=historical.baseline_dem_margin,
        source_era="historical_1994_2016",
    )
    recent = pd.read_csv(RECENT, low_memory=False)
    recent = recent.loc[recent.primary_calibration_eligible.astype(bool)].copy()
    recent["chamber"] = recent.chamber.map({"lower": "house", "upper": "senate"}).fillna(recent.chamber)
    recent = recent.assign(actual_dem_margin=recent.dem_margin, source_era="recent_2018_2024")
    columns = KEYS + ["actual_dem_margin", "environment_baseline_margin",
                      "incumbency_balance", "source_era"]
    panel = pd.concat([historical[columns], recent[columns]], ignore_index=True)
    panel["gap"] = panel.actual_dem_margin - panel.environment_baseline_margin
    # Preserve missing 2024 incumbency as missing. The regime tournament does
    # not use that feature until a complete recent label set is available.
    panel = panel.dropna(subset=["actual_dem_margin", "environment_baseline_margin"])
    panel = panel.sort_values(KEYS).reset_index(drop=True)
    if panel.duplicated(KEYS).any():
        raise ValueError("Duplicate normalized race keys")
    return panel


def cell_balanced_weights(frame: pd.DataFrame, half_life: float | None) -> np.ndarray:
    keys = list(zip(frame.state, frame.year, frame.chamber))
    counts = pd.Series(keys).value_counts()
    weights = np.array([1 / counts[key] for key in keys], dtype=float)
    if half_life is not None:
        age = frame.year.max() - frame.year.to_numpy(dtype=float)
        weights *= np.power(0.5, age / half_life)
    return weights / weights.mean()


def ridge_pipeline() -> Pipeline:
    features = ColumnTransformer([
        ("numeric", StandardScaler(), ["environment_baseline_margin"]),
        ("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]),
    ])
    return Pipeline([("features", features), ("ridge", Ridge(alpha=10.0))])


def training_rows(panel: pd.DataFrame, test_year: int, spec: dict) -> pd.DataFrame:
    train = panel.loc[panel.year.lt(test_year)].copy()
    if spec["training"] == "recent":
        train = train.loc[train.year.ge(2018)].copy()
    return train


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, spec: dict) -> np.ndarray:
    if spec["kind"] == "zero":
        return np.zeros(len(test))
    if train.empty:
        raise ValueError("No eligible training rows")
    weights = cell_balanced_weights(train, spec.get("half_life"))
    if spec["kind"] == "mean":
        return np.repeat(np.average(train.gap, weights=weights), len(test))
    model = ridge_pipeline()
    model.fit(train, train.gap, ridge__sample_weight=weights)
    return model.predict(test)


def forward_predictions(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in (2018, 2020, 2022, 2024):
        test = panel.loc[panel.year.eq(year)]
        for name, spec in SPECS.items():
            train = training_rows(panel, year, spec)
            if spec["kind"] != "zero" and len(train) < 50:
                continue
            predicted_gap = fit_predict(train, test, spec)
            for race, gap in zip(test.itertuples(), predicted_gap):
                predicted_margin = race.environment_baseline_margin + gap
                rows.append({
                    **{key: getattr(race, key) for key in KEYS},
                    "model": name, "train_rows": len(train),
                    "train_min_year": int(train.year.min()) if len(train) else np.nan,
                    "train_max_year": int(train.year.max()) if len(train) else np.nan,
                    "predicted_gap": gap, "predicted_dem_margin": predicted_margin,
                    "actual_dem_margin": race.actual_dem_margin,
                    "error": race.actual_dem_margin - predicted_margin,
                })
    return pd.DataFrame(rows)


def rank_models(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    recent = predictions.loc[predictions.year.isin([2020, 2022, 2024])].copy()
    metrics = (recent.groupby(["model", "year"], as_index=False)
               .agg(races=("district", "size"), mae=("error", lambda x: x.abs().mean()),
                    rmse=("error", lambda x: np.sqrt(np.mean(x ** 2))), bias=("error", "mean")))
    complete = metrics.groupby("model").year.nunique().loc[lambda x: x.eq(3)].index
    metrics = metrics.loc[metrics.model.isin(complete)].copy()
    baseline = metrics.loc[metrics.model.eq("baseline_only")].set_index("year").mae
    rows = []
    for model, group in metrics.groupby("model"):
        group = group.sort_values("year")
        delta = group.mae - group.year.map(baseline)
        rows.append({
            "model": model, "mean_mae_2020_2024": group.mae.mean(),
            "mean_rmse_2020_2024": group.rmse.mean(), "mean_delta_vs_baseline": delta.mean(),
            "latest_2024_mae": group.loc[group.year.eq(2024), "mae"].iloc[0],
            "latest_2024_delta": delta.loc[group.year.eq(2024)].iloc[0],
            "worst_cycle_delta": delta.max(), "cycles_improved": int(delta.lt(0).sum()),
        })
    ranking = pd.DataFrame(rows)
    ranking["guardrail_pass"] = (
        ranking.model.ne("baseline_only")
        & ranking.mean_delta_vs_baseline.lt(0)
        & ranking.latest_2024_delta.le(0)
        & ranking.worst_cycle_delta.le(2.0)
        & ranking.cycles_improved.ge(2)
    )
    eligible = ranking.loc[ranking.guardrail_pass]
    selected = (eligible.sort_values(["mean_mae_2020_2024", "model"]).iloc[0].model
                if not eligible.empty else "baseline_only")
    ranking["selected"] = ranking.model.eq(selected)
    return metrics, ranking.sort_values(["selected", "mean_mae_2020_2024"], ascending=[False, True])


def prospective(panel: pd.DataFrame, selected: str) -> pd.DataFrame:
    source = prepare_prospective_data().copy()
    source["state"] = "AL"
    source["year"] = 2026
    source["environment_baseline_margin"] = source.national_environment_baseline
    source["incumbency_balance"] = source.dem_incumbent_i - source.rep_incumbent_i
    spec = SPECS[selected]
    train = training_rows(panel, 2026, spec)
    adjustment = fit_predict(train, source, spec)
    records = []
    for weight, view in ((0.2, "basic"), (1.0, "fundamentals_plus")):
        frame = source[["chamber", "district", "environment_baseline_margin", "incumbency_balance"]].copy()
        frame["forecast_view"] = view
        frame["selected_model"] = selected
        frame["full_expected_gap"] = adjustment
        frame["applied_gap_weight"] = weight
        frame["applied_gap_adjustment"] = weight * adjustment
        frame["predicted_dem_margin"] = frame.environment_baseline_margin + frame.applied_gap_adjustment
        records.append(frame)
    return pd.concat(records, ignore_index=True).sort_values(["forecast_view", "chamber", "district"])


def main() -> None:
    panel = normalized_panel()
    predictions = forward_predictions(panel)
    metrics, ranking = rank_models(predictions)
    selected = ranking.loc[ranking.selected, "model"].iloc[0]
    forecast = prospective(panel, selected)
    outputs = {
        "forecast_regime_v1_panel.csv": panel,
        "forecast_regime_v1_predictions.csv": predictions,
        "forecast_regime_v1_metrics.csv": metrics,
        "forecast_regime_v1_ranking.csv": ranking,
        "forecast_regime_v1_2026.csv": forecast,
    }
    for name, frame in outputs.items():
        frame.to_csv(WAR / name, index=False)
    script = Path(__file__).resolve()
    manifest = {
        "schema_version": 1, "status": "research_candidate", "code_commit": git_commit(),
        "selected_model": selected, "selection_years": [2020, 2022, 2024], "models": SPECS,
        "inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
                   for path in (HISTORICAL, RECENT)],
        "outputs": [{"path": f"data/processed/war/{name}", "rows": len(frame),
                     "sha256": sha256(WAR / name)} for name, frame in outputs.items()],
    }
    manifest["build_id"] = hashlib.sha256(
        (json.dumps(manifest, sort_keys=True) + sha256(script)).encode()).hexdigest()[:20]
    (WAR / "forecast_regime_v1_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Regime forecast rebuild: panel={len(panel)}, selected={selected}, build={manifest['build_id']}")
    print(ranking.to_string(index=False))


if __name__ == "__main__":
    main()
