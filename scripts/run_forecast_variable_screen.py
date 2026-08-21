"""Leakage-aware first-stage screening of variables for the legislative forecast.

This is a model-selection research artifact, not a headline forecast builder.
Every prediction for cycle t is trained only on cycles earlier than t. The two
political-break specifications are prespecified assumptions: Alabama data
cannot learn a new regime before its first election has occurred.
"""
from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from run_forecast_experiment_tournament import prepare_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "war"
SEED = 20260817

# All fields below are known before the election. Same-cycle federal and state
# vote margins are deliberately excluded even though they are useful CMO
# baselines and retrospective diagnostics.
GROUPS = {
    "incumbency": ["dem_incumbent_i", "rep_incumbent_i", "open_seat"],
    "candidate_history": [
        "dem_prior_recent", "rep_prior_recent", "dem_prior_winner", "rep_prior_winner",
        "dem_prior_candidate_overperformance", "rep_prior_candidate_overperformance",
        "dem_prior_cycle_gap", "rep_prior_cycle_gap",
    ],
    "demographics": ["nonwhite_share", "white_college_share"],
    "presidential_trend": ["prior_pres_swing_filled", "trend_available"],
    "fundraising": ["finance_ratio_capped", "ftm_finance_complete"],
}


def add_regime_baselines(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    prior = data["prior_pres_dem_margin"]
    swing = data["national_environment_swing"]
    # Election cycles are even midterms, hence the post-election break dates
    # first appear in the 2010 and 2018 observations.
    data["baseline_no_environment"] = prior
    data["baseline_uniform_environment"] = prior + swing
    data["baseline_post2008_step"] = prior + swing * data.cycle.ge(2010)
    data["baseline_post2016_step"] = prior + swing * data.cycle.ge(2018)
    data["baseline_two_step_environment"] = prior + swing * np.select(
        [data.cycle.ge(2018), data.cycle.ge(2010)], [1.0, 0.5], default=0.0)
    return data


def cycle_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.cycle.value_counts()
    return frame.cycle.map(lambda value: 1.0 / counts.loc[value]).to_numpy()


def ridge() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", Ridge(alpha=20.0)),
    ])


def regime_screen(data: pd.DataFrame) -> pd.DataFrame:
    baselines = [
        "baseline_no_environment", "baseline_uniform_environment",
        "baseline_post2008_step", "baseline_post2016_step",
        "baseline_two_step_environment",
    ]
    rows = []
    for cycle in sorted(data.cycle.unique())[1:]:
        test = data[data.cycle.eq(cycle)]
        for baseline in baselines:
            use = test.dropna(subset=[baseline, "legislative_dem_margin"])
            for chamber, group in [("all", use), *list(use.groupby("chamber"))]:
                if group.empty:
                    continue
                rows.append({
                    "test_cycle": cycle, "chamber": chamber,
                    "specification": baseline.removeprefix("baseline_"), "races": len(group),
                    "mae": mean_absolute_error(group.legislative_dem_margin, group[baseline]),
                    "bias": float((group.legislative_dem_margin - group[baseline]).mean()),
                })
    return pd.DataFrame(rows)


def variable_screen(data: pd.DataFrame) -> pd.DataFrame:
    """Add each group to the best-supported prespecified regime baseline."""
    rows = []
    cycles = sorted(data.cycle.unique())
    specifications = {"environment_baseline": []} | GROUPS
    for cycle in cycles[1:]:
        train = data[data.cycle.lt(cycle)].dropna(
            subset=["baseline_post2016_step", "legislative_dem_margin"])
        test = data[data.cycle.eq(cycle)].dropna(
            subset=["baseline_post2016_step", "legislative_dem_margin"])
        for name, features in specifications.items():
            prediction = test.baseline_post2016_step.to_numpy(copy=True)
            if features:
                model = ridge()
                target = train.legislative_dem_margin - train.baseline_post2016_step
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(train[features], target, model__sample_weight=cycle_weights(train))
                prediction += model.predict(test[features])
            for race, pred in zip(test.itertuples(), prediction):
                rows.append({
                    "test_cycle": cycle, "chamber": race.chamber, "district": race.district,
                    "specification": name, "actual": race.legislative_dem_margin,
                    "prediction": pred, "error": race.legislative_dem_margin - pred,
                })
    result = pd.DataFrame(rows)
    result["absolute_error"] = result.error.abs()
    return result


def bootstrap_delta(values: pd.DataFrame, repetitions: int = 5000) -> tuple[float, float]:
    """Cycle-block bootstrap interval for candidate-minus-baseline MAE."""
    rng = np.random.default_rng(SEED)
    cycles = values.test_cycle.unique()
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(cycles, len(cycles), replace=True)
        draws.append(np.mean([values.loc[values.test_cycle.eq(c), "delta_mae"].iloc[0] for c in sampled]))
    return tuple(np.quantile(draws, [0.025, 0.975]))


def summarize(predictions: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
    cycle = (predictions.groupby(["specification", "test_cycle"], as_index=False)
             .absolute_error.mean().rename(columns={"absolute_error": "mae"}))
    base = (cycle[cycle.specification.eq("environment_baseline")]
            .set_index("test_cycle").mae)
    rows = []
    for name, group in cycle.groupby("specification"):
        paired = group.copy()
        paired["delta_mae"] = paired.mae - paired.test_cycle.map(base)
        low, high = bootstrap_delta(paired)
        detail = predictions[predictions.specification.eq(name)]
        house = detail[detail.chamber.eq("house")].absolute_error.mean()
        senate = detail[detail.chamber.eq("senate")].absolute_error.mean()
        recent = paired[paired.test_cycle.ge(2018)].delta_mae.mean()
        latest = paired.loc[paired.test_cycle.eq(paired.test_cycle.max()), "delta_mae"].mean()
        features = GROUPS.get(name, [])
        availability = float(data[features].notna().all(axis=1).mean()) if features else 1.0
        # Screening, not automatic publication: require average, recent, and
        # latest gains, reasonable coverage, and no cycle-bootstrap evidence of harm.
        promoted = bool(name != "environment_baseline" and paired.delta_mae.mean() < 0 and
                        recent < 0 and latest < 0 and availability >= 0.75 and high <= 0)
        rows.append({
            "specification": name, "features": ";".join(features),
            "forward_cycles": paired.test_cycle.nunique(), "races": len(detail),
            "cycle_balanced_mean_mae": paired.mae.mean(),
            "delta_mae_vs_environment": paired.delta_mae.mean(),
            "delta_mae_ci95_low": low, "delta_mae_ci95_high": high,
            "post2016_delta_mae": recent, "latest_cycle_delta_mae": latest,
            "house_race_weighted_mae": house, "senate_race_weighted_mae": senate,
            "complete_case_share": availability, "passes_screen": promoted,
        })
    return pd.DataFrame(rows).sort_values("cycle_balanced_mean_mae")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = add_regime_baselines(prepare_data())
    regimes = regime_screen(data)
    predictions = variable_screen(data)
    summary = summarize(predictions, data)
    regimes.to_csv(OUT / "forecast_variable_regime_backtest.csv", index=False)
    predictions.to_csv(OUT / "forecast_variable_predictions.csv", index=False)
    summary.to_csv(OUT / "forecast_variable_screen_summary.csv", index=False)
    assert set(data.cycle.unique()) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert predictions.groupby("test_cycle").size().gt(0).all()
    print("Environment regime MAE (all chambers)")
    print(regimes[regimes.chamber.eq("all")].pivot(
        index="test_cycle", columns="specification", values="mae").round(2).to_string())
    print("\nVariable screen")
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
