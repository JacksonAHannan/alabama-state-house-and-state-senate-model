"""Build reproducible descriptive exhibits for the CMO/ideology article."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
ELECTION_DATES = {
    2010: pd.Timestamp("2010-11-02"), 2014: pd.Timestamp("2014-11-04"),
    2018: pd.Timestamp("2018-11-06"), 2022: pd.Timestamp("2022-11-08"),
}


def spearman(frame: pd.DataFrame, x: str, y: str) -> float:
    usable = frame[[x, y]].dropna()
    return usable[x].corr(usable[y], method="spearman") if len(usable) >= 3 else np.nan


def cluster_bootstrap_spearman(frame: pd.DataFrame, x: str, y: str) -> tuple[float, float]:
    """Person-cluster bootstrap interval for a descriptive rank correlation."""
    usable = frame[["person_id", x, y]].dropna()
    people = usable.person_id.unique()
    if len(people) < 5:
        return np.nan, np.nan
    rng = np.random.default_rng(20260815)
    grouped = {
        person_id: (part[x].to_numpy(), part[y].to_numpy())
        for person_id, part in usable.groupby("person_id")
    }
    estimates = []
    for _ in range(2000):
        sampled = rng.choice(people, size=len(people), replace=True)
        x_values = np.concatenate([grouped[person_id][0] for person_id in sampled])
        y_values = np.concatenate([grouped[person_id][1] for person_id in sampled])
        estimate = spearmanr(x_values, y_values).statistic
        if pd.notna(estimate):
            estimates.append(estimate)
    return tuple(np.quantile(estimates, [0.025, 0.975])) if estimates else (np.nan, np.nan)


def main() -> None:
    cycles = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv")
    universe = pd.read_csv(RESEARCH / "shor_mccarty_candidate_universe.csv")
    scatter = universe[universe.shor_match_status.eq("matched")].copy()
    scatter = scatter.rename(columns={
        "shor_np_score": "np_score",
        "shor_al_dem_conservative_percentile": "al_dem_caucus_conservative_percentile",
        "shor_served_by_election": "served_in_either_chamber_by_election",
    })
    scatter["temporal_use"] = np.where(
        scatter.served_in_either_chamber_by_election.eq(True),
        "pre_election_service_available", "post_election_only",
    )
    scatter.to_csv(RESEARCH / "article_ideology_scatter.csv", index=False)

    specifications = {
        "oof_total": "candidate_cmo_total_oof",
        "district_grouped_total": "candidate_cmo_total_district_grouped",
        "oof_resource_adjusted": "candidate_cmo_resource_adjusted_oof",
        "raw_top_ticket": "raw_overperformance_x",
    }
    samples = {
        "all_matched_through_2018": scatter.cycle.le(2018),
        "exclude_2014": scatter.cycle.ne(2014),
        "pre_election_service": scatter.served_in_either_chamber_by_election.eq(True),
        "pre_election_exclude_2014": (
            scatter.served_in_either_chamber_by_election.eq(True) & scatter.cycle.ne(2014)
        ),
    }
    sensitivity = []
    for sample_name, mask in samples.items():
        part = scatter[mask]
        for spec_name, cmo_col in specifications.items():
            ci_low, ci_high = cluster_bootstrap_spearman(part, cmo_col, "np_score")
            sensitivity.append({
                "sample": sample_name,
                "specification": spec_name,
                "n": int(part[[cmo_col, "np_score"]].dropna().shape[0]),
                "spearman_cmo_vs_np_score": spearman(part, cmo_col, "np_score"),
                "cluster_bootstrap_95_low": ci_low,
                "cluster_bootstrap_95_high": ci_high,
                "interpretation": "positive_means_more_conservative_associated_with_more_overperformance",
            })
    for cycle, part in scatter.groupby("cycle"):
        ci_low, ci_high = cluster_bootstrap_spearman(part, "candidate_cmo_total_oof", "np_score")
        sensitivity.append({
            "sample": f"cycle_{int(cycle)}",
            "specification": "oof_total",
            "n": int(part[["candidate_cmo_total_oof", "np_score"]].dropna().shape[0]),
            "spearman_cmo_vs_np_score": spearman(part, "candidate_cmo_total_oof", "np_score"),
            "cluster_bootstrap_95_low": ci_low,
            "cluster_bootstrap_95_high": ci_high,
            "interpretation": "positive_means_more_conservative_associated_with_more_overperformance",
        })
    pd.DataFrame(sensitivity).to_csv(RESEARCH / "article_ideology_sensitivity.csv", index=False)

    context = (cycles.groupby(["cycle", "district_context"], dropna=False)
               .agg(n=("person_id", "size"),
                    median_oof_cmo=("candidate_cmo_total_oof", "median"),
                    mean_oof_cmo=("candidate_cmo_total_oof", "mean"),
                    median_raw_overperformance=("raw_overperformance_x", "median"),
                    robust_positive_share=("robust_positive", "mean"))
               .reset_index())
    context.to_csv(RESEARCH / "article_context_summary.csv", index=False)

    ranking_cols = [
        "cycle", "chamber", "district", "person_id", "candidate", "incumbent",
        "district_context", "candidate_cmo_total_oof",
        "candidate_cmo_total_district_grouped", "candidate_cmo_resource_adjusted_oof",
        "raw_overperformance_x", "robust_positive",
    ]
    (cycles[cycles.cycle.ne(2014)].sort_values("candidate_cmo_total_oof", ascending=False)
     [ranking_cols].head(30)
     .to_csv(RESEARCH / "article_top_overperformers_excluding_2014.csv", index=False))

    repeats = cycles.groupby("person_id").filter(lambda x: x.cycle.nunique() >= 2).copy()
    repeats.sort_values(["person_id", "cycle"]).to_csv(
        RESEARCH / "article_repeat_candidate_trajectories.csv", index=False
    )

    ledger = pd.read_csv(RESEARCH / "evidence_ledger.csv")
    ledger["evidence_date_parsed"] = pd.to_datetime(ledger.evidence_date, errors="coerce")
    ledger["election_date"] = ledger.election_cycle.map(ELECTION_DATES)
    ledger = ledger[
        ledger.evidence_date_parsed.le(ledger.election_date)
        & ~ledger.review_status.fillna("").str.contains("post_election|retrospective", case=False)
    ].copy()
    coded = ledger.assign(coded_numeric=pd.to_numeric(ledger.coded_value, errors="coerce"))
    coded = coded[coded.coded_numeric.notna()].copy()
    heatmap = (coded.groupby(["person_id", "candidate", "election_cycle", "dimension"], as_index=False)
               .agg(coded_value=("coded_numeric", "median"),
                    evidence_items=("source_url", "size"),
                    sources=("source_url", "nunique"),
                    high_confidence_items=("confidence", lambda x: x.eq("high").sum())))
    heatmap.to_csv(RESEARCH / "article_issue_heatmap.csv", index=False)

    pairs = pd.read_csv(RESEARCH / "matched_pair_evidence.csv")
    pair_cols = [
        "focal_candidate", "comparison_candidate", "cycle", "chamber",
        "cmo_difference", "resource_adjusted_cmo_difference",
        "fundraising_adjusted_cmo_difference", "np_score_difference_focal_minus_comparison",
        "both_ideology_scores_available", "pair_interpretation",
    ]
    decomposition = pairs[pair_cols].copy()
    geography = pd.read_csv(RESEARCH / "cmo_geography_sensitivity.csv")[[
        "person_id", "cycle", "cmo_geography_low", "cmo_geography_high"
    ]]
    focal_geography = geography.rename(columns={
        "person_id": "focal_person_id",
        "cmo_geography_low": "focal_cmo_geography_low",
        "cmo_geography_high": "focal_cmo_geography_high",
    })
    comparison_geography = geography.rename(columns={
        "person_id": "comparison_person_id",
        "cmo_geography_low": "comparison_cmo_geography_low",
        "cmo_geography_high": "comparison_cmo_geography_high",
    })
    decomposition = decomposition.join(
        pairs[["focal_person_id", "comparison_person_id"]]
    ).merge(
        focal_geography, on=["focal_person_id", "cycle"], how="left", validate="many_to_one"
    ).merge(
        comparison_geography, on=["comparison_person_id", "cycle"], how="left",
        validate="many_to_one",
    )
    decomposition["geography_gap_low"] = (
        decomposition.focal_cmo_geography_low - decomposition.comparison_cmo_geography_high
    )
    decomposition["geography_gap_high"] = (
        decomposition.focal_cmo_geography_high - decomposition.comparison_cmo_geography_low
    )
    decomposition["geography_direction_robust"] = (
        decomposition.geography_gap_low.gt(0) | decomposition.geography_gap_high.lt(0)
    )
    decomposition["geography_gap_exceeds_5pt"] = (
        decomposition.geography_gap_low.gt(5) | decomposition.geography_gap_high.lt(-5)
    )
    decomposition["cmo_gap_reduction_after_resource_adjustment"] = (
        decomposition.cmo_difference - decomposition.resource_adjusted_cmo_difference
    )
    decomposition["share_of_cmo_gap_reduced_by_resource_adjustment"] = np.where(
        decomposition.cmo_difference.abs().gt(0),
        decomposition.cmo_gap_reduction_after_resource_adjustment / decomposition.cmo_difference,
        np.nan,
    )
    decomposition.to_csv(RESEARCH / "article_matched_pair_decomposition.csv", index=False)

    baseline_uncertainty = pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_baseline_uncertainty.csv"
    )
    baseline_sensitivity = cycles.merge(
        baseline_uncertainty, on=["cycle", "chamber", "district"], how="left",
        validate="many_to_one",
    )
    baseline_sensitivity["production_minus_scenario_mean"] = (
        baseline_sensitivity.core_index_margin - baseline_sensitivity.baseline_mean
    )
    baseline_sensitivity["raw_overperformance_at_scenario_mean"] = (
        baseline_sensitivity.legislative_dem_margin - baseline_sensitivity.baseline_mean
    )
    baseline_sensitivity["baseline_sensitive_5pt"] = baseline_sensitivity.baseline_range.ge(5)
    baseline_sensitivity.sort_values(
        "baseline_range", ascending=False
    ).to_csv(RESEARCH / "article_baseline_geography_sensitivity.csv", index=False)

    print(
        f"Wrote {len(scatter)} scatter rows, {len(sensitivity)} sensitivity rows, "
        f"{len(context)} context rows, {len(repeats)} repeat rows, {len(heatmap)} issue cells, "
        f"{len(decomposition)} pair decompositions, and {len(baseline_sensitivity)} baseline audits"
    )


if __name__ == "__main__":
    main()
