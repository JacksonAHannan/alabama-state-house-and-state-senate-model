"""Enrich CMO matched comparisons with ideology and competing explanations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"


def main() -> None:
    pairs = pd.read_csv(RESEARCH / "matched_comparisons.csv")
    universe = pd.read_csv(RESEARCH / "shor_mccarty_candidate_universe.csv")
    fields = [
        "person_id",
        "cycle",
        "incumbent",
        "winner",
        "raw_overperformance_x",
        "candidate_cmo_total_cycle_holdout",
        "candidate_cmo_total_district_grouped",
        "candidate_cmo_resource_adjusted_oof",
        "candidate_cmo_fundraising_adjusted_oof",
        "log_spending_ratio_d_to_r",
        "log_fundraising_ratio_d_to_r",
        "shor_match_status",
        "shor_np_score",
        "shor_al_dem_conservative_percentile",
        "shor_served_by_election",
    ]
    focal = universe[fields].rename(
        columns={
            "person_id": "focal_person_id",
            **{field: f"focal_{field}" for field in fields if field not in {"person_id", "cycle"}},
        }
    )
    comparison = universe[fields].rename(
        columns={
            "person_id": "comparison_person_id",
            **{field: f"comparison_{field}" for field in fields if field not in {"person_id", "cycle"}},
        }
    )
    result = pairs.merge(
        focal, on=["focal_person_id", "cycle"], how="left", validate="many_to_one"
    ).merge(
        comparison,
        on=["comparison_person_id", "cycle"],
        how="left",
        validate="many_to_one",
    )
    result["np_score_difference_focal_minus_comparison"] = (
        result.focal_shor_np_score - result.comparison_shor_np_score
    )
    result["both_ideology_scores_available"] = (
        result.focal_shor_match_status.eq("matched")
        & result.comparison_shor_match_status.eq("matched")
    )
    result["same_broad_ideology_band"] = (
        result.both_ideology_scores_available
        & result.np_score_difference_focal_minus_comparison.abs().le(0.10)
    )
    result["raw_overperformance_difference"] = (
        result.focal_raw_overperformance_x - result.comparison_raw_overperformance_x
    )
    result["cycle_holdout_cmo_difference"] = (
        result.focal_candidate_cmo_total_cycle_holdout
        - result.comparison_candidate_cmo_total_cycle_holdout
    )
    result["district_grouped_cmo_difference"] = (
        result.focal_candidate_cmo_total_district_grouped
        - result.comparison_candidate_cmo_total_district_grouped
    )
    result["resource_adjusted_cmo_difference"] = (
        result.focal_candidate_cmo_resource_adjusted_oof
        - result.comparison_candidate_cmo_resource_adjusted_oof
    )
    result["fundraising_adjusted_cmo_difference"] = (
        result.focal_candidate_cmo_fundraising_adjusted_oof
        - result.comparison_candidate_cmo_fundraising_adjusted_oof
    )
    result["pair_interpretation"] = "ideology_unobserved_for_one_or_both"
    result.loc[
        result.both_ideology_scores_available
        & result.np_score_difference_focal_minus_comparison.gt(0.10),
        "pair_interpretation",
    ] = "higher_cmo_candidate_more_conservative"
    result.loc[
        result.both_ideology_scores_available
        & result.np_score_difference_focal_minus_comparison.lt(-0.10),
        "pair_interpretation",
    ] = "higher_cmo_candidate_more_progressive"
    result.loc[result.same_broad_ideology_band, "pair_interpretation"] = (
        "large_cmo_difference_without_large_ideology_difference"
    )
    output = RESEARCH / "matched_pair_evidence.csv"
    result.to_csv(output, index=False)
    print(f"Wrote {len(result)} pairs to {output}")
    print(result.pair_interpretation.value_counts().to_string())


if __name__ == "__main__":
    main()
