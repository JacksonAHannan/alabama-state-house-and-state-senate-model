"""Backtest national generic-ballot transfers into Alabama CES estimates.

This is an experimental validation layer, not a production forecast. For a
target election t, every forecast starts with CES estimates from t-2 and a
YouGov snapshot observed before election t. No target-election CES outcome is
used until the forecast has been generated.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POLLING = ROOT / "data" / "processed" / "polling"
EPSILON = 0.01


def logit(value: float) -> float:
    value = float(np.clip(value, EPSILON, 1 - EPSILON))
    return float(np.log(value / (1 - value)))


def inv_logit(value: float) -> float:
    return float(1 / (1 + np.exp(-value)))


def fit_pooled_beta(history: pd.DataFrame, prior_strength: float = 4.0) -> float:
    """Fit one transfer coefficient, shrunk toward unit transfer."""
    if history.empty:
        return 1.0
    valid = history.dropna(subset=["national_signal_logit", "actual_change_logit"])
    if valid.empty:
        return 1.0
    x = valid.national_signal_logit.to_numpy()
    y = valid.actual_change_logit.to_numpy()
    weights = np.sqrt(valid.effective_n_actual.clip(lower=1).to_numpy())
    numerator = np.sum(weights * x * y) + prior_strength
    denominator = np.sum(weights * x * x) + prior_strength
    return float(np.clip(numerator / denominator, -0.5, 2.0))


def prepare_inputs(ces: pd.DataFrame, polls: pd.DataFrame) -> pd.DataFrame:
    ces = ces[ces.weight_method == "year_specific_weight"].copy()
    key = ["year", "dimension", "group"]
    al = ces[ces.geography == "alabama"].rename(columns={
        "dem_two_party_share": "al_share", "effective_n": "al_effective_n",
    })[key + ["al_share", "al_effective_n"]]
    national = ces[ces.geography == "rest_us"].rename(columns={
        "dem_two_party_share": "national_share",
    })[key + ["national_share"]]
    ces_wide = al.merge(national, on=key, validate="one_to_one")
    polls = polls.rename(columns={"cycle": "year", "dem_two_party_share": "poll_share"})
    return ces_wide.merge(polls[key + ["poll_share"]], on=key, how="left", validate="one_to_one")


def backtest(inputs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    history: list[dict] = []
    for target_year in [2018, 2020, 2022, 2024]:
        prior = inputs[inputs.year == target_year - 2].set_index(["dimension", "group"])
        target = inputs[inputs.year == target_year].set_index(["dimension", "group"])
        common = prior.index.intersection(target.index)
        beta = fit_pooled_beta(pd.DataFrame(history)) if history else 1.0
        overall_prior_us = prior.loc[("overall", "all"), "national_share"]
        overall_poll = target.loc[("overall", "all"), "poll_share"]
        uniform_signal = logit(overall_poll) - logit(overall_prior_us)
        for dimension, group in common:
            old = prior.loc[(dimension, group)]
            current = target.loc[(dimension, group)]
            if pd.isna(current.poll_share):
                continue
            signal = logit(current.poll_share) - logit(old.national_share)
            old_al_logit = logit(old.al_share)
            actual_logit = logit(current.al_share)
            forecasts = {
                "carry_forward": old.al_share,
                "uniform_national_swing": inv_logit(old_al_logit + uniform_signal),
                "demographic_unit_transfer": inv_logit(old_al_logit + signal),
                "demographic_pooled_transfer": inv_logit(old_al_logit + beta * signal),
            }
            for method, forecast in forecasts.items():
                rows.append({
                    "target_year": target_year, "prior_year": target_year - 2,
                    "dimension": dimension, "group": group, "method": method,
                    "pooled_beta": beta, "forecast_dem_share": forecast,
                    "actual_dem_share": current.al_share,
                    "error_points": 100 * (forecast - current.al_share),
                    "absolute_error_points": 100 * abs(forecast - current.al_share),
                    "effective_n_actual": current.al_effective_n,
                    "national_signal_logit": signal,
                })
            history.append({
                "national_signal_logit": signal,
                "actual_change_logit": actual_logit - old_al_logit,
                "effective_n_actual": current.al_effective_n,
            })
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    for keys, group in results.groupby(["method", "target_year"], sort=True):
        weights = group.effective_n_actual.clip(lower=1)
        summaries.append({
            "method": keys[0], "target_year": keys[1], "groups": len(group),
            "weighted_mae_points": float(np.average(group.absolute_error_points, weights=weights)),
            "median_ae_points": float(group.absolute_error_points.median()),
        })
    result = pd.DataFrame(summaries)
    all_years = []
    for method, group in results.groupby("method", sort=True):
        weights = group.effective_n_actual.clip(lower=1)
        all_years.append({
            "method": method, "target_year": "all", "groups": len(group),
            "weighted_mae_points": float(np.average(group.absolute_error_points, weights=weights)),
            "median_ae_points": float(group.absolute_error_points.median()),
        })
    return pd.concat([result, pd.DataFrame(all_years)], ignore_index=True)


def main() -> None:
    ces = pd.read_csv(POLLING / "ces_house_vote_demographics.csv")
    polls = pd.read_csv(POLLING / "yougov_generic_ballot_election_snapshots.csv")
    inputs = prepare_inputs(ces, polls)
    results = backtest(inputs)
    summary = summarize(results)
    results.to_csv(POLLING / "ces_yougov_transfer_backtest.csv", index=False)
    summary.to_csv(POLLING / "ces_yougov_transfer_backtest_summary.csv", index=False)
    print(summary[summary.target_year.astype(str) == "all"].to_string(index=False))


if __name__ == "__main__":
    main()
