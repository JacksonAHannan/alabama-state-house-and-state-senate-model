"""Build a recent-era probability calibrator for Alabama's 2026 margins.

The margin forecast and the probability calibration are deliberately separate.
This script asks a narrow question: given a genuinely out-of-sample expected
Democratic margin, how often did the Democrat win? It uses Southern legislative
races, compares simple zero-centered error distributions in forward-cycle and
leave-state-out tests, and applies the selected distribution to both published
Alabama margin views.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, ndtr
from scipy.stats import t as student_t
from sklearn.metrics import brier_score_loss, log_loss


ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "data" / "processed" / "forecast_calibration"
WAR = ROOT / "data" / "processed" / "war"
SEED = 20260819
EPS = 1e-6


FAMILIES = ("normal", "logistic", "student_t")


def candidate_specs(family: str | None = None) -> list[dict]:
    specs = []
    for scale in np.arange(3.0, 16.01, 0.25):
        specs.append({"family": "normal", "scale": float(scale), "df": np.nan})
    for scale in np.arange(2.0, 12.01, 0.25):
        specs.append({"family": "logistic", "scale": float(scale), "df": np.nan})
    for df in (3, 5, 8, 12):
        for scale in np.arange(2.0, 14.01, 0.25):
            specs.append({"family": "student_t", "scale": float(scale), "df": float(df)})
    return [s for s in specs if family is None or s["family"] == family]


def probability(margin: np.ndarray, spec: dict) -> np.ndarray:
    z = np.asarray(margin, dtype=float) / float(spec["scale"])
    if spec["family"] == "normal":
        p = ndtr(z)
    elif spec["family"] == "logistic":
        p = expit(z)
    elif spec["family"] == "student_t":
        p = student_t.cdf(z, df=float(spec["df"]))
    else:
        raise ValueError(spec["family"])
    return np.clip(p, EPS, 1 - EPS)


def balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    """Give every state-cycle-chamber cell equal total fitting weight."""
    keys = list(zip(frame.state, frame.year, frame.chamber))
    counts = pd.Series(keys).value_counts()
    raw = np.array([1 / counts[k] for k in keys], dtype=float)
    return raw / raw.mean()


def fit_spec(train: pd.DataFrame, family: str | None = None) -> dict:
    y = train.dem_win.to_numpy(dtype=float)
    margin = train.environment_baseline_margin.to_numpy(dtype=float)
    weights = balanced_weights(train)
    best = None
    for spec in candidate_specs(family):
        p = probability(margin, spec)
        score = np.average((p - y) ** 2, weights=weights)
        key = (score, 0 if spec["family"] == "normal" else 1, spec["scale"])
        if best is None or key < best[0]:
            best = (key, dict(spec, training_brier=float(score)))
    return best[1]


def metric_row(frame: pd.DataFrame) -> dict:
    y = frame.dem_win.to_numpy(dtype=int)
    p = np.clip(frame.dem_probability.to_numpy(dtype=float), EPS, 1 - EPS)
    bins = pd.qcut(p, min(10, len(p)), duplicates="drop")
    grouped = frame.assign(_bin=bins).groupby("_bin", observed=True).agg(
        predicted=("dem_probability", "mean"), observed=("dem_win", "mean")
    )
    return {
        "n": int(len(frame)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "calibration_mae": float((grouped.predicted - grouped.observed).abs().mean()),
        "winner_accuracy": float(((p >= .5).astype(int) == y).mean()),
    }


def validation_predictions(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in (2020, 2022, 2024):
        train, test = data[data.year < year], data[data.year == year]
        if train.empty or test.empty:
            continue
        for family in FAMILIES:
            spec = fit_spec(train, family)
            for race, p in zip(test.itertuples(), probability(test.environment_baseline_margin, spec)):
                rows.append({"validation": "forward_cycle", "holdout": str(year),
                             "state": race.state, "year": race.year, "chamber": race.chamber,
                             "district": race.district, "expected_dem_margin": race.environment_baseline_margin,
                             "dem_win": race.dem_win, "dem_probability": p, **spec})
    for state in sorted(data.state.unique()):
        train, test = data[data.state != state], data[data.state == state]
        if train.empty or test.empty:
            continue
        for family in FAMILIES:
            spec = fit_spec(train, family)
            for race, p in zip(test.itertuples(), probability(test.environment_baseline_margin, spec)):
                rows.append({"validation": "leave_state_out", "holdout": state,
                             "state": race.state, "year": race.year, "chamber": race.chamber,
                             "district": race.district, "expected_dem_margin": race.environment_baseline_margin,
                             "dem_win": race.dem_win, "dem_probability": p, **spec})
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_csv(CAL / "southern_legislative_probability_panel.csv")
    data = panel[panel.primary_calibration_eligible.astype(bool)].dropna(
        subset=["environment_baseline_margin", "dem_win"]
    ).copy()
    predictions = validation_predictions(data)
    predictions.to_csv(CAL / "production_probability_validation_predictions.csv", index=False)

    metrics = []
    for keys, group in predictions.groupby(["validation", "holdout", "family"], sort=True):
        metrics.append({"validation": keys[0], "holdout": keys[1], "family": keys[2], **metric_row(group),
                        "scale": group.scale.iloc[0],
                        "df": group.df.iloc[0]})
    metric_df = pd.DataFrame(metrics)
    metric_df.to_csv(CAL / "production_probability_validation_metrics.csv", index=False)

    family_summary = (metric_df.groupby(["family", "validation"], as_index=False)
                      .agg(mean_brier=("brier", "mean"), mean_log_loss=("log_loss", "mean"),
                           mean_calibration_mae=("calibration_mae", "mean")))
    family_summary.to_csv(CAL / "production_probability_family_comparison.csv", index=False)
    scores = family_summary.groupby("family").mean_brier.mean().sort_values()
    selected_family = scores.index[0]
    # Prefer the transparent normal curve when its average validation Brier is
    # practically tied with the nominal winner.
    if scores.get("normal", np.inf) <= scores.iloc[0] + .001:
        selected_family = "normal"
    final_spec = fit_spec(data, selected_family)
    forecast = pd.read_csv(WAR / "next_forecast_tournament_2026.csv")
    labels = {
        "cmo_expectation__blend20": "basic",
        "cmo_expectation__blend100": "fundamentals_plus",
    }
    forecast = forecast[forecast.specification.isin(labels)].copy()
    forecast["forecast_view"] = forecast.specification.map(labels)
    forecast["dem_win_probability"] = probability(forecast.predicted_dem_margin, final_spec)
    forecast["rep_win_probability"] = 1 - forecast.dem_win_probability
    forecast["probability_family"] = final_spec["family"]
    forecast["probability_scale"] = final_spec["scale"]
    forecast["probability_df"] = final_spec["df"]
    forecast.to_csv(CAL / "production_probability_2026.csv", index=False)

    curve = pd.DataFrame({"expected_dem_margin": np.linspace(-50, 50, 401)})
    curve["dem_win_probability"] = probability(curve.expected_dem_margin, final_spec)
    curve["rep_win_probability"] = 1 - curve.dem_win_probability
    curve.to_csv(CAL / "production_probability_curve.csv", index=False)

    selected_metrics = metric_df[metric_df.family == selected_family]
    summary = (selected_metrics.groupby("validation", as_index=False)
               .agg(holdouts=("holdout", "nunique"), races=("n", "sum"),
                    mean_brier=("brier", "mean"), mean_log_loss=("log_loss", "mean"),
                    mean_calibration_mae=("calibration_mae", "mean"),
                    mean_winner_accuracy=("winner_accuracy", "mean")))
    summary.to_csv(CAL / "production_probability_validation_summary.csv", index=False)

    residual = data.dem_margin - data.environment_baseline_margin
    serialized_spec = {k: (None if isinstance(v, float) and np.isnan(v) else v)
                       for k, v in final_spec.items()}
    card = {
        "model_name": "Southern recent-era legislative margin probability calibrator",
        "status": "research_candidate",
        "built_date": "2026-08-19",
        "training_races": int(len(data)),
        "training_states": sorted(data.state.unique().tolist()),
        "training_cycles": sorted(int(x) for x in data.year.unique()),
        "selected_distribution": serialized_spec,
        "family_validation_comparison": family_summary.to_dict(orient="records"),
        "validation": summary.to_dict(orient="records"),
        "residual_quantiles": {str(q): float(residual.quantile(q)) for q in (.025, .10, .50, .90, .975)},
        "rules": [
            "Probability is calibrated from expected margin, not from the public Monte Carlo intervals.",
            "Distribution is zero-centered so calibration cannot silently shift the margin forecast.",
            "State-cycle-chamber cells receive equal total fitting weight.",
            "Alabama is excluded from training.",
        ],
        "known_limitations": [
            "Only recent Southern cycles with compatible district presidential baselines are eligible.",
            "Odd-year Louisiana and Mississippi files are staged but not mixed into the even-year environment calibration yet.",
            "National polling uncertainty must be modeled as a shared scenario layer, not hidden in district win probabilities.",
        ],
    }
    (CAL / "production_probability_model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")

    print("Selected:", final_spec)
    print(summary.to_string(index=False))
    print("\nHD-21")
    print(forecast[(forecast.chamber == "house") & (forecast.district == 21)][
        ["forecast_view", "predicted_dem_margin", "dem_win_probability", "rep_win_probability"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
