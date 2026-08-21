"""Audit a compact challenger library built from the improved data products.

The broad RDH tournament is exploratory. This script freezes a small candidate
set, compares every candidate on identical expanding-window predictions, and
simulates a past-only selector. It does not alter the public forecast.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
VALID = ROOT / "data" / "processed" / "elections" / "validation"
SEED = 20260817
BENCHMARK = "public_80_20_total_ridge"
SOURCE_NAMES = {
    BENCHMARK: "total_control__ridge_20__0.2",
    "full_total_ridge5": "total_control__ridge_5__1",
    "full_hybrid_cvap_ridge5": "all_hybrid__ridge_5__1",
    "stable_cvap_composition_elastic": "all_hybrid_stable_composition__elastic_30__1",
    "stable_hybrid_bayesian_35": "all_hybrid_stable__bayesian__0.35",
    "stable_hybrid_elastic10_35": "all_hybrid_stable__elastic_10__0.35",
    "stable_total_elastic10_35": "total_stable__elastic_10__0.35",
}


def compact_predictions() -> pd.DataFrame:
    raw = pd.read_csv(VALID / "rdh_demographic_model_tournament_predictions.csv")
    reverse = {value: key for key, value in SOURCE_NAMES.items() if key != BENCHMARK}
    use = raw[raw.specification.isin(reverse)].copy()
    use["specification"] = use.specification.map(reverse)
    public = pd.read_csv(WAR / "forecast_experiment_ensemble_predictions.csv")
    public = public[public.specification.eq("ensemble_ramp_ridge_80_20")][
        ["test_cycle", "chamber", "district", "actual", "prediction"]].assign(
            specification=BENCHMARK)
    use = pd.concat([use, public], ignore_index=True)
    keys = ["test_cycle", "chamber", "district", "actual"]
    wide = use.pivot(index=keys, columns="specification", values="prediction").reset_index()
    # Conservative blends let us test whether the full CVAP ridge signal should
    # be introduced gradually rather than replacing the public shrinkage at once.
    for weight in (0.25, 0.50, 0.75):
        wide[f"hybrid_cvap_blend_{int(weight*100)}"] = (
            (1 - weight) * wide[BENCHMARK] + weight * wide["full_hybrid_cvap_ridge5"])
    for weight in (0.25, 0.50):
        wide[f"stable_bayesian_blend_{int(weight*100)}"] = (
            (1 - weight) * wide[BENCHMARK] + weight * wide["stable_hybrid_bayesian_35"])
    stable_delta = wide["stable_hybrid_bayesian_35"] - wide[BENCHMARK]
    for cap in (1.0, 2.0):
        wide[f"stable_bayesian_cap_{int(cap)}"] = wide[BENCHMARK] + stable_delta.clip(-cap, cap)
    return wide.melt(id_vars=keys, var_name="specification", value_name="prediction")


def bootstrap_interval(cycle_delta: pd.Series, repetitions: int = 20000) -> tuple[float, float, float]:
    values = cycle_delta.to_numpy()
    rng = np.random.default_rng(SEED)
    draws = rng.choice(values, size=(repetitions, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(draws, .025)), float(np.quantile(draws, .975)), float((draws < 0).mean())


def summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = detail.assign(absolute_error=lambda x: (x.actual - x.prediction).abs())
    cycle = (detail.groupby(["specification", "test_cycle"], as_index=False)
             .absolute_error.mean().rename(columns={"absolute_error": "mae"}))
    baseline = cycle[cycle.specification.eq(BENCHMARK)].set_index("test_cycle").mae
    rows = []
    for name, group in cycle.groupby("specification"):
        group = group.copy()
        group["delta_vs_public"] = group.mae - group.test_cycle.map(baseline)
        low, high, probability = bootstrap_interval(group.set_index("test_cycle").delta_vs_public)
        rows.append({
            "specification": name, "forward_cycles": len(group),
            "cycle_balanced_mae": group.mae.mean(),
            "delta_mae_vs_public": group.delta_vs_public.mean(),
            "post2016_mae": group[group.test_cycle.ge(2018)].mae.mean(),
            "latest_2022_mae": group.loc[group.test_cycle.eq(2022), "mae"].iloc[0],
            "worst_cycle_delta_vs_public": group.delta_vs_public.max(),
            "cycles_improved": int(group.delta_vs_public.lt(0).sum()),
            "cycle_bootstrap_delta_low": low, "cycle_bootstrap_delta_high": high,
            "bootstrap_probability_improvement": probability,
        })
    return cycle, pd.DataFrame(rows).sort_values("cycle_balanced_mae")


def nested_selector(detail: pd.DataFrame) -> pd.DataFrame:
    """Choose a candidate for cycle t using only holdouts earlier than t."""
    detail = detail.assign(absolute_error=lambda x: (x.actual - x.prediction).abs())
    candidates = [BENCHMARK] + sorted(set(detail.specification) - {BENCHMARK})
    cycle_mae = detail.groupby(["specification", "test_cycle"]).absolute_error.mean()
    rows = []
    cycles = sorted(detail.test_cycle.unique())
    for cycle in cycles:
        prior = [value for value in cycles if value < cycle]
        if len(prior) < 2:
            selected = BENCHMARK
            reason = "benchmark_fallback_fewer_than_two_prior_holdouts"
        else:
            scores = {name: cycle_mae.loc[name].reindex(prior).mean() for name in candidates}
            selected = min(scores, key=lambda name: (scores[name], candidates.index(name)))
            reason = "lowest_mean_mae_on_prior_holdouts_only"
        value = float(cycle_mae.loc[(selected, cycle)])
        benchmark = float(cycle_mae.loc[(BENCHMARK, cycle)])
        rows.append({"test_cycle": cycle, "selected_specification": selected,
                     "selection_reason": reason, "mae": value,
                     "public_mae": benchmark, "delta_mae_vs_public": value - benchmark})
    return pd.DataFrame(rows)


def prospective_comparison() -> pd.DataFrame:
    source = pd.read_csv(WAR / "rdh_demographic_model_tournament_2026.csv")
    reverse = {value: key for key, value in SOURCE_NAMES.items() if key != BENCHMARK}
    use = source[source.specification.isin(reverse)].copy()
    use["specification"] = use.specification.map(reverse)
    public = pd.read_csv(WAR / "2026_model_comparison.csv")
    public = public[public.is_public_default][
        ["chamber", "district", "predicted_dem_margin"]].assign(specification=BENCHMARK)
    use = pd.concat([use, public], ignore_index=True)
    keys = ["chamber", "district"]
    wide = use.pivot(index=keys, columns="specification", values="predicted_dem_margin").reset_index()
    for weight in (0.25, 0.50, 0.75):
        wide[f"hybrid_cvap_blend_{int(weight*100)}"] = (
            (1 - weight) * wide[BENCHMARK] + weight * wide["full_hybrid_cvap_ridge5"])
    for weight in (0.25, 0.50):
        wide[f"stable_bayesian_blend_{int(weight*100)}"] = (
            (1 - weight) * wide[BENCHMARK] + weight * wide["stable_hybrid_bayesian_35"])
    stable_delta = wide["stable_hybrid_bayesian_35"] - wide[BENCHMARK]
    for cap in (1.0, 2.0):
        wide[f"stable_bayesian_cap_{int(cap)}"] = wide[BENCHMARK] + stable_delta.clip(-cap, cap)
    long = wide.melt(id_vars=keys, var_name="specification", value_name="predicted_dem_margin")
    public = long[long.specification.eq(BENCHMARK)][keys + ["predicted_dem_margin"]].rename(
        columns={"predicted_dem_margin": "public_margin"})
    long = long.merge(public, on=keys, validate="many_to_one")
    long["margin_change_vs_public"] = long.predicted_dem_margin - long.public_margin
    long["winner_changed_vs_public"] = ((long.predicted_dem_margin >= 0) != (long.public_margin >= 0))
    return long


def data_eligibility() -> pd.DataFrame:
    ideology = pd.read_csv(ROOT / "data" / "processed" / "ideology" /
                           "votesmart_pct_cmo_race_features.csv")
    finance = pd.read_csv(WAR / "fcpa_fundraising_experiment_panel.csv")
    rows = [{"data_family": "cycle_matched_cvap", "forecast_eligible": True,
             "historical_cycles": "2010;2014;2018;2022", "prospective_2026": True,
             "decision": "included_in_challenger_library"},
            {"data_family": "reviewed_fcpa_fundraising", "forecast_eligible": True,
             "historical_cycles": ";".join(map(str, sorted(finance.cycle.unique()))),
             "prospective_2026": True,
             "decision": "full_zero_policy_panel_available_short_history"},
            {"data_family": "votesmart_candidate_ideology", "forecast_eligible": False,
             "historical_cycles": ";".join(map(str, sorted(ideology.cycle.unique()))),
             "prospective_2026": False,
             "decision": "excluded_no_2022_or_2026_candidate_coverage"}]
    return pd.DataFrame(rows)


def main() -> None:
    detail = compact_predictions()
    cycle, summary = summarize(detail)
    nested = nested_selector(detail)
    prospective = prospective_comparison()
    prospective_audit = (prospective.groupby("specification", as_index=False)
        .agg(mean_2026_change=("margin_change_vs_public", "mean"),
             mean_absolute_2026_change=("margin_change_vs_public", lambda value: value.abs().mean()),
             max_absolute_2026_change=("margin_change_vs_public", lambda value: value.abs().max()),
             winner_changes_2026=("winner_changed_vs_public", "sum")))
    sd2 = (prospective[(prospective.chamber.eq("senate")) & prospective.district.eq(2)]
           [["specification", "predicted_dem_margin"]]
           .rename(columns={"predicted_dem_margin": "sd2_2026_margin"}))
    summary = summary.merge(prospective_audit, on="specification", validate="one_to_one").merge(
        sd2, on="specification", validate="one_to_one")
    summary["prospective_smell_test_pass"] = (
        summary.sd2_2026_margin.ge(0) & summary.max_absolute_2026_change.le(10))
    eligibility = data_eligibility()
    detail.to_csv(WAR / "forecast_challenger_predictions.csv", index=False)
    cycle.to_csv(WAR / "forecast_challenger_cycle_metrics.csv", index=False)
    summary.to_csv(WAR / "forecast_challenger_summary.csv", index=False)
    nested.to_csv(WAR / "forecast_challenger_nested_selection.csv", index=False)
    prospective.to_csv(WAR / "forecast_challenger_2026_comparison.csv", index=False)
    eligibility.to_csv(WAR / "forecast_challenger_data_eligibility.csv", index=False)
    assert detail.groupby("specification").test_cycle.nunique().eq(7).all()
    print(summary.round(3).to_string(index=False))
    print("\nPast-only selector")
    print(nested.round(3).to_string(index=False))
    print("\nData eligibility")
    print(eligibility.to_string(index=False))


if __name__ == "__main__":
    main()
