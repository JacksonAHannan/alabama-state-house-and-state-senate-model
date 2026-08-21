"""Test Democratic social ideology against presidential/federal overperformance.

Positive ideology is conservative; positive outcomes are Democratic legislative
performance above the selected national benchmark.  Results are descriptive,
use pre-election individual evidence only, and never impute ideology by party.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
ELECTIONS = ROOT / "data" / "processed" / "elections"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
OUT = ELECTIONS / "validation"


def hc3_ols(frame: pd.DataFrame, outcome: str, controls: list[str], label: str) -> dict[str, object]:
    columns = [outcome, "social_score", *controls]
    data = frame[columns].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(data) < len(controls) + 5 or data.social_score.nunique() < 2:
        return {"outcome": outcome, "specification": label, "n": len(data)}
    pieces = [np.ones((len(data), 1)), data[["social_score"] + controls].to_numpy(float)]
    x = np.column_stack(pieces)
    y = data[outcome].to_numpy(float)
    inv = np.linalg.pinv(x.T @ x)
    beta = inv @ x.T @ y
    resid = y - x @ beta
    leverage = np.clip(np.einsum("ij,jk,ik->i", x, inv, x), 0, .999999)
    adjusted = resid / (1 - leverage)
    meat = x.T @ (x * adjusted[:, None] ** 2)
    cov = inv @ meat @ inv
    se = float(np.sqrt(max(cov[1, 1], 0)))
    dof = max(len(data) - np.linalg.matrix_rank(x), 1)
    coefficient = float(beta[1])
    p = float(2 * stats.t.sf(abs(coefficient / se), dof)) if se else np.nan
    scale = float(data.social_score.std(ddof=1))
    return {
        "outcome": outcome, "specification": label, "n": len(data),
        "cycles": "+".join(map(str, sorted(frame.loc[data.index, "cycle"].unique()))),
        "social_coefficient_full_unit": coefficient, "social_hc3_se": se,
        "social_ci_low": coefficient - stats.t.ppf(.975, dof) * se,
        "social_ci_high": coefficient + stats.t.ppf(.975, dof) * se,
        "social_p_value": p, "social_sd": scale,
        "effect_per_social_sd": coefficient * scale,
        "outcome_mean": float(data[outcome].mean()), "outcome_sd": float(data[outcome].std(ddof=1)),
        "r_squared": float(1 - np.sum(resid ** 2) / np.sum((y - y.mean()) ** 2)),
    }


def prepare() -> pd.DataFrame:
    candidates = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv", low_memory=False)
    universe = pd.read_csv(IDEOLOGY / "candidate_ideology_full_universe.csv", low_memory=False)
    federal = pd.read_csv(ELECTIONS / "historical_federal_district_baselines.csv", low_memory=False)
    ideology_columns = [
        "canonical_candidate_id", "best_available_social_ideology", "best_available_social_source",
        "best_available_economic_ideology", "best_available_economic_source",
    ]
    data = (candidates.merge(universe[ideology_columns], on="canonical_candidate_id", how="left", validate="one_to_one")
            .merge(federal, on=["cycle", "chamber", "district"], how="left", validate="many_to_one"))
    data["social_score"] = data.best_available_social_ideology
    data["economic_score"] = data.best_available_economic_ideology
    # Earlier historical builds already supply a resolved prior-presidential
    # margin. Later cycles use their explicit election-specific columns.
    data["presidential_baseline_margin"] = data.prior_pres_dem_margin
    for cycle, column in {1994: "pres_1992_dem_margin", 2014: "pres_2012_dem_margin",
                          2018: "pres_2016_dem_margin", 2022: "pres_2020_dem_margin"}.items():
        data.loc[data.cycle.eq(cycle), "presidential_baseline_margin"] = data.loc[data.cycle.eq(cycle), column]
    data["presidential_overperformance"] = data.legislative_dem_margin - data.presidential_baseline_margin
    data["senate_overperformance"] = data.legislative_dem_margin - data.us_senate_dem_margin
    data["national_baseline_margin"] = data[["presidential_baseline_margin", "us_senate_dem_margin"]].mean(axis=1)
    data["national_overperformance"] = data.legislative_dem_margin - data.national_baseline_margin
    data["published_cmo"] = data.candidate_cmo_total_oof
    data["dem_incumbent_numeric"] = data.dem_incumbent.fillna(False).astype(int)
    data["senate_chamber"] = data.chamber.eq("senate").astype(int)
    data["majority_white"] = data.nonwhite_share.lt(.5)
    data["era"] = np.select([data.cycle.le(2006), data.cycle.le(2014)],
                            ["pre_2008", "obama_era"], default="post_2016")
    return data


def add_fixed_effects(frame: pd.DataFrame, base_controls: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    result = frame.copy()
    columns = list(base_controls or [])
    for cycle in sorted(result.cycle.dropna().unique())[1:]:
        name = f"cycle_{int(cycle)}"
        result[name] = result.cycle.eq(cycle).astype(int)
        columns.append(name)
    return result, columns


def main() -> None:
    data = prepare()
    scored = data[data.social_score.notna()].copy()
    estimates: list[dict[str, object]] = []
    outcomes = ["published_cmo", "presidential_overperformance", "senate_overperformance", "national_overperformance"]
    for outcome in outcomes:
        estimates.append(hc3_ols(scored, outcome, [], "bivariate"))
        estimates.append(hc3_ols(scored, outcome, ["economic_score"], "economic_adjusted"))
        available = scored[scored[outcome].notna()].copy()
        cycle, cycle_controls = add_fixed_effects(available, ["senate_chamber"])
        estimates.append(hc3_ols(cycle, outcome, cycle_controls, "cycle_and_chamber_adjusted"))
        econ_cycle, econ_cycle_controls = add_fixed_effects(available, ["economic_score", "senate_chamber"])
        estimates.append(hc3_ols(econ_cycle, outcome, econ_cycle_controls, "economic_cycle_chamber_adjusted"))
        estimates.append(hc3_ols(available, outcome, ["nonwhite_share", "white_college_share"], "geography_adjusted"))
        full, controls = add_fixed_effects(available, ["economic_score", "dem_incumbent_numeric",
                                                       "nonwhite_share", "white_college_share", "senate_chamber"])
        estimates.append(hc3_ols(full, outcome, controls, "context_and_cycle_adjusted"))
        majority_base = scored[scored.majority_white & scored[outcome].notna()].copy()
        estimates.append(hc3_ols(majority_base, outcome, [], "majority_white_bivariate"))
        estimates.append(hc3_ols(majority_base, outcome, ["economic_score"], "majority_white_economic_adjusted"))
        majority, majority_controls = add_fixed_effects(majority_base, ["economic_score", "dem_incumbent_numeric",
                                                                        "nonwhite_share", "white_college_share", "senate_chamber"])
        estimates.append(hc3_ols(majority, outcome, majority_controls, "majority_white_context_adjusted"))
        for source, group in scored[scored[outcome].notna()].groupby("best_available_social_source"):
            estimates.append(hc3_ols(group, outcome, [], f"bivariate_source:{source}"))
        for era, group in scored[scored[outcome].notna()].groupby("era"):
            estimates.append(hc3_ols(group, outcome, ["economic_score", "dem_incumbent_numeric", "senate_chamber"],
                                     f"era_adjusted:{era}"))
        for cycle_year, group in scored[scored[outcome].notna()].groupby("cycle"):
            estimates.append(hc3_ols(group, outcome, [], f"within_cycle:{int(cycle_year)}"))
        for incumbent_value, group in scored[scored[outcome].notna()].groupby("dem_incumbent_numeric"):
            estimates.append(hc3_ols(group, outcome, [],
                                     "incumbent_only" if incumbent_value else "nonincumbent_only"))
    estimates_df = pd.DataFrame(estimates)

    # Paired comparisons force CMO and national outcomes to use identical rows.
    paired_rows = []
    for outcome in ["presidential_overperformance", "senate_overperformance", "national_overperformance"]:
        pair = scored.dropna(subset=[outcome, "published_cmo", "social_score"])
        for paired_outcome in ["published_cmo", outcome]:
            paired_rows.append(hc3_ols(pair, paired_outcome, [], f"paired_with:{outcome}"))
    paired = pd.DataFrame(paired_rows)

    bins = []
    for outcome in outcomes:
        subset = scored.dropna(subset=[outcome]).copy()
        if len(subset) < 8:
            continue
        subset["social_tercile"] = pd.qcut(subset.social_score.rank(method="first"), 3,
                                            labels=["more_progressive", "middle", "more_conservative"])
        summary = subset.groupby("social_tercile", observed=True).agg(
            candidates=(outcome, "size"), social_mean=("social_score", "mean"),
            outcome_mean=(outcome, "mean"), outcome_median=(outcome, "median")).reset_index()
        summary.insert(0, "outcome", outcome)
        bins.append(summary)
    bins_df = pd.concat(bins, ignore_index=True)

    keep = ["canonical_candidate_id", "candidate", "cycle", "chamber", "district", "incumbent",
            "best_available_social_source", "social_score", "economic_score", "nonwhite_share", "white_college_share",
            "legislative_dem_margin", "presidential_baseline_margin", "us_senate_dem_margin", "national_baseline_margin",
            "published_cmo", "presidential_overperformance", "senate_overperformance", "national_overperformance"]
    OUT.mkdir(parents=True, exist_ok=True)
    data[keep].to_csv(OUT / "social_ideology_national_baseline_detail.csv", index=False)
    estimates_df.to_csv(OUT / "social_ideology_national_baseline_estimates.csv", index=False)
    paired.to_csv(OUT / "social_ideology_national_baseline_paired.csv", index=False)
    bins_df.to_csv(OUT / "social_ideology_national_baseline_terciles.csv", index=False)
    correlations = scored[["social_score", "economic_score", "dem_incumbent_numeric", "nonwhite_share",
                            "white_college_share", "published_cmo", "presidential_overperformance",
                            "senate_overperformance", "national_overperformance"]].corr()
    correlations.to_csv(OUT / "social_ideology_national_baseline_correlations.csv")
    print("Primary bivariate estimates (+ ideology = more conservative):")
    print(estimates_df[estimates_df.specification.eq("bivariate")][[
        "outcome", "n", "cycles", "social_coefficient_full_unit", "effect_per_social_sd",
        "social_ci_low", "social_ci_high", "social_p_value", "r_squared"]].to_string(index=False))
    print("\nPaired comparison:")
    print(paired[["outcome", "specification", "n", "social_coefficient_full_unit", "social_p_value"]].to_string(index=False))
    print("\nTerciles:")
    print(bins_df.to_string(index=False))


if __name__ == "__main__":
    main()
