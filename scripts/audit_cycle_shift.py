"""Quantify cycle-level shifts relevant to pooled Alabama legislative WAR."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    races = pd.read_csv(WAR / "preliminary_war_races.csv")
    races = races[races.war_eligible.astype(bool)].copy()
    measures = [
        "legislative_dem_margin", "statewide_index_margin", "raw_overperformance",
        "prior_pres_dem_margin", "prior_pres_swing", "incumbency_advantage_d",
        "nonwhite_share", "white_college_share", "log_spending_ratio_d_to_r",
        "war_residual_oof", "war_residual_loco",
    ]
    # The current CMO decomposes incumbency into separate Democratic and
    # Republican indicators; retain compatibility with older snapshots without
    # requiring their retired net-advantage column.
    measures = [column for column in measures if column in races.columns]
    summary = (races.groupby("cycle")[measures]
               .agg(["count", "mean", "median", "std"])
               .stack(level=0, future_stack=True).reset_index()
               .rename(columns={"level_1": "measure"}))
    coverage = (races.groupby("cycle", as_index=False)
                .agg(eligible_races=("district", "size"),
                     core_baseline_complete=("core_index_complete", "sum"),
                     finance_complete=("finance_complete", "sum"),
                     presidential_trend_available=("pres_trend_available", "sum")))
    for col in ["core_baseline_complete", "finance_complete", "presidential_trend_available"]:
        coverage[col + "_share"] = coverage[col] / coverage.eligible_races

    offices = pd.read_csv(WAR / "district_baseline_office.csv")
    office_summary = (offices.groupby(["cycle", "office"], as_index=False)
                      .agg(district_rows=("district", "size"),
                           dem_votes=("dem_votes", "sum"), rep_votes=("rep_votes", "sum")))
    office_summary["contested_partisan_office"] = (
        office_summary.dem_votes.gt(0) & office_summary.rep_votes.gt(0))

    summary.to_csv(WAR / "cycle_shift_feature_summary.csv", index=False)
    coverage.to_csv(WAR / "cycle_shift_coverage_summary.csv", index=False)
    office_summary.to_csv(WAR / "cycle_baseline_office_summary.csv", index=False)
    print(coverage.to_string(index=False))
    focus = summary[summary.measure.isin(["legislative_dem_margin", "statewide_index_margin",
                                         "raw_overperformance", "war_residual_oof"])]
    print("\nCycle distribution summary:")
    print(focus.to_string(index=False))


if __name__ == "__main__":
    main()
